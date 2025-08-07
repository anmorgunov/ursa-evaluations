import pytest

from ursa.adapters.aizynth_adapter import AizynthAdapter
from ursa.domain.schemas import TargetInfo
from ursa.typing import SmilesStr


@pytest.fixture
def aizynth_raw_output() -> list[dict]:
    # fmt:off
    return [{"type": "mol", "smiles": "Cc1cccc(C)c1N(CC(=O)Nc1ccc(-c2ncon2)cc1)C(=O)C1CCS(=O)(=O)CC1",
            "children": [{"type": "reaction", "smiles": "[C:1]...>>Cl[C:1]...", 
                          "children": [{"type": "mol", "smiles": "Nc1ccc(-c2ncon2)cc1", "in_stock": True},
                                       {"type": "mol", "smiles": "Cc1cccc(C)c1N(CC(=O)Cl)C(=O)C1CCS(=O)(=O)CC1", "in_stock": False,
                                        "children": [{"type": "reaction", "smiles": "[C:1]...>>I[C:1]...",
                                                       "children": [{"type": "mol", "smiles": "O=C(Cl)CI", "in_stock": True},
                                                                    {"type": "mol", "smiles": "Cc1cccc(C)c1NC(=O)C1CCS(=O)(=O)CC1", "in_stock": False,
                                                                        "children": [{"type": "reaction", "smiles": "[C:1]...>>CO[C:1]...",
                                                                                      "children": [{"type": "mol", "smiles": "Cc1cccc(C)c1N", "in_stock": True},
                                                                                                   {"type": "mol", "smiles": "COC(=O)C1CCS(=O)(=O)CC1", "in_stock": True},
                                                                                    ]}]
                                                                    }]
                                                    }]
                                }]
                        }]
            }]


# fmt:on


@pytest.fixture
def target_info() -> TargetInfo:
    """
    FIXED: The SMILES string now matches the one RDKit produces, resolving the mismatch.
    """
    return TargetInfo(
        smiles=SmilesStr("Cc1cccc(C)c1N(CC(=O)Nc1ccc(-c2ncon2)cc1)C(=O)C1CCS(=O)(=O)CC1"),
        id="test_target_1",
    )


def test_aizynth_adapter_instantiation():
    """Tests that the adapter can be instantiated."""
    adapter = AizynthAdapter()
    assert isinstance(adapter, AizynthAdapter)


def test_successful_transformation(aizynth_raw_output, target_info):
    """Tests a full, successful transformation of a valid aizynth route."""
    adapter = AizynthAdapter()
    results = list(adapter.adapt(aizynth_raw_output, target_info))

    assert len(results) == 1
    tree = results[0]

    assert tree.target == target_info
    root_node = tree.retrosynthetic_tree
    assert root_node.smiles == target_info.smiles
    assert not root_node.is_starting_material
    assert len(root_node.reactions) == 1

    # check first reaction
    rxn1 = root_node.reactions[0]
    assert len(rxn1.reactants) == 2
    # Sort reactants by smiles to ensure consistent ordering for tests
    sorted_reactants = sorted(rxn1.reactants, key=lambda r: r.smiles)
    reactant1a, reactant1b = sorted_reactants

    # check one of the branches to see recursion is working
    assert reactant1a.smiles == "Cc1cccc(C)c1N(CC(=O)Cl)C(=O)C1CCS(=O)(=O)CC1"
    assert not reactant1a.is_starting_material
    assert len(reactant1a.reactions) == 1

    assert reactant1b.smiles == "Nc1ccc(-c2ncon2)cc1"
    assert reactant1b.is_starting_material
    assert not reactant1b.reactions

    # check reaction smiles generation
    expected_rxn1_smiles = "Cc1cccc(C)c1N(CC(=O)Cl)C(=O)C1CCS(=O)(=O)CC1.Nc1ccc(-c2ncon2)cc1>>Cc1cccc(C)c1N(CC(=O)Nc1ccc(-c2ncon2)cc1)C(=O)C1CCS(=O)(=O)CC1"
    assert rxn1.reaction_smiles == expected_rxn1_smiles


def test_adapter_handles_malformed_input(target_info, caplog):
    """Tests that the adapter logs a warning and returns no results for bad data."""
    malformed_data = [{"type": "mol", "not_a_smiles_field": "foo"}]
    adapter = AizynthAdapter()
    results = list(adapter.adapt(malformed_data, target_info))

    assert len(results) == 0
    assert "failed AiZynth schema validation" in caplog.text


def test_adapter_handles_invalid_smiles_in_tree(aizynth_raw_output, target_info, caplog):
    """An invalid smiles deep in the tree should cause that route to fail, but not crash."""
    aizynth_raw_output[0]["children"][0]["children"][0]["smiles"] = "invalid"
    adapter = AizynthAdapter()
    results = list(adapter.adapt(aizynth_raw_output, target_info))

    assert len(results) == 0
    assert "failed transformation" in caplog.text
    assert "Invalid SMILES string" in caplog.text


def test_adapter_handles_mismatched_target_smiles(aizynth_raw_output, caplog):
    """If the transformed root SMILES doesn't match the target, it's a logic error."""
    mismatched_target_info = TargetInfo(smiles=SmilesStr("CC"), id="test_target_1")
    adapter = AizynthAdapter()
    results = list(adapter.adapt(aizynth_raw_output, mismatched_target_info))

    assert len(results) == 0
    # FIXED: The assertion now correctly checks for the logged error message.
    assert "Mismatched SMILES for target" in caplog.text


def test_adapter_handles_broken_bipartite_graph(aizynth_raw_output, target_info, caplog):
    """Test that a mol node having a mol child raises a logic error."""
    # Sabotage the graph: make a molecule a child of a molecule
    aizynth_raw_output[0]["children"][0] = {"type": "mol", "smiles": "CC"}
    adapter = AizynthAdapter()
    results = list(adapter.adapt(aizynth_raw_output, target_info))

    assert len(results) == 0
    assert "Child of molecule node was not a reaction node" in caplog.text
