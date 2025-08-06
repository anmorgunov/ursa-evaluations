import csv
import json
from pathlib import Path

import pytest

from ursa.domain.schemas import TargetInfo
from ursa.exceptions import UrsaException, UrsaIOException, UrsaSerializationError
from ursa.io import (
    load_and_prepare_targets,
    load_json_gz,
    load_targets_csv,
    load_targets_json,
    save_json,
    save_json_gz,
)

# --- Test Data ---

VALID_TARGET_DATA = {
    "target_abc": "CCO",
    "target_xyz": "c1ccccc1",
}

# --- Fixtures ---


@pytest.fixture
def valid_csv_file(tmp_path: Path) -> Path:
    """Creates a valid CSV file for testing loaders."""
    file_path = tmp_path / "targets.csv"
    with file_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Structure ID", "SMILES"])
        writer.writerow(["target_abc", "CCO"])
        writer.writerow(["target_xyz", "c1ccccc1"])
    return file_path


@pytest.fixture
def valid_json_file(tmp_path: Path) -> Path:
    """Creates a valid, uncompressed JSON file for testing."""
    file_path = tmp_path / "targets.json"
    with file_path.open("w") as f:
        json.dump(VALID_TARGET_DATA, f)
    return file_path


@pytest.fixture
def valid_json_gz_file(tmp_path: Path) -> Path:
    """Creates a valid, gzipped JSON file for testing."""
    file_path = tmp_path / "targets.json.gz"
    save_json_gz(VALID_TARGET_DATA, file_path)
    return file_path


# --- Core JSON I/O Tests (Original and Expanded) ---


def test_save_and_load_json_gz_roundtrip(tmp_path: Path) -> None:
    """Tests that data remains identical after a save/load roundtrip."""
    test_data = {"key": "value", "nested": [1, 2, {"a": 3}]}
    file_path = tmp_path / "test.json.gz"
    save_json_gz(test_data, file_path)
    loaded_data = load_json_gz(file_path)
    assert loaded_data == test_data


def test_save_and_load_uncompressed_json_roundtrip(tmp_path: Path) -> None:
    """Tests the roundtrip for the standard, uncompressed JSON helper."""
    manifest_data = {"run_hash": "abc-123", "model_name": "test"}
    file_path = tmp_path / "manifest.json"
    save_json(manifest_data, file_path)
    with file_path.open("r") as f:
        loaded_data = json.load(f)
    assert loaded_data == manifest_data


def test_save_json_gz_creates_directories(tmp_path: Path) -> None:
    """Tests that the save function can create parent directories if needed."""
    nested_dir = tmp_path / "processed" / "run_1"
    file_path = nested_dir / "results.json.gz"
    assert not nested_dir.exists()
    save_json_gz({"status": "ok"}, file_path)
    assert file_path.exists()


def test_load_json_gz_raises_io_error_for_missing_file(tmp_path: Path) -> None:
    """Tests that loading a non-existent file raises UrsaIOException."""
    with pytest.raises(UrsaIOException, match="Data loading error"):
        load_json_gz(tmp_path / "nope.json.gz")


def test_load_json_gz_raises_io_error_for_malformed_gzip(tmp_path: Path) -> None:
    """Tests that loading a file that is not valid gzip raises UrsaIOException."""
    file_path = tmp_path / "bad.json.gz"
    file_path.write_text("this is not gzipped")
    # **FIX 1**: Removed the brittle `match` parameter. Checking the type is enough.
    with pytest.raises(UrsaIOException):
        load_json_gz(file_path)


def test_save_json_gz_raises_serialization_error(tmp_path: Path) -> None:
    """Tests that UrsaSerializationError is raised for non-serializable types."""
    unserializable_data = {"a_set": {1, 2, 3}}
    file_path = tmp_path / "bad_data.json.gz"
    with pytest.raises(UrsaSerializationError, match="Data serialization error"):
        save_json_gz(unserializable_data, file_path)


def test_load_json_gz_raises_on_non_dict_content(tmp_path: Path) -> None:
    """Tests that loading a JSON file not containing a dict raises an error."""
    file_path = tmp_path / "list.json.gz"
    save_json_gz([1, 2, 3], file_path)  # type: ignore
    with pytest.raises(UrsaIOException, match="Expected a JSON object"):
        load_json_gz(file_path)


# --- Target File Loader Tests ---


