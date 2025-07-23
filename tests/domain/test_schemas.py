import pytest
from pydantic import ValidationError

from ursa.domain.schemas import (
    BenchmarkTree,
    DMSTree,
    MoleculeNode,
    ReactionNode,
    TargetInfo,
)


def test_dms_tree_parses_valid_data(single_dms_aspirin_tree_data: dict) -> None:
    """Tests that the raw input schema can parse valid hierarchical data."""
    # Act
    validated_tree = DMSTree.model_validate(single_dms_aspirin_tree_data)

    # Assert
    assert validated_tree.smiles == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert len(validated_tree.children) == 2
    assert validated_tree.children[0].smiles == "OC1=CC=CC=C1C(=O)O"
    assert len(validated_tree.children[0].children) == 0


def test_molecule_node_validator_fails_on_sm_with_reactions() -> None:
    """
    Tests that the pydantic validator raises an error if a node is marked
    as a starting material but also has parent reactions.
    """
    # Act / Assert
    with pytest.raises(ValidationError, match="is a starting material but has 1 parent reactions"):
        MoleculeNode(
            id="test-mol-0",
            molecule_hash="hash1",
            smiles="CCO",
            is_starting_material=True,  # Contradiction
            reactions=[
                ReactionNode(
                    id="test-rxn-0",
                    reaction_smiles="CC>>CCO",
                    reactants=[],
                )
            ],
        )


def test_molecule_node_validator_fails_on_intermediate_without_reactions() -> None:
    """
    Tests that the validator raises an error if a node is an intermediate
    but has no parent reaction.
    """
    # Act / Assert
    with pytest.raises(ValidationError, match="is an intermediate but has no parent reaction"):
        MoleculeNode(
            id="test-mol-0",
            molecule_hash="hash1",
            smiles="CCO",
            is_starting_material=False,  # Contradiction
            reactions=[],
        )


def test_molecule_node_validator_fails_on_intermediate_with_multiple_reactions() -> None:
    """
    Tests that the validator raises an error if a node is an intermediate
    and has more than one reaction (i.e., it's a DAG, not a tree).
    """
    # Act / Assert
    with pytest.raises(ValidationError, match="is part of a DAG"):
        MoleculeNode(
            id="test-mol-0",
            molecule_hash="hash1",
            smiles="CCO",
            is_starting_material=False,
            reactions=[
                ReactionNode(id="rxn1", reaction_smiles="C.C>>CCO", reactants=[]),
                ReactionNode(id="rxn2", reaction_smiles="CC=O.[H][H]>>CCO", reactants=[]),
            ],
        )


def test_benchmark_tree_parses_valid_structure(aspirin_target_info: TargetInfo) -> None:
    """Tests that a fully-formed, valid benchmark tree object can be created."""
    # Arrange: Manually construct a valid, simple tree
    salicylic_acid = MoleculeNode(
        id="root-0",
        molecule_hash="hash_sa",
        smiles="OC1=CC=CC=C1C(=O)O",
        is_starting_material=True,
        reactions=[],
    )
    acetyl_chloride = MoleculeNode(
        id="root-1",
        molecule_hash="hash_ac",
        smiles="CC(=O)Cl",
        is_starting_material=True,
        reactions=[],
    )

    aspirin_reaction = ReactionNode(
        id="rxn-root",
        reaction_smiles=f"{salicylic_acid.smiles}.{acetyl_chloride.smiles}>>{aspirin_target_info.smiles}",
        reactants=[salicylic_acid, acetyl_chloride],
    )

    aspirin_tree_root = MoleculeNode(
        id="root",
        molecule_hash="hash_aspirin",
        smiles=aspirin_target_info.smiles,
        is_starting_material=False,
        reactions=[aspirin_reaction],
    )

    # Act
    # This should not raise any errors
    benchmark_tree = BenchmarkTree(
        target=aspirin_target_info,
        retrosynthetic_tree=aspirin_tree_root,
    )

    # Assert
    assert benchmark_tree.target.id == "aspirin"
    assert benchmark_tree.retrosynthetic_tree.smiles == aspirin_target_info.smiles
    assert len(benchmark_tree.retrosynthetic_tree.reactions) == 1
    assert len(benchmark_tree.retrosynthetic_tree.reactions[0].reactants) == 2
