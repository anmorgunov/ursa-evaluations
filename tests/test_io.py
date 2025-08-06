"""Tests for the ursa.io module.

This module contains unit tests for all public I/O utilities, including
JSON (gzipped and uncompressed), CSV, and SMILES canonicalization.
"""

import csv
import json
import pathlib
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from ursa.exceptions import UrsaException, UrsaIOException, UrsaSerializationError
from ursa.io import (
    load_and_prepare_targets,
    load_json_gz,
    load_targets_csv,
    load_targets_json,
    save_json,
    save_json_gz,
)

VALID_TARGET_DATA = {"target_abc": "CCO", "target_xyz": "c1ccccc1"}


@pytest.fixture
def valid_csv_file(tmp_path: Path) -> Path:
    """Create a CSV file with two valid target rows."""
    file_path = tmp_path / "targets.csv"
    with file_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Structure ID", "SMILES"])
        writer.writerow(["target_abc", "CCO"])
        writer.writerow(["target_xyz", "c1ccccc1"])
    return file_path


@pytest.fixture
def valid_json_file(tmp_path: Path) -> Path:
    """Create an uncompressed JSON file with two valid targets."""
    file_path = tmp_path / "targets.json"
    file_path.write_text(json.dumps(VALID_TARGET_DATA))
    return file_path


@pytest.fixture
def valid_json_gz_file(tmp_path: Path) -> Path:
    """Create a gzipped JSON file with two valid targets."""
    file_path = tmp_path / "targets.json.gz"
    save_json_gz(VALID_TARGET_DATA, file_path)
    return file_path


def test_save_and_load_json_gz_roundtrip(tmp_path: Path) -> None:
    """Ensure gzipped JSON round-trip preserves nested structures."""
    data = {"key": "value", "nested": [1, 2, {"a": 3}]}
    file_path = tmp_path / "test.json.gz"
    save_json_gz(data, file_path)
    assert load_json_gz(file_path) == data


def test_save_and_load_uncompressed_json_roundtrip(tmp_path: Path) -> None:
    """Ensure uncompressed JSON round-trip preserves manifest data."""
    manifest = {"run_hash": "abc-123", "model_name": "test"}
    file_path = tmp_path / "manifest.json"
    save_json(manifest, file_path)
    assert json.loads(file_path.read_text()) == manifest


def test_save_json_gz_creates_directories(tmp_path: Path) -> None:
    """Verify that save_json_gz creates missing parent directories."""
    file_path = tmp_path / "processed" / "run_1" / "results.json.gz"
    save_json_gz({"status": "ok"}, file_path)
    assert file_path.exists()


def test_load_json_gz_raises_io_error_for_missing_file(tmp_path: Path) -> None:
    """Missing files raise UrsaIOException when loading gzipped JSON."""
    with pytest.raises(UrsaIOException):
        load_json_gz(tmp_path / "nope.json.gz")


def test_load_json_gz_raises_io_error_for_malformed_gzip(tmp_path: Path) -> None:
    """Malformed gzip content raises UrsaIOException."""
    file_path = tmp_path / "bad.json.gz"
    file_path.write_text("not gzipped")
    with pytest.raises(UrsaIOException):
        load_json_gz(file_path)


def test_save_json_gz_raises_serialization_error(tmp_path: Path) -> None:
    """Non-serializable objects raise UrsaSerializationError."""
    with pytest.raises(UrsaSerializationError):
        save_json_gz({"a_set": {1, 2, 3}}, tmp_path / "bad.json.gz")


def test_load_json_gz_raises_on_non_dict_content(tmp_path: Path) -> None:
    """Non-dict content raises UrsaIOException when loading gzipped JSON."""
    file_path = tmp_path / "list.json.gz"
    save_json_gz([1, 2, 3], file_path)  # type: ignore
    with pytest.raises(UrsaIOException):
        load_json_gz(file_path)


def test_load_targets_csv_happy_path(valid_csv_file: Path):
    """CSV loader returns expected dict for well-formed input."""
    assert load_targets_csv(valid_csv_file) == VALID_TARGET_DATA


def test_load_targets_csv_raises_on_missing_column(tmp_path: Path):
    """CSV loader raises when required columns are absent."""
    file_path = tmp_path / "bad_headers.csv"
    file_path.write_text("Structure ID,Wrong_Header\n-,-")
    with pytest.raises(UrsaIOException):
        load_targets_csv(file_path)


def test_load_targets_csv_empty_file(tmp_path: Path, caplog):
    """Empty CSV files return an empty dict and log a warning."""
    file_path = tmp_path / "empty.csv"
    file_path.touch()
    assert load_targets_csv(file_path) == {}
    assert "is empty or has no header" in caplog.text


