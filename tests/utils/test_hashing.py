import hashlib
from pathlib import Path

import pytest

from ursa.exceptions import UrsaException
from ursa.utils.hashing import generate_molecule_hash, generate_run_hash, get_file_hash


def test_generate_molecule_hash_is_deterministic() -> None:
    """Tests that the same SMILES string always produces the same hash."""
    # Arrange
    smiles1 = "CCO"
    smiles2 = "CCO"

    # Act
    hash1 = generate_molecule_hash(smiles1)
    hash2 = generate_molecule_hash(smiles2)

    # Assert
    assert hash1 == hash2
    assert hash1.startswith("sha256-")


def test_generate_molecule_hash_is_sensitive() -> None:
    """Tests that different SMILES strings produce different hashes."""
    # Arrange
    smiles1 = "CCO"  # Ethanol
    smiles2 = "COC"  # Dimethyl ether

    # Act
    hash1 = generate_molecule_hash(smiles1)
    hash2 = generate_molecule_hash(smiles2)

    # Assert
    assert hash1 != hash2


def test_generate_run_hash_is_deterministic_and_order_invariant() -> None:
    """
    Tests that the run hash is deterministic and invariant to the order
    of file hashes.
    """
    # Arrange
    model_name = "test-model"
    file_hashes_1 = ["hash_a", "hash_b", "hash_c"]
    file_hashes_2 = ["hash_c", "hash_a", "hash_b"]  # Same hashes, different order

    # Act
    run_hash_1 = generate_run_hash(model_name, file_hashes_1)
    run_hash_2 = generate_run_hash(model_name, file_hashes_2)

    # Assert
    assert run_hash_1 == run_hash_2
    assert run_hash_1.startswith("ursa-run-")


def test_generate_run_hash_is_sensitive_to_model_name() -> None:
    """Tests that changing the model name changes the run hash."""
    # Arrange
    model_name_1 = "model-a"
    model_name_2 = "model-b"
    file_hashes = ["hash_a", "hash_b", "hash_c"]

    # Act
    run_hash_1 = generate_run_hash(model_name_1, file_hashes)
    run_hash_2 = generate_run_hash(model_name_2, file_hashes)

    # Assert
    assert run_hash_1 != run_hash_2


def test_get_file_hash_is_correct(tmp_path: Path) -> None:
    """
    Tests that get_file_hash correctly computes the sha256 of a file's content.
    """
    # Arrange
    content = b"ursa major is the best bear"
    expected_hash = hashlib.sha256(content).hexdigest()
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content)

    # Act
    calculated_hash = get_file_hash(file_path)

    # Assert
    assert calculated_hash == expected_hash


def test_get_file_hash_raises_exception_for_missing_file(tmp_path: Path) -> None:
    """Tests that our custom exception is raised if the file does not exist."""
    # Arrange
    non_existent_path = tmp_path / "this_file_does_not_exist.txt"

    # Act / Assert
    with pytest.raises(UrsaException):
        get_file_hash(non_existent_path)
