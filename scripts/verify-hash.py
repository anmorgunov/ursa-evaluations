"""
Verifies the integrity of a processed Ursa benchmark run.

This script reads a manifest file, locates the original raw data files,
and re-computes the run hash to ensure it matches the one stored in the
manifest. This provides cryptographic proof that the processed data has not been
tampered with and corresponds exactly to the specified raw inputs.

Example Usage:
    python scripts/verify-hash.py \
        --manifest "data/processed/dms_explorer_xl_buy/ursa-run-7ef88905b36129da99b3fda1b0c3571132d5c925d6c14a8d86861bf134dae756-manifest.json" \
        --raw-dir "data/evaluations/dms_explorer_xl_buy"
"""

import argparse
import json
from pathlib import Path

from ursa.exceptions import UrsaIOException
from ursa.utils.hashing import generate_run_hash, get_file_hash
from ursa.utils.logging import logger

# ANSI color codes for pretty printing
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def main() -> None:
    """Main function to parse arguments and orchestrate the verification."""
    parser = argparse.ArgumentParser(description="Verify the integrity of a processed Ursa benchmark run.")
    parser.add_argument(
        "--manifest", type=Path, required=True, help="Path to the manifest.json file for the run to be verified."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        required=True,
        help="Path to the ORIGINAL raw data directory containing the source files.",
    )
    args = parser.parse_args()

    try:
        # 1. LOAD THE MANIFEST FILE
        logger.info(f"Loading manifest from: {args.manifest}")
        with args.manifest.open("r") as f:
            manifest_data = json.load(f)

        # 2. EXTRACT NECESSARY INFO FROM MANIFEST
        # This is the hash we are trying to match.
        original_hash_from_manifest = manifest_data["run_hash"]
        model_name = manifest_data["model_name"]
        source_files = manifest_data["source_files"]  # This is a dict of filename -> hash

        logger.info(f"Verifying run for model '{model_name}'...")
        logger.info(f"Original run hash from manifest: {original_hash_from_manifest}")

        # 3. RE-CALCULATE HASHES OF RAW SOURCE FILES
        recalculated_file_hashes = []
        for filename in sorted(source_files.keys()):  # Sort for deterministic order
            file_path = args.raw_dir / filename
            if not file_path.is_file():
                logger.error(f"{RED}FAILURE: Source file '{filename}' not found at expected path: {file_path}{RESET}")
                exit(1)

            # Use the exact same hashing function from our library
            file_hash = get_file_hash(file_path)
            recalculated_file_hashes.append(file_hash)
            logger.info(f"  - Calculated hash for '{filename}': {file_hash[:12]}...")

        # 4. RE-CALCULATE THE FINAL RUN HASH
        # Use the exact same run hash generation function from our library
        recalculated_run_hash = generate_run_hash(model_name, recalculated_file_hashes)
        logger.info(f"Recalculated run hash from source files: {recalculated_run_hash}")

        # 5. COMPARE AND REPORT THE RESULT
        if recalculated_run_hash == original_hash_from_manifest:
            logger.info(f"{GREEN}---> SUCCESS: Verification passed. The hashes match! <---{RESET}")
        else:
            logger.error(f"{RED}---> FAILURE: Verification FAILED. The hashes DO NOT match. <---{RESET}")
            logger.error("This means the raw input files have changed or the model name is different.")
            exit(1)

    except FileNotFoundError:
        logger.error(f"{RED}FAILURE: Manifest file not found at: {args.manifest}{RESET}")
        exit(1)
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"{RED}FAILURE: Manifest file is corrupted or malformed. Error: {e}{RESET}")
        exit(1)
    except UrsaIOException as e:
        logger.error(f"{RED}FAILURE: An I/O error occurred while reading a source file: {e}{RESET}")
        exit(1)


if __name__ == "__main__":
    main()
