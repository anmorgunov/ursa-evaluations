# src/ursa/io.py

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ursa.exceptions import UrsaException
from ursa.utils.logging import logger


def get_file_hash(path: Path) -> str:
    """Computes the sha256 hash of a file's content."""
    try:
        with path.open("rb") as f:
            file_bytes = f.read()
            return hashlib.sha256(file_bytes).hexdigest()
    except OSError as e:
        logger.error(f"Could not read file for hashing: {path}")
        raise UrsaException(f"File I/O error on {path}: {e}") from e


def load_json_gz(path: Path) -> dict[str, Any]:
    """Loads a gzipped JSON file into a Python dictionary."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, gzip.BadGzipFile, json.JSONDecodeError) as e:
        logger.error(f"Failed to load or parse gzipped JSON file: {path}")
        raise UrsaException(f"Data loading error on {path}: {e}") from e


def save_json_gz(data: dict[str, Any], path: Path) -> None:
    """Saves a Python dictionary to a gzipped JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        json_str = json.dumps(data, indent=2)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(json_str)
    except OSError as e:
        logger.error(f"Failed to write to gzipped JSON file: {path}")
        raise UrsaException(f"Data saving error on {path}: {e}") from e


def save_pydantic_model_gz(model: BaseModel, path: Path) -> None:
    """Serializes a Pydantic model and saves it to a gzipped JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # .model_dump_json is the canonical way to serialize pydantic models
        json_str = model.model_dump_json(indent=2)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(json_str)
    except OSError as e:
        logger.error(f"Failed to write Pydantic model to gzipped JSON file: {path}")
        raise UrsaException(f"Data saving error on {path}: {e}") from e
