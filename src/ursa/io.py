import gzip
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ursa.exceptions import UrsaException, UrsaIOException, UrsaSerializationError
from ursa.utils.logging import logger


def save_json(data: dict[str, Any], path: Path) -> None:
    """Saves a Python dictionary to a standard, uncompressed JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to write to JSON file: {path}")
        raise UrsaException(f"Data saving error on {path}: {e}") from e


def load_json_gz(path: Path) -> dict[str, Any]:
    """Loads a gzipped JSON file into a Python dictionary."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, gzip.BadGzipFile, json.JSONDecodeError) as e:
        logger.error(f"Failed to load or parse gzipped JSON file: {path}")
        raise UrsaException(f"Data loading error on {path}: {e}") from e


def _pydantic_encoder(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    # Raise our specific exception instead of a generic TypeError
    raise UrsaSerializationError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def save_json_gz(data: dict[str, Any], path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        json_str = json.dumps(data, indent=2, default=_pydantic_encoder)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(json_str)
    except UrsaSerializationError as e:
        # Re-raise the specific error so it's not caught by the generic handler
        raise e
    except Exception as e:
        # Wrap any other error (IOError, etc.) in our custom IO exception
        raise UrsaIOException(f"Failed to write or serialize gzipped JSON to {path}: {e}") from e


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
