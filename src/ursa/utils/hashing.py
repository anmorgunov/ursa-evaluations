import hashlib
from pathlib import Path

from ursa.exceptions import UrsaException
from ursa.typing import SmilesStr
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


def generate_molecule_hash(smiles: SmilesStr) -> str:
    """
    Generates a deterministic, content-based hash for a canonical SMILES string.

    Args:
        smiles: The canonical SMILES string.

    Returns:
        A 'sha256:' prefixed hex digest of the SMILES string.
    """
    # we encode to bytes before hashing
    smiles_bytes = smiles.encode("utf-8")
    hasher = hashlib.sha256(smiles_bytes)
    return f"sha256-{hasher.hexdigest()}"


def generate_run_hash(model_name: str, file_hashes: list[str]) -> str:
    """
    Generates a deterministic ID for a model run based on the model's name
    and the content of all its output files.

    Args:
        model_name: The name of the model being processed.
        file_hashes: A sorted list of the sha256 hashes of all input files.

    Returns:
        A 'ursa-run-' prefixed sha256 hex digest.
    """
    # ensure consistent ordering
    sorted_hashes = sorted(file_hashes)
    # create a single string that uniquely represents the run
    run_signature = model_name + "".join(sorted_hashes)
    run_bytes = run_signature.encode("utf-8")
    hasher = hashlib.sha256(run_bytes)
    return f"ursa-run-{hasher.hexdigest()}"
