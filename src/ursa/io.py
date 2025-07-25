import csv
import gzip
import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from ursa.exceptions import UrsaIOException
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
    except (OSError, TypeError) as e:
        # TypeError is caught if data is not serializable.
        logger.error(f"Failed to write or serialize gzipped JSON to {path}: {e}")
        raise UrsaIOException(f"Data saving/serialization error on {path}: {e}") from e


def load_json_gz(path: Path) -> dict[str, Any]:  # <<< CHANGE
    """
    Loads a gzipped JSON file into a Python dictionary.

    This is a low-level loader. It performs no validation beyond ensuring
    the file contains valid JSON.
    """
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            # The type assertion tells mypy we know what we're doing.
            # We expect a dict, but the file could contain anything.
            # The orchestrator MUST handle this responsibly.
            loaded_data = json.load(f)
            if not isinstance(loaded_data, dict):
                raise UrsaIOException(f"Expected a JSON object (dict), but found {type(loaded_data)} in {path}")
            return loaded_data  # <<< FIX: This now returns a dict, satisfying mypy.
    except (OSError, gzip.BadGzipFile, json.JSONDecodeError) as e:
        logger.error(f"Failed to load or parse gzipped JSON file: {path}")
        raise UrsaIOException(f"Data loading error on {path}: {e}") from e


def save_json(data: dict[str, Any], path: Path) -> None:
    # This implementation was already fine. No changes needed.
    """Saves a Python dictionary to a standard, uncompressed JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to write to JSON file: {path}")
        raise UrsaIOException(f"Data saving error on {path}: {e}") from e


def load_csv(path: Path) -> list[dict[str, str]]:
    """
    Loads a CSV file into a list of dictionaries, where each dictionary represents a row
    with column headers as keys.

    The CSV must have a header row. Each row is returned as a dictionary where the keys
    are the column headers and values are strings.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = list(reader)
            if not data:
                logger.warning(f"CSV file {path} is empty")
            return data
    except OSError as e:
        logger.error(f"Failed to read CSV file: {path}")
        raise UrsaIOException(f"Data loading error on {path}: {e}") from e
    except csv.Error as e:
        logger.error(f"Failed to parse CSV file: {path}")
        raise UrsaIOException(f"CSV parsing error on {path}: {e}") from e
