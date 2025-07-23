import datetime
from pathlib import Path

from pydantic import ValidationError
from tqdm import tqdm

from ursa.adapters.base_adapter import BaseAdapter
from ursa.domain.schemas import BenchmarkTree, DMSRouteList, TargetInfo
from ursa.domain.tree import deduplicate_routes
from ursa.exceptions import UrsaException, UrsaIOException
from ursa.io import load_json_gz, save_json, save_json_gz
from ursa.utils.hashing import generate_run_hash, get_file_hash
from ursa.utils.logging import logger


def process_model_run(
    model_name: str,
    adapter: BaseAdapter,
    raw_results_dir: Path,
    processed_dir: Path,
    targets_map: dict[str, TargetInfo],
) -> None:
    """
    Orchestrates the complete processing pipeline for a given model's output.

    This function performs validation, transformation, deduplication, and
    serialization, culminating in a single, consolidated results file and a
    human-readable manifest.
    """
    logger.info(f"--- Starting Ursa Processing for Model: '{model_name}' ---")
    processed_dir.mkdir(parents=True, exist_ok=True)
    raw_files = sorted(list(raw_results_dir.glob("*.json.gz")))

    if not raw_files:
        logger.warning(f"No '.json.gz' files found in {raw_results_dir}. Aborting.")
        return

    # 1. INITIAL SETUP & ANONYMIZATION
    # Generate a unique, filesystem-safe hash for this specific run.
    run_hash = generate_run_hash(model_name, [get_file_hash(p) for p in raw_files])
    logger.info(f"Generated unique run hash: '{run_hash}'")

    # 2. INITIALIZE ACCUMULATORS
    # This dictionary will hold all valid, unique BenchmarkTree objects in memory.
    final_output_data: dict[str, list[BenchmarkTree]] = {}

    # These variables will track detailed statistics for the manifest.
    stats = {"succeeded": 0, "failed": 0, "targets_with_pred": set(), "preds_per_target": []}
    source_file_info = {}

    # 3. CORE PROCESSING LOOP
    # Iterate through each file of raw model outputs.
    for file_path in raw_files:
        try:
            logger.info(f"Processing file: {file_path.name}")
            raw_routes_per_target = load_json_gz(file_path)
            source_file_info[file_path.name] = get_file_hash(file_path)
        except UrsaIOException as e:
            logger.error(f"Could not read or parse file {file_path}. Skipping. Error: {e}")
            continue

        # Iterate through each target within the file.
        pbar = tqdm(raw_routes_per_target.items(), desc="Processing predictions", unit="target")
        for target_id, raw_routes_list in pbar:
            if target_id not in targets_map:
                logger.warning(f"Skipping routes for '{target_id}': No target info in targets map.")
                continue

            try:
                validated_routes = DMSRouteList.model_validate(raw_routes_list)
                target_info = targets_map[target_id]

                transformed_trees: list[BenchmarkTree] = []
                for raw_route in validated_routes.root:
                    try:
                        tree = adapter.transform(raw_route, target_info)
                        transformed_trees.append(tree)
                    except UrsaException as e:
                        # This route failed, but others for the same target may succeed.
                        logger.warning(f"  - Route for '{target_id}' failed transformation: {e}")
                        stats["failed"] += 1

                unique_trees = deduplicate_routes(transformed_trees)

                if num_unique := len(unique_trees):
                    final_output_data[target_id] = unique_trees
                    stats["succeeded"] += num_unique
                    stats["targets_with_pred"].add(target_id)
                    stats["preds_per_target"].append(num_unique)

            except (ValidationError, UrsaException) as e:
                # A catastrophic failure for this target (e.g., malformed main list).
                num_routes = len(raw_routes_list) if isinstance(raw_routes_list, list) else 1
                logger.error(f"Could not process any routes for target '{target_id}'. Error: {e}")
                stats["failed"] += num_routes

    # 4. FINAL WRITE & MANIFEST GENERATION
    if final_output_data:
        output_filename = f"{run_hash}-results.json.gz"
        output_path = processed_dir / output_filename
        logger.info(f"Writing all {stats['succeeded']} unique routes to single file: {output_path}")
        save_json_gz(final_output_data, output_path)
    else:
        logger.warning("No routes were successfully processed. No output file written.")
        output_filename = None

    num_targets_with_preds = len(stats["targets_with_pred"])
    avg_preds = (sum(stats["preds_per_target"]) / num_targets_with_preds) if num_targets_with_preds > 0 else 0

    manifest = {
        "run_hash": run_hash,
        "model_name": model_name,
        "results_file": output_filename,
        "processing_timestamp_utc": datetime.datetime.utcnow().isoformat(timespec="seconds"),
        "source_files": source_file_info,
        "statistics": {
            "total_unique_routes_saved": stats["succeeded"],
            "total_routes_failed_or_duplicate": stats["failed"],
            "num_targets_with_at_least_one_route": num_targets_with_preds,
            "avg_unique_routes_per_successful_target": round(avg_preds, 2),
            "max_unique_routes_for_any_target": max(stats["preds_per_target"], default=0),
        },
    }
    manifest_path = processed_dir / f"{run_hash}-manifest.json"
    save_json(manifest, manifest_path)
    logger.info(f"--- Processing Complete. Manifest written to {manifest_path} ---")