def test_load_targets_csv_header_only(tmp_path: Path):
    """CSV files with only headers return an empty dict."""
    file_path = tmp_path / "header_only.csv"
    file_path.write_text("Structure ID,SMILES\n")
    assert load_targets_csv(file_path) == {}


def test_load_targets_json_happy_path(valid_json_file: Path):
    """JSON loader returns expected dict for well-formed input."""
    assert load_targets_json(valid_json_file) == VALID_TARGET_DATA


def test_load_targets_json_gz_happy_path(valid_json_gz_file: Path):
    """Gzipped JSON loader returns expected dict for well-formed input."""
    assert load_targets_json(valid_json_gz_file) == VALID_TARGET_DATA


def test_load_targets_json_raises_on_non_dict(tmp_path: Path):
    """Non-dict JSON content raises UrsaIOException."""
    file_path = tmp_path / "list.json"
    file_path.write_text("[1, 2, 3]")
    with pytest.raises(UrsaIOException):
        load_targets_json(file_path)


def test_prepare_targets_from_csv(valid_csv_file: Path):
    """Target preparation from CSV yields canonical SMILES."""
    targets = load_and_prepare_targets(valid_csv_file)
    assert targets["target_abc"].smiles == "CCO"
    assert targets["target_xyz"].smiles == "c1ccccc1"


def test_prepare_targets_from_json(valid_json_file: Path):
    """Target preparation from JSON yields expected target IDs."""
    targets = load_and_prepare_targets(valid_json_file)
    assert "target_abc" in targets


def test_prepare_targets_from_json_gz(valid_json_gz_file: Path):
    """Target preparation from gzipped JSON yields expected target IDs."""
    targets = load_and_prepare_targets(valid_json_gz_file)
    assert "target_xyz" in targets


def test_prepare_targets_raises_on_unsupported_format(tmp_path: Path):
    """Unsupported file extensions raise UrsaException."""
    file_path = tmp_path / "data.txt"
    file_path.touch()
    with pytest.raises(UrsaException):
        load_and_prepare_targets(file_path)


def test_prepare_targets_raises_on_invalid_smiles(tmp_path: Path):
    """Invalid SMILES strings raise UrsaException with a clear message."""
    file_path = tmp_path / "bad_smiles.csv"
    with file_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Structure ID", "SMILES"])
        writer.writerow(["good", "CCO"])
        writer.writerow(["bad", "invalid"])
    with pytest.raises(UrsaException):
        load_and_prepare_targets(file_path)


def test_prepare_targets_propagates_io_error(tmp_path: Path):
    """Non-existent files raise UrsaIOException."""
    with pytest.raises(UrsaIOException):
        load_and_prepare_targets(tmp_path / "non_existent_file.csv")


def test_save_json_gz_raises_io_error_on_write_failure(tmp_path: Path, monkeypatch: MonkeyPatch):
    """Write failures during save_json_gz raise UrsaIOException."""
    file_path = tmp_path / "protected" / "data.json.gz"

    def mock_mkdir(*_, **__):
        raise OSError("Permission denied")

    monkeypatch.setattr(pathlib.Path, "mkdir", mock_mkdir)
    with pytest.raises(UrsaIOException):
        save_json_gz({"key": "value"}, file_path)


def test_save_json_raises_io_error_on_write_failure(tmp_path: Path, monkeypatch: MonkeyPatch):
    """Write failures during save_json raise UrsaIOException."""
    file_path = tmp_path / "protected" / "data.json"

    def mock_mkdir(*_, **__):
        raise OSError("Disk is full")

    monkeypatch.setattr(pathlib.Path, "mkdir", mock_mkdir)
    with pytest.raises(UrsaIOException):
        save_json({"key": "value"}, file_path)


def test_load_targets_csv_raises_io_error_on_read_failure(monkeypatch: MonkeyPatch):
    """Read failures during CSV loading raise UrsaIOException."""

    def mock_open(*_, **__):
        raise OSError("Cannot read file")

    monkeypatch.setattr(Path, "open", mock_open)
    with pytest.raises(UrsaIOException):
        load_targets_csv(Path("/fake/path.csv"))


def test_load_targets_json_with_empty_object(tmp_path: Path, caplog):
    """Empty JSON objects return an empty dict and log a warning."""
    file_path = tmp_path / "empty.json"
    file_path.write_text("{}")
    assert load_targets_json(file_path) == {}
    assert "JSON file" in caplog.text and "is empty" in caplog.text


def test_load_targets_json_raises_on_malformed_json(tmp_path: Path):
    file_path = tmp_path / "malformed.json"
    file_path.write_text("{'key': 'invalid'}")
    with pytest.raises(UrsaIOException):
        load_targets_json(file_path)
