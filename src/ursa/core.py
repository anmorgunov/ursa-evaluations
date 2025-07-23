import datetime
from pathlib import Path

from pydantic import ValidationError

from ursa.adapters.base_adapter import BaseAdapter
from ursa.domain.schemas import DMSTree, TargetInfo
from ursa.exceptions import UrsaException
from ursa.io import get_file_hash, load_json_gz, save_json_gz, save_pydantic_model_gz
from ursa.utils.hashing import generate_run_hash
from ursa.utils.logging import logger


def process_model_run(
    model_name: str,
    adapter: BaseAdapter,
    raw_results_dir: Path,
    processed_dir: Path,
    targets_map: dict[str, TargetInfo],
) -> None:
    """
    Processes a directory of raw model outputs, transforms them using the
    provided adapter, and saves them to an anonymized, structured directory.

    Args:
        model_name: A unique name for the model (e.g., "dms_v1").
        adapter: An instantiated adapter object (e.g., DMSAdapter()).
        raw_results_dir: The path to the directory with raw model outputs.
        processed_dir: The root path where processed data will be saved.
        targets_map: A dict mapping target_id to TargetInfo Pydantic models.
    """
    logger.info(f"Starting processing for model: '{model_name}'")
    raw_files = sorted(list(raw_results_dir.glob("*.json.gz")))
    if not raw_files:
        logger.warning(f"No '.json.gz' files found in {raw_results_dir}. Aborting.")
        return

    # 1. Generate the anonymous run ID
    file_hashes = [get_file_hash(p) for p in raw_files]
    run_hash = generate_run_hash(model_name, file_hashes)
    run_output_dir = processed_dir / run_hash
    run_output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Anonymized run hash: '{run_hash}'. Output dir: {run_output_dir}")

    # 2. Process each file and its routes
    success_count, failure_count = 0, 0
    source_file_info = {}

    for file_path in raw_files:
        logger.info(f"Processing file: {file_path.name}")
        raw_routes_dict = load_json_gz(file_path)

        for target_id, raw_route in raw_routes_dict.items():
            if target_id not in targets_map:
                logger.warning(f"Skipping route for '{target_id}': No target info provided.")
                failure_count += 1
                continue

            target_info = targets_map[target_id]
            # This is the bomb disposal unit
            try:
                # Validate raw input against the DMS schema
                dms_data = DMSTree.model_validate(raw_route)
                # The main transformation call. This can raise UrsaException.
                benchmark_tree = adapter.transform(dms_data, target_info)
                # If we get here, it worked. Save the output.
                output_path = run_output_dir / f"{target_id}.json.gz"
                save_pydantic_model_gz(benchmark_tree, output_path)
                success_count += 1

            except (ValidationError, UrsaException) as e:
                logger.warning(
                    f"Failed to process route for target '{target_id}' from file "
                    f"'{file_path.name}'. Reason: {e}"
                )
                failure_count += 1

        source_file_info[file_path.name] = get_file_hash(file_path)

    # 3. Create the manifest for verifiability
    manifest = {
        "run_hash": run_hash,
        "model_name": model_name,
        "processing_timestamp_utc": datetime.datetime.utcnow().isoformat(),
        "source_files": source_file_info,
        "statistics": {
            "routes_succeeded": success_count,
            "routes_failed": failure_count,
        }
    }
    save_json_gz(manifest, processed_dir / "manifest.json")
    logger.info(f"Processing complete. Success: {success_count}, Failed: {failure_count}.")
    logger.info(f"Manifest written to {processed_dir / 'manifest.json'}")