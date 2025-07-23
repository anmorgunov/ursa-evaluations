# tests/adapters/test_dms_adapter.py

import pytest

from ursa.adapters.dms_adapter import DMSAdapter
from ursa.domain.chem import canonicalize_smiles
from ursa.domain.schemas import BenchmarkTree, DMSTree, TargetInfo
from ursa.exceptions import AdapterLogicError


def test_adapt_happy_path_aspirin(
    dms_adapter: DMSAdapter,
    raw_dms_aspirin_data: dict,
    aspirin_target_info: TargetInfo,
) -> None:
    """Tests a simple, valid 1-step transformation."""
    # Act
    # The adapt method is a generator, so we consume it into a list
    results = list(dms_adapter.adapt(raw_dms_aspirin_data, aspirin_target_info))

    # Assert
    assert len(results) == 1
    tree = results[0]
    assert isinstance(tree, BenchmarkTree)

    # Check root node
    root = tree.retrosynthetic_tree
    assert root.smiles == aspirin_target_info.smiles
    assert root.is_starting_material is False
    assert len(root.reactions) == 1

    # Check reaction
    reaction = root.reactions[0]
    assert len(reaction.reactants) == 2
    reactant_smiles = {r.smiles for r in reaction.reactants}
    expected_reactant_smiles = {
        canonicalize_smiles("OC1=CC=CC=C1C(=O)O"),
        canonicalize_smiles("CC(=O)Cl"),
    }
    assert reactant_smiles == expected_reactant_smiles

    # Check leaf nodes
    for reactant in reaction.reactants:
        assert reactant.is_starting_material is True
        assert len(reactant.reactions) == 0


def test_adapt_yields_nothing_for_invalid_smiles(
    dms_adapter: DMSAdapter,
    raw_dms_invalid_smiles_data: dict,
    aspirin_target_info: TargetInfo,
) -> None:
    """
    Tests that if a route contains an invalid SMILES, the adapt generator
    handles the exception internally and simply yields nothing for that route.
    """
    # Act
    results = list(dms_adapter.adapt(raw_dms_invalid_smiles_data, aspirin_target_info))

    # Assert
    assert len(results) == 0


def test_transform_raises_adapter_logic_error_on_mismatch(
    dms_adapter: DMSAdapter,
    raw_dms_aspirin_data: dict,
    vonoprazan_target_info: TargetInfo,  # Mismatched target
) -> None:
    """
    Tests that a direct call to the private _transform method raises an
    AdapterLogicError if the transformed root SMILES does not match the
    canonical target SMILES.
    """
    # Arrange
    single_route_data = raw_dms_aspirin_data[0]
    dms_tree = DMSTree.model_validate(single_route_data)

    # Act / Assert
    with pytest.raises(AdapterLogicError, match="Mismatched SMILES"):
        # We test the private method here to isolate this specific logic check
        dms_adapter._transform(dms_tree, vonoprazan_target_info)


def test_adapter_generates_correct_ids(
    dms_adapter: DMSAdapter,
    raw_dms_vonoprazan_data: dict,
    vonoprazan_target_info: TargetInfo,
) -> None:
    """
    Tests that the adapter correctly generates path-dependent IDs for a
    multi-step synthesis.
    """
    # Act
    results = list(dms_adapter.adapt(raw_dms_vonoprazan_data, vonoprazan_target_info))
    tree = results[0]
    root = tree.retrosynthetic_tree

    # Assert IDs
    assert root.id == "ursa-mol-root"
    assert root.reactions[0].id == "ursa-rxn-root"

    # First level of reactants
    aldehyde_node = root.reactions[0].reactants[0]
    methylamine_node = root.reactions[0].reactants[1]
    assert aldehyde_node.id == "ursa-mol-root-0"
    assert methylamine_node.id == "ursa-mol-root-1"

    # Second level of reactants (children of the aldehyde)
    assert aldehyde_node.reactions[0].id == "ursa-rxn-root-0"
    pyrrole_node = aldehyde_node.reactions[0].reactants[0]
    sulfonyl_chloride_node = aldehyde_node.reactions[0].reactants[1]
    assert pyrrole_node.id == "ursa-mol-root-0-0"
    assert sulfonyl_chloride_node.id == "ursa-mol-root-0-1"
