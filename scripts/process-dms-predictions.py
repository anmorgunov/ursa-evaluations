"""
Processes raw output from a DMS-type retrosynthesis model.

This script performs the following actions:
1.  Reads raw model outputs (gzipped JSON files) from an input directory.
2.  Loads a map of target IDs to target SMILES.
3.  Uses the Ursa DMSAdapter to transform the raw data into the canonical
    BenchmarkTree format. This includes canonicalizing all SMILES and
    validating the tree structure.
4.  Anonymizes the run by generating a unique hash based on the model name
    and the content of the input files.
5.  Saves the processed, validated, and anonymized routes to an output
    directory.
6.  Creates a manifest.json file to allow for verification of the run.

Example Usage:
    python scripts/process-dms-predictions.py \
        --model-name "dms_explorer_xl_961_buy" \
        --raw-dir "data/evaluations/dms_explorer_xl_buy" \
        --output-dir "data/processed/dms_explorer_xl_buy" \
        --targets-file "data/ReRSA_dataset_961_smiles.json.gz"
"""

import argparse
import gzip
import json
from pathlib import Path

from ursa.adapters.dms_adapter import DMSAdapter
from ursa.core import process_model_run
from ursa.domain.chem import canonicalize_smiles
from ursa.domain.schemas import TargetInfo
from ursa.exceptions import UrsaException
from ursa.utils.logging import logger


def load_and_prepare_targets(file_path: Path) -> dict[str, TargetInfo]:
    """
    Loads a JSON file containing target IDs and SMILES, canonicalizes the SMILES,
    and prepares a dictionary of TargetInfo objects.

    Args:
        file_path: Path to the JSON file.
                   Expected format: {"target_id_1": "SMILES_1", ...}

    Returns:
        A dictionary mapping target IDs to validated TargetInfo objects.

    Raises:
        UrsaException: If a target SMILES is invalid.
    """
    logger.info(f"Loading and preparing targets from {file_path}...")
    try:
        with gzip.open(file_path, "rt") as f:
            targets_json = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to read or parse targets file: {e}")
        raise UrsaException from e

    prepared_targets: dict[str, TargetInfo] = {}
    for target_id, raw_smiles in targets_json.items():
        try:
            # Canonicalize smiles right at the start.
            canon_smiles = canonicalize_smiles(raw_smiles)
            prepared_targets[target_id] = TargetInfo(id=target_id, smiles=canon_smiles)
        except UrsaException as e:
            logger.error(f"Invalid SMILES for target '{target_id}': {raw_smiles}. Cannot proceed.")
            # This is a fatal error for a run; we must have valid targets.
            raise e

    logger.info(f"Successfully prepared {len(prepared_targets)} targets.")
    return prepared_targets


def main() -> None:
    """Main function to parse arguments and orchestrate the processing."""
    # fmt:off
    parser = argparse.ArgumentParser(description="Transform DMS model outputs for the Ursa benchmark.")
    parser.add_argument("--model-name", type=str, required=True, 
           help="A unique name for this model run (e.g., 'dms_v1_run1'). Used for anonymization.")
    parser.add_argument("--raw-dir", type=Path, required=True,
           help="Directory containing the raw *.json.gz output files from the DMS model.")
    parser.add_argument("--output-dir", type=Path, required=True,
           help="Directory where the processed, anonymized data will be saved.")
    parser.add_argument("--targets-file", type=Path, required=True,
           help="Path to a JSON file mapping target IDs to their SMILES strings.")
    # fmt:on
    args = parser.parse_args()
    base_dir = Path(__file__).resolve().parents[1]
    args.raw_dir = base_dir / args.raw_dir
    args.output_dir = base_dir / args.output_dir
    args.targets_file = base_dir / args.targets_file

    try:
        # 1. Prepare the target information.
        targets_map = load_and_prepare_targets(args.targets_file)

        # 2. Instantiate the specific adapter we need.
        dms_adapter = DMSAdapter()

        # 3. Call the core processing function from our library.
        # This function encapsulates all the complex logic we built.
        process_model_run(
            model_name=args.model_name,
            adapter=dms_adapter,
            raw_results_dir=args.raw_dir,
            processed_dir=args.output_dir,
            targets_map=targets_map,
        )
        logger.info("🎉 Script finished successfully. 🎉")

    except UrsaException as e:
        logger.error(f"A critical error occurred during processing: {e}")
        logger.error("Script aborted.")
        # Exit with a non-zero status code to indicate failure
        exit(1)
    except Exception as e:
        logger.critical(f"An unexpected, non-Ursa error occurred: {e}", exc_info=True)
        logger.critical("Script aborted due to a fatal error.")
        exit(1)


if __name__ == "__main__":
    main()
