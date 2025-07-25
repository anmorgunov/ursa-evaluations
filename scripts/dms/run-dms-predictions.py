import argparse
import json
import time
from pathlib import Path

from directmultistep.generate import create_beam_search, load_model, prepare_input_tensors
from directmultistep.model import ModelFactory
from directmultistep.utils.dataset import RoutesProcessing
from directmultistep.utils.logging_config import logger
from directmultistep.utils.post_process import (
    find_path_strings_with_commercial_sm,
    find_valid_paths,
)
from directmultistep.utils.pre_process import canonicalize_smiles
from tqdm import tqdm

from ursa.io import load_targets_csv, save_json_gz

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

    logger.info("Retrosythesis starting")
    start = time.time()

    valid_results = {}
    buyable_results = {}
    emol_results = {}
    raw_solved_count = 0
    buyable_solved_count = 0
    emol_solved_count = 0

    model = load_model(model_name, dms_dir / "checkpoints", use_fp16)

    rds = RoutesProcessing(metadata_path=dms_dir / "dms_dictionary.yaml")
    product_max_length, sm_max_length, beam_obj = create_beam_search(model, 50, dms_dir / "dms_dictionary.yaml")

    for target_key, target_smiles in tqdm(targets.items()):
        target = canonicalize_smiles(target_smiles)
        all_beam_results_NS2 = []
        if model_name == "explorer XL" or model_name == "explorer":
            # Prepare input tensors
            encoder_inp, steps_tens, path_tens = prepare_input_tensors(
                target, None, None, rds, product_max_length, sm_max_length, use_fp16
            )

            # Run beam search
            device = ModelFactory.determine_device()
            beam_result_BS2 = beam_obj.decode(
                src_BC=encoder_inp.to(device),
                steps_B1=steps_tens.to(device) if steps_tens is not None else None,
                path_start_BL=path_tens.to(device),
            )
            for beam_result_S2 in beam_result_BS2:
                all_beam_results_NS2.append(beam_result_S2)
        else:
            for step in range(2, 9):
                # Prepare input tensors
                encoder_inp, steps_tens, path_tens = prepare_input_tensors(
                    target, step, None, rds, product_max_length, sm_max_length, use_fp16
                )

                # Run beam search
                device = ModelFactory.determine_device()
                beam_result_BS2 = beam_obj.decode(
                    src_BC=encoder_inp.to(device),
                    steps_B1=steps_tens.to(device) if steps_tens is not None else None,
                    path_start_BL=path_tens.to(device),
                )
                for beam_result_S2 in beam_result_BS2:
                    all_beam_results_NS2.append(beam_result_S2)
        valid_paths_NS2n = find_valid_paths(all_beam_results_NS2)
        raw_paths = [beam_result[0] for beam_result in valid_paths_NS2n[0]]
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
        valid_results[target_key] = [eval(p) for p in raw_paths]
        buyable_results[target_key] = [eval(p) for p in buyables_paths]
        emol_results[target_key] = [eval(p) for p in emol_paths]

    end = time.time()

    results = {
        "raw_solved_count": raw_solved_count,
        "buyable_solved_count": buyable_solved_count,
        "emol_solved_count": emol_solved_count,
        "time_elapsed": end - start,
    }
    logger.info(f"Results: {results}")
    with open(save_dir / "results.json", "w") as f:
        json.dump(results, f)
    save_json_gz(valid_results, save_dir / "valid_results.json.gz")
    save_json_gz(buyable_results, save_dir / "buyable_results.json.gz")
    save_json_gz(emol_results, save_dir / "emol_results.json.gz")

    usage = """
    python scripts/dms/run-dms-predictions.py --model_name "flash" --use_fp16
    """
    logger.info(usage)