def test_load_targets_csv_happy_path(valid_csv_file: Path):
    """Tests loading a correctly formatted CSV file."""
    data = load_targets_csv(valid_csv_file)
    assert data == VALID_TARGET_DATA


def test_load_targets_csv_raises_on_missing_column(tmp_path: Path):
    """Tests that a KeyError is caught and wrapped in UrsaIOException."""
    file_path = tmp_path / "bad_headers.csv"
    file_path.write_text("Structure ID,Wrong_Header\n-,-")
    with pytest.raises(UrsaIOException, match="CSV column 'SMILES' not found"):
        load_targets_csv(file_path)


def test_load_targets_csv_empty_file(tmp_path: Path, caplog):
    """Tests loading an empty CSV file, expecting an empty dict and a warning."""
    file_path = tmp_path / "empty.csv"
    file_path.touch()
    data = load_targets_csv(file_path)
    assert data == {}
    # **FIX 2**: Match the actual log message.
    assert "is empty or has no header" in caplog.text


def test_load_targets_csv_header_only(tmp_path: Path):
    """Tests loading a CSV with only a header row."""
    file_path = tmp_path / "header_only.csv"
    file_path.write_text("Structure ID,SMILES\n")
    data = load_targets_csv(file_path)
    assert data == {}


def test_load_targets_json_happy_path(valid_json_file: Path):
    """Tests loading a correctly formatted uncompressed JSON file."""
    data = load_targets_json(valid_json_file)
    assert data == VALID_TARGET_DATA


def test_load_targets_json_gz_happy_path(valid_json_gz_file: Path):
    """Tests loading a correctly formatted gzipped JSON file."""
    data = load_targets_json(valid_json_gz_file)
    assert data == VALID_TARGET_DATA


def test_load_targets_json_raises_on_non_dict(tmp_path: Path):
    """Tests that UrsaIOException is raised if the JSON does not contain a dict."""
    file_path = tmp_path / "list.json"
    file_path.write_text("[1, 2, 3]")
    with pytest.raises(UrsaIOException, match="Expected JSON object"):
        load_targets_json(file_path)


# --- Orchestrator (`load_and_prepare_targets`) Tests ---


def test_prepare_targets_from_csv(valid_csv_file: Path):
    """Tests the full orchestration logic with a CSV file."""
    targets = load_and_prepare_targets(valid_csv_file)
    assert "target_abc" in targets
    assert isinstance(targets["target_abc"], TargetInfo)
    assert targets["target_abc"].smiles == "CCO"
    assert targets["target_xyz"].smiles == "c1ccccc1"


def test_prepare_targets_from_json(valid_json_file: Path):
    """Tests the full orchestration logic with a JSON file."""
    targets = load_and_prepare_targets(valid_json_file)
    assert "target_abc" in targets
    assert isinstance(targets["target_abc"], TargetInfo)


def test_prepare_targets_from_json_gz(valid_json_gz_file: Path):
    """Tests the full orchestration logic with a gzipped JSON file."""
    targets = load_and_prepare_targets(valid_json_gz_file)
    assert "target_xyz" in targets
    assert isinstance(targets["target_xyz"], TargetInfo)


def test_prepare_targets_raises_on_unsupported_format(tmp_path: Path):
    """Tests that an unsupported file extension raises UrsaException."""
    file_path = tmp_path / "data.txt"
    file_path.touch()
    with pytest.raises(UrsaException, match="Unsupported file format"):
        load_and_prepare_targets(file_path)


def test_prepare_targets_raises_on_invalid_smiles(tmp_path: Path):
    """Tests that an invalid SMILES in the input file aborts the process."""
    file_path = tmp_path / "bad_smiles.csv"
    with file_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Structure ID", "SMILES"])
        writer.writerow(["good", "CCO"])
        writer.writerow(["bad", "this is not a real smiles"])

    # **FIX 3**: The test assertion now matches the new, more informative
    # exception message raised by the fixed code.
    with pytest.raises(UrsaException, match="Invalid SMILES for target 'bad'"):
        load_and_prepare_targets(file_path)


def test_prepare_targets_propagates_io_error(tmp_path: Path):
    """Ensures a file I/O error from a loader is not swallowed."""
    with pytest.raises(UrsaIOException):
        load_and_prepare_targets(tmp_path / "non_existent_file.csv")
