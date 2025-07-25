import argparse
import json
import pickle
import time
from pathlib import Path

from directmultistep.generate import generate_routes
from directmultistep.utils.logging_config import logger
from directmultistep.utils.post_process import find_path_strings_with_commercial_sm
from directmultistep.utils.pre_process import canonicalize_smiles
from tqdm import tqdm

from ursa.io import load_targets_csv

base_dir = Path(__file__).resolve().parents[2]

targets = load_targets_csv(base_dir / "data" / "rs_first_25.csv")
dms_dir = base_dir / "data" / "models" / "dms"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, required=True, help="Name of the model")
    parser.add_argument("--use_fp16", action="store_true", help="Whether to use FP16")
    args = parser.parse_args()
    model_name = args.model_name
    use_fp16 = args.use_fp16

    logger.info(f"model_name: {model_name}")
    logger.info(f"use_fp16: {use_fp16}")

    logger.info("Loading targets and stock compounds")

    with open(dms_dir / "compounds" / "eMolecules.txt") as f:
        emol_stock_set = set(f.read().splitlines())
    with open(dms_dir / "compounds" / "buyables-stock.txt") as f:
        buyables_stock_set = set(f.read().splitlines())

    folder_name = f"dms-{model_name}_fp16" if use_fp16 else f"dms-{model_name}"
    save_dir = base_dir / "data" / "evaluations" / folder_name
    save_dir.mkdir(parents=True, exist_ok=True)
    SAVED_PATH = save_dir / "paths.pkl"
    SAVED_COUNT_PATH = save_dir / "count.json"

    logger.info("Retrosythesis starting")
    start = time.time()

    all_paths = {}
    raw_solved_count = 0
    buyable_solved_count = 0
    emol_solved_count = 0

    for target_key, target_smiles in tqdm(targets.items()):
        target = canonicalize_smiles(target_smiles)
        raw_paths = []
        if model_name == "explorer XL" or model_name == "explorer":
            raw_paths += generate_routes(
                target,
                n_steps=None,
                starting_material=None,
                beam_size=50,
                model=model_name,
                config_path=dms_dir / "dms_dictionary.yaml",
                ckpt_dir=dms_dir / "checkpoints",
                commercial_stock=None,
                use_fp16=use_fp16,
            )
        else:
            for step in range(2, 9):
                raw_paths += generate_routes(
                    target,
                    n_steps=step,
                    starting_material=None,
                    beam_size=50,
                    model=model_name,
                    config_path=dms_dir / "dms_dictionary.yaml",
                    ckpt_dir=dms_dir / "checkpoints",
                    commercial_stock=None,
                    use_fp16=use_fp16,
                )
        buyables_paths = find_path_strings_with_commercial_sm(raw_paths, commercial_stock=buyables_stock_set)
        emol_paths = find_path_strings_with_commercial_sm(raw_paths, commercial_stock=emol_stock_set)
        if len(raw_paths) > 0:
            raw_solved_count += 1
        if len(buyables_paths) > 0:
            buyable_solved_count += 1
        if len(emol_paths) > 0:
            emol_solved_count += 1
        logger.info(f"Current raw solved count: {raw_solved_count}")
        logger.info(f"Current buyable solved count: {buyable_solved_count}")
        logger.info(f"Current emol solved count: {emol_solved_count}")
        all_paths[target_key] = [raw_paths, buyables_paths, emol_paths]

    end = time.time()

    results = {
        "raw_solved_count": raw_solved_count,
        "buyable_solved_count": buyable_solved_count,
        "emol_solved_count": emol_solved_count,
        "time_elapsed": end - start,
    }
    logger.info(f"Results: {results}")
    with open(SAVED_COUNT_PATH, "w") as f:
        json.dump(results, f)
    with open(SAVED_PATH, "wb") as f:
        pickle.dump(all_paths, f)

    usage = """
    python scripts/dms/run-dms-predictions.py --model_name "flash" --use_fp16
    """
    logger.info(usage)
