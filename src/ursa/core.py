import datetime
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ursa.adapters.base_adapter import BaseAdapter
from ursa.domain.schemas import RunStatistics, TargetInfo
from ursa.domain.tree import deduplicate_routes
from ursa.exceptions import UrsaIOException
from ursa.io import load_json_gz, save_json, save_json_gz
from ursa.utils.hashing import generate_run_hash, get_file_hash
from ursa.utils.logging import logger


def process_model_run(
    model_name: str,
    adapter: BaseAdapter,
    raw_results_file: Path,
    processed_dir: Path,
    targets_map: dict[str, TargetInfo],
) -> None:
    """
    Orchestrates the processing pipeline for a model's output, now fully decoupled.
    """
    logger.info(f"--- Starting Ursa Processing for Model: '{model_name}' ---")
    processed_dir.mkdir(parents=True, exist_ok=True)
    # raw_files = sorted(list(raw_results_dir.glob("*.json.gz")))

    # if not raw_files:
    #     logger.warning(f"No '.json.gz' files found in {raw_results_dir}. Aborting.")
    #     return

    run_hash = generate_run_hash(model_name, [get_file_hash(raw_results_file)])
    logger.info(f"Generated unique run hash: '{run_hash}'")

    final_output_data: dict[str, list[dict[str, Any]]] = {}  # Store as dicts for direct JSON serialization
    stats = RunStatistics()
    source_file_info = {}

    for file_path in [raw_results_file]:
        try:
            logger.info(f"Processing file: {file_path.name}")
            raw_data_per_target = load_json_gz(file_path)
            source_file_info[file_path.name] = get_file_hash(file_path)
        except UrsaIOException as e:
            logger.error(f"Could not read or parse file {file_path}. Skipping. Error: {e}")
            continue

        pbar = tqdm(raw_data_per_target.items(), desc="Processing targets", unit="target")
        for target_id, raw_routes_list in pbar:
            if target_id not in targets_map:
                logger.warning(f"Skipping routes for '{target_id}': No target info found.")
                continue

            # This is now fully generic. The adapter handles all the specifics.
            transformed_trees = list(adapter.adapt(raw_routes_list, targets_map[target_id]))

            # Deduplicate the successful routes for this target
            unique_trees = deduplicate_routes(transformed_trees)

            if len(unique_trees):
                # Dump to dict immediately to avoid holding complex Pydantic objects in memory
                final_output_data[target_id] = [tree.model_dump() for tree in unique_trees]
                stats.targets_with_at_least_one_route.add(target_id)

            # Update statistics based on the process
            stats.successful_routes_before_dedup += len(transformed_trees)
            stats.final_unique_routes_saved += len(unique_trees)

    if final_output_data:
        output_filename = f"{run_hash}-results.json.gz"
        output_path = processed_dir / output_filename
        logger.info(f"Writing {stats.final_unique_routes_saved} unique routes to: {output_path}")
        save_json_gz(final_output_data, output_path)
    else:
        logger.warning("No routes were successfully processed. No output file written.")
        output_filename = None

    manifest = {
        "run_hash": run_hash,
        "model_name": model_name,
        "results_file": output_filename,
        "processing_timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "source_files": source_file_info,
        "statistics": stats.to_manifest_dict(),
    }
    manifest_path = processed_dir / f"{run_hash}-manifest.json"
    save_json(manifest, manifest_path)
    logger.info(f"--- Processing Complete. Manifest written to {manifest_path} ---")
