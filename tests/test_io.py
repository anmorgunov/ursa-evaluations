from pathlib import Path

import pytest

from ursa.exceptions import UrsaIOException
from ursa.io import load_json_gz, save_json, save_json_gz


def test_save_and_load_json_gz_roundtrip(tmp_path: Path) -> None:
    """
    Tests that saving a dictionary to a gzipped JSON and loading it back
    results in the original data.
    """
    # Arrange
    test_data = {
        "model": "ursa_prime",
        "parameters": {"layers": 12, "heads": 8},
        "results": [
            {"smiles": "CCO", "score": 0.9},
            {"smiles": "c1ccccc1", "score": 0.8},
        ],
    }
    file_path = tmp_path / "test_output.json.gz"

    # Act
    save_json_gz(test_data, file_path)
    loaded_data = load_json_gz(file_path)

    # Assert
    assert loaded_data == test_data


def test_load_json_gz_raises_io_error_for_missing_file(tmp_path: Path) -> None:
    """Tests that loading a non-existent file raises our custom IO exception."""
    # Arrange
    non_existent_file = tmp_path / "this_does_not_exist.json.gz"

    # Act / Assert
    with pytest.raises(UrsaIOException, match="Data loading error"):
        load_json_gz(non_existent_file)


def test_save_json_gz_creates_directories(tmp_path: Path) -> None:
    """Tests that the save function can create parent directories if needed."""
    # Arrange
    nested_dir = tmp_path / "processed" / "run_hash_123"
    file_path = nested_dir / "results.json.gz"
    test_data = {"status": "ok"}

    # Pre-condition check
    assert not nested_dir.exists()

    # Act
    save_json_gz(test_data, file_path)

    # Assert
    assert nested_dir.exists()
    assert file_path.exists()


def test_load_json_gz_raises_io_error_for_malformed_file(tmp_path: Path) -> None:
    """
    Tests that loading a file that is not valid gzipped JSON raises
    our custom IO exception.
    """
    # Arrange
    file_path = tmp_path / "bad_file.json.gz"
    file_path.write_text("this is not json")

    # Act / Assert
    with pytest.raises(UrsaIOException):
        load_json_gz(file_path)


def test_save_and_load_uncompressed_json(tmp_path: Path) -> None:
    """Tests the roundtrip for the standard, uncompressed JSON helper."""
    # Arrange
    manifest_data = {"run_hash": "abc-123", "model_name": "test"}
    file_path = tmp_path / "manifest.json"

    # Act
    save_json(manifest_data, file_path)
    with file_path.open("r") as f:
        import json

        loaded_data = json.load(f)

    # Assert
    assert loaded_data == manifest_data
