# tests/test_core.py

import json
from pathlib import Path

from pytest_mock import MockerFixture

from ursa.adapters.base_adapter import BaseAdapter
from ursa.core import process_model_run
from ursa.domain.schemas import BenchmarkTree, TargetInfo
from ursa.io import save_json_gz  # <-- Import our helper


def test_process_model_run_happy_path(tmp_path: Path, mocker: MockerFixture, aspirin_target_info: TargetInfo) -> None:
    """
    Tests the full orchestration of process_model_run.
    - Creates fake raw files.
    - Mocks the adapter to return predictable data.
    - Verifies that the correct processed files and manifest are created.
    """
    # 1. ARRANGE
    # --- Filesystem Setup ---
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()

    # --- THE FIX IS HERE ---
    # Create a *real*, valid gzipped JSON file using our own I/O function.
    # This file will contain one target.
    raw_file_content = {
        "aspirin": [{"smiles": "...", "children": []}]  # Content doesn't matter for the adapter mock
    }
    raw_file_path = raw_dir / "target_aspirin.json.gz"
    save_json_gz(raw_file_content, raw_file_path)

    # --- Mocking the Adapter ---
    # (This part was already correct)
    fake_tree = BenchmarkTree.model_validate(
        {
            "target": aspirin_target_info.model_dump(),
            "retrosynthetic_tree": {
                "id": "root",
                "molecule_hash": "hash_aspirin",
                "smiles": aspirin_target_info.smiles,
                "is_starting_material": False,
                "reactions": [
                    {
                        "id": "rxn-root",
                        "reaction_smiles": "A.B>>T",
                        "reactants": [
                            {
                                "id": "root-0",
                                "molecule_hash": "hash_a",
                                "smiles": "A",
                                "is_starting_material": True,
                                "reactions": [],
                            }
                        ],
                    }
                ],
            },
        }
    )
    mock_adapter_instance = mocker.MagicMock(spec=BaseAdapter)
    mock_adapter_instance.adapt.return_value = iter([fake_tree])

    # 2. ACT
    process_model_run(
        model_name="test_model_v1",
        adapter=mock_adapter_instance,
        raw_results_dir=raw_dir,
        processed_dir=processed_dir,
        targets_map={"aspirin": aspirin_target_info},
    )

    # 3. ASSERT
    # --- Verify Adapter Was Called Correctly ---
    mock_adapter_instance.adapt.assert_called_once()
    call_args, _ = mock_adapter_instance.adapt.call_args
    # The data passed to the adapter should be the content from the file
    assert call_args[0] == raw_file_content["aspirin"]
    assert call_args[1] == aspirin_target_info

    # --- Verify Output Files ---
    manifest_files = list(processed_dir.glob("*-manifest.json"))
    assert len(manifest_files) == 1
    manifest_path = manifest_files[0]

    with manifest_path.open("r") as f:
        manifest = json.load(f)

    assert manifest["model_name"] == "test_model_v1"
    assert manifest["results_file"] is not None

    stats = manifest["statistics"]
    assert stats["final_unique_routes_saved"] == 1
    assert stats["num_targets_with_at_least_one_route"] == 1
    assert stats["duplication_factor"] == 1.0

    results_file_path = processed_dir / manifest["results_file"]
    assert results_file_path.exists()


def test_process_model_run_no_files(tmp_path: Path, mocker: MockerFixture) -> None:
    """Tests that the function exits gracefully if no raw files are found."""
    # Arrange
    raw_dir = tmp_path / "raw_empty"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()
    mock_adapter_instance = mocker.MagicMock(spec=BaseAdapter)

    # Act
    process_model_run(
        model_name="test_model_v2",
        adapter=mock_adapter_instance,
        raw_results_dir=raw_dir,
        processed_dir=processed_dir,
        targets_map={},
    )

    # Assert
    # The adapter should never have been called
    mock_adapter_instance.adapt.assert_not_called()
    # No files should have been created in the processed directory
    assert len(list(processed_dir.iterdir())) == 0
