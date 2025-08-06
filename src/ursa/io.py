import csv
import gzip
import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from ursa.domain.chem import canonicalize_smiles
from ursa.domain.schemas import TargetInfo
from ursa.exceptions import UrsaException, UrsaIOException, UrsaSerializationError
from ursa.utils.logging import logger

# This allows us to return the same type that was passed in.
# e.g., load_model(MyModel) -> MyModel
T = TypeVar("T", bound=BaseModel)


def save_json_gz(data: dict[str, Any], path: Path) -> None:
    """
    Serializes a standard dictionary to a gzipped JSON file.

    The calling function is responsible for ensuring the dict is serializable
    (e.g., by calling .model_dump() on Pydantic objects first).
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # We assume the data is a clean dict, no need for custom encoders.
        json_str = json.dumps(data, indent=2)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(json_str)
    except TypeError as e:
        logger.error(f"Data for {path} is not JSON serializable: {e}")
        raise UrsaSerializationError(f"Data serialization error for {path}: {e}") from e
    except OSError as e:
        logger.error(f"Failed to write or serialize gzipped JSON to {path}: {e}")
        raise UrsaIOException(f"Data saving/serialization error on {path}: {e}") from e


def load_json_gz(path: Path) -> dict[str, Any]:
    """
    Loads a gzipped JSON file into a Python dictionary.

    This is a low-level loader. It performs no validation beyond ensuring
    the file contains valid JSON.
    """
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            loaded_data = json.load(f)
            if not isinstance(loaded_data, dict):
                raise UrsaIOException(f"Expected a JSON object (dict), but found {type(loaded_data)} in {path}")
            return loaded_data
    except (OSError, gzip.BadGzipFile, json.JSONDecodeError) as e:
        logger.error(f"Failed to load or parse gzipped JSON file: {path}")
        raise UrsaIOException(f"Data loading error on {path}: {e}") from e


def save_json(data: dict[str, Any], path: Path) -> None:
    """Saves a Python dictionary to a standard, uncompressed JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to write to JSON file: {path}")
        raise UrsaIOException(f"Data saving error on {path}: {e}") from e


def load_targets_csv(path: Path) -> dict[str, str]:
    """
    Loads a CSV file containing target IDs and SMILES.

    The CSV must have a header row with "Structure ID" and "SMILES" columns.
    Returns a dictionary mapping target IDs to SMILES strings.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                logger.warning(f"CSV file {path} is empty or has no header")
                return {}
            data = {row["Structure ID"]: row["SMILES"] for row in reader}
            if not data:
                logger.warning(f"CSV file {path} is empty")
            return data
    except KeyError as e:
        logger.error(f"Missing required column in CSV file {path}: {e}")
        raise UrsaIOException(f"CSV column {e} not found in {path}") from e
    except OSError as e:
        logger.error(f"Failed to read CSV file: {path}")
        raise UrsaIOException(f"Data loading error on {path}: {e}") from e
    except csv.Error as e:
        logger.error(f"Failed to parse CSV file: {path}")
        raise UrsaIOException(f"CSV parsing error on {path}: {e}") from e


def load_targets_json(path: Path) -> dict[str, str]:
    """
    Loads a JSON file containing target IDs and SMILES.

    Expected format: {"target_id_1": "SMILES_1", ...}
    Returns a dictionary mapping target IDs to SMILES strings.
    """
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt") as f:
                data = json.load(f)
        else:
            with path.open("r") as f:
                data = json.load(f)

        if not isinstance(data, dict):
            raise UrsaIOException(f"Expected JSON object (dict), found {type(data)}")
        if not data:
            logger.warning(f"JSON file {path} is empty")
        return data
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to read or parse JSON file: {path}")
        raise UrsaIOException(f"Data loading error on {path}: {e}") from e


def load_and_prepare_targets(file_path: Path) -> dict[str, TargetInfo]:
    """
    Loads a file containing target IDs and SMILES, canonicalizes the SMILES,
    and prepares a dictionary of TargetInfo objects.
    """
    logger.info(f"Loading and preparing targets from {file_path}...")

    try:
        if file_path.suffix == ".csv":
            targets_raw = load_targets_csv(file_path)
        elif file_path.suffix == ".json" or (file_path.suffix == ".gz" and file_path.stem.endswith(".json")):
            targets_raw = load_targets_json(file_path)
        else:
            raise UrsaException(f"Unsupported file format: {file_path}")
    except UrsaIOException:
        # Let IO exceptions propagate with their specific type.
        raise

    prepared_targets: dict[str, TargetInfo] = {}
    for target_id, raw_smiles in targets_raw.items():
        try:
            canon_smiles = canonicalize_smiles(raw_smiles)
            prepared_targets[target_id] = TargetInfo(id=target_id, smiles=canon_smiles)
        except UrsaException as e:
            msg = f"Invalid SMILES for target '{target_id}': {raw_smiles}. Cannot proceed."
            logger.error(msg)
            # **THE FIX IS HERE**: Raise a new exception with the better message.
            raise UrsaException(msg) from e

    logger.info(f"Successfully prepared {len(prepared_targets)} targets.")
    return prepared_targets
