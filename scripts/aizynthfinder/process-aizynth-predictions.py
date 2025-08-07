# scripts/aizynth/process-aizynth-predictions.py
"""
Processes raw output from an AiZynthFinder-type retrosynthesis model.
"""

import argparse
from pathlib import Path

from ursa.adapters.aizynth_adapter import AizynthAdapter
from ursa.core import process_model_run
from ursa.exceptions import UrsaException
from ursa.io import load_and_prepare_targets
from ursa.utils.logging import logger


def main() -> None:
    """Main function to parse arguments and orchestrate the processing."""
    # fmt:off
    parser = argparse.ArgumentParser(description="Transform AiZynthFinder model outputs for the Ursa benchmark.")
    parser.add_argument("--model-name", type=str, required=True, 
           help="A unique name for this model run (e.g., 'aizynth_v1_run1').")
    parser.add_argument("--raw-file", type=Path, required=True,
           help="Path to the raw *.json.gz output file from the AiZynthFinder model.")
    parser.add_argument("--output-dir", type=Path, required=True,
           help="Directory where the processed, anonymized data will be saved.")
    parser.add_argument("--targets-file", type=Path, required=True,
           help="Path to a file mapping target IDs to their SMILES strings.")
    # fmt:on
    args = parser.parse_args()

    # you can adjust this if you don't run from the root directory
    base_dir = Path(__file__).resolve().parents[2]
    args.raw_file = base_dir / args.raw_file
    args.output_dir = base_dir / args.output_dir
    args.targets_file = base_dir / args.targets_file

    try:
        targets_map = load_and_prepare_targets(args.targets_file)
        aizynth_adapter = AizynthAdapter()

        process_model_run(
            model_name=args.model_name,
            adapter=aizynth_adapter,
            raw_results_file=args.raw_file,
            processed_dir=args.output_dir,
            targets_map=targets_map,
        )
        logger.info("🎉 Script finished successfully. 🎉")

    except UrsaException as e:
        logger.error(f"A critical error occurred during processing: {e}")
        exit(1)
    except Exception as e:
        logger.critical(f"An unexpected, non-Ursa error occurred: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()
