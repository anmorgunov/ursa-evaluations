# tests/test_tree.py

from ursa.domain.schemas import BenchmarkTree, MoleculeNode, ReactionNode, TargetInfo
from ursa.domain.tree import deduplicate_routes
from ursa.utils.hashing import generate_molecule_hash


def _build_simple_tree(target_smiles: str, reactant_smiles_list: list[str]) -> BenchmarkTree:
    """A helper function to quickly build a 1-step BenchmarkTree for testing."""
    target_info = TargetInfo(id=target_smiles, smiles=target_smiles)
    reactants = []
    for i, smiles in enumerate(reactant_smiles_list):
        reactants.append(
            MoleculeNode(
                id=f"root-{i}",
                molecule_hash=generate_molecule_hash(smiles),
                smiles=smiles,
                is_starting_material=True,
                reactions=[],
            )
        )

    reaction = ReactionNode(
        id="rxn-root",
        reaction_smiles=f"{'.'.join(sorted(r.smiles for r in reactants))}>>{target_smiles}",
        reactants=reactants,
    )

    root_node = MoleculeNode(
        id="root",
        molecule_hash=generate_molecule_hash(target_smiles),
        smiles=target_smiles,
        is_starting_material=False,
        reactions=[reaction],
    )

    return BenchmarkTree(target=target_info, retrosynthetic_tree=root_node)


def test_deduplicate_keeps_unique_routes() -> None:
    """
    Tests that two genuinely different routes for the same target are both kept.
    """
    # Arrange
    # Route 1: A + B >> T
    route1 = _build_simple_tree("T", ["A", "B"])
    # Route 2: C + D >> T
    route2 = _build_simple_tree("T", ["C", "D"])

    # Act
    unique_routes = deduplicate_routes([route1, route2])

    # Assert
    assert len(unique_routes) == 2


def test_deduplicate_removes_identical_routes() -> None:
    """
    Tests that an exact copy of a route is correctly removed.
    """
    # Arrange
    route1 = _build_simple_tree("T", ["A", "B"])
    route2 = _build_simple_tree("T", ["A", "B"])  # Identical

    # Act
    unique_routes = deduplicate_routes([route1, route2])

    # Assert
    assert len(unique_routes) == 1


def test_deduplicate_removes_reactant_order_duplicates() -> None:
    """
    The most important test: ensures that reactant order does not affect
    the route's unique signature.
    """
    # Arrange
    # Route 1: A + B >> T
    route1 = _build_simple_tree("T", ["A", "B"])
    # Route 2: B + A >> T (semantically identical)
    route2 = _build_simple_tree("T", ["B", "A"])

    # Act
    unique_routes = deduplicate_routes([route1, route2])

    # Assert
    assert len(unique_routes) == 1
    # Check that the remaining route is one of the ones we put in
    assert unique_routes[0].retrosynthetic_tree.reactions[0].reactants[0].smiles in ["A", "B"]


def test_deduplicate_handles_deeper_trees() -> None:
    """Tests that the recursive signature works for multi-step syntheses."""
    # Arrange
    # Intermediate C is formed from A + B
    intermediate_c = _build_simple_tree("C", ["A", "B"]).retrosynthetic_tree

    # Now we build a tree where C reacts with D to form T
    # Manually construct the final step
    reactant_d = MoleculeNode(
        id="root-1",
        molecule_hash=generate_molecule_hash("D"),
        smiles="D",
        is_starting_material=True,
        reactions=[],
    )

    # Route 1: (A + B >> C) + D >> T
    target_info = TargetInfo(id="T", smiles="T")
    final_reaction = ReactionNode(
        id="rxn-root-final",
        reaction_smiles="C.D>>T",
        reactants=[intermediate_c, reactant_d],  # Order 1
    )
    final_root_node = MoleculeNode(
        id="root-final",
        molecule_hash=generate_molecule_hash("T"),
        smiles="T",
        is_starting_material=False,
        reactions=[final_reaction],
    )
    route1 = BenchmarkTree(target=target_info, retrosynthetic_tree=final_root_node)

    # Route 2: D + (A + B >> C) >> T (same thing, different order)
    final_reaction_2 = ReactionNode(
        id="rxn-root-final-2",
        reaction_smiles="C.D>>T",
        reactants=[reactant_d, intermediate_c],  # Order 2
    )
    final_root_node_2 = MoleculeNode(
        id="root-final-2",
        molecule_hash=generate_molecule_hash("T"),
        smiles="T",
        is_starting_material=False,
        reactions=[final_reaction_2],
    )
    route2 = BenchmarkTree(target=target_info, retrosynthetic_tree=final_root_node_2)

    # Act
    unique_routes = deduplicate_routes([route1, route2])

    # Assert
    assert len(unique_routes) == 1


def test_deduplicate_on_empty_list() -> None:
    """Tests that the function handles an empty list gracefully."""
    # Act
    unique_routes = deduplicate_routes([])
    # Assert
    assert unique_routes == []


def test_deduplicate_distinguishes_different_intermediates() -> None:
    """
    Tests that (A+B>>C)+D>>T is different from (E+F>>C)+D>>T, even if the
    intermediate has the same SMILES. This is a hard test.
    """
    # Arrange
    # Route 1: A + B >> C, then C + D >> T
    tree1 = _build_simple_tree("T", ["C", "D"])  # Top level
    intermediate_c1 = _build_simple_tree("C", ["A", "B"]).retrosynthetic_tree
    # Replace the starting material 'C' with the subtree that forms it
    tree1.retrosynthetic_tree.reactions[0].reactants[0] = intermediate_c1

    # Route 2: E + F >> C, then C + D >> T
    tree2 = _build_simple_tree("T", ["C", "D"])  # Top level
    intermediate_c2 = _build_simple_tree("C", ["E", "F"]).retrosynthetic_tree
    # Replace the starting material 'C' with the different subtree that forms it
    tree2.retrosynthetic_tree.reactions[0].reactants[0] = intermediate_c2

    # Act
    unique_routes = deduplicate_routes([tree1, tree2])

    # Assert
    # The routes are different because the history of 'C' is different
    assert len(unique_routes) == 2


def test_deduplicate_distinguishes_based_on_final_target() -> None:
    """
    Tests that A+B>>T1 is different from A+B>>T2.
    """
    # Arrange
    route1 = _build_simple_tree("T1", ["A", "B"])
    route2 = _build_simple_tree("T2", ["A", "B"])

    # Act
    unique_routes = deduplicate_routes([route1, route2])

    # Assert
    assert len(unique_routes) == 2


def test_deduplicate_symmetric_reactants() -> None:
    """
    Tests that a reaction with two identical reactants (A + A >> B) is
    handled correctly and deduplicated.
    """
    # Arrange
    route1 = _build_simple_tree("B", ["A", "A"])
    route2 = _build_simple_tree("B", ["A", "A"])

    # Act
    unique_routes = deduplicate_routes([route1, route2])

    # Assert
    assert len(unique_routes) == 1


def test_deduplicate_three_reactant_permutations() -> None:
    """
    Tests that the signature is invariant to permutations of a 3-reactant step.
    """
    # Arrange
    route1 = _build_simple_tree("T", ["A", "B", "C"])
    route2 = _build_simple_tree("T", ["C", "A", "B"])
    route3 = _build_simple_tree("T", ["B", "C", "A"])

    # Act
    unique_routes = deduplicate_routes([route1, route2, route3])

    # Assert
    assert len(unique_routes) == 1


def test_deduplicate_is_independent_of_node_ids() -> None:
    """
    Tests that the signature relies on content, not the arbitrary path-dependent IDs.
    We'll build two identical trees with different node IDs.
    """
    # Arrange
    # Route 1
    r1_reactant_a = MoleculeNode(
        id="r1-a", molecule_hash=generate_molecule_hash("A"), smiles="A", is_starting_material=True, reactions=[]
    )
    r1_reactant_b = MoleculeNode(
        id="r1-b", molecule_hash=generate_molecule_hash("B"), smiles="B", is_starting_material=True, reactions=[]
    )
    r1_reaction = ReactionNode(id="r1-rxn", reaction_smiles="A.B>>T", reactants=[r1_reactant_a, r1_reactant_b])
    r1_root = MoleculeNode(
        id="r1-root",
        molecule_hash=generate_molecule_hash("T"),
        smiles="T",
        is_starting_material=False,
        reactions=[r1_reaction],
    )
    route1 = BenchmarkTree(target=TargetInfo(id="T", smiles="T"), retrosynthetic_tree=r1_root)

    # Route 2 (identical structure, different IDs)
    r2_reactant_a = MoleculeNode(
        id="r2-a", molecule_hash=generate_molecule_hash("A"), smiles="A", is_starting_material=True, reactions=[]
    )
    r2_reactant_b = MoleculeNode(
        id="r2-b", molecule_hash=generate_molecule_hash("B"), smiles="B", is_starting_material=True, reactions=[]
    )
    r2_reaction = ReactionNode(id="r2-rxn", reaction_smiles="A.B>>T", reactants=[r2_reactant_a, r2_reactant_b])
    r2_root = MoleculeNode(
        id="r2-root",
        molecule_hash=generate_molecule_hash("T"),
        smiles="T",
        is_starting_material=False,
        reactions=[r2_reaction],
    )
    route2 = BenchmarkTree(target=TargetInfo(id="T", smiles="T"), retrosynthetic_tree=r2_root)

    # Act
    unique_routes = deduplicate_routes([route1, route2])

    # Assert
    assert len(unique_routes) == 1


def test_deduplicate_distinguishes_different_assembly_order() -> None:
    """
    THE BIG ONE: Tests two routes that use the same starting materials to make
    the same target, but combine them in a different order.
    Route 1: (A + B -> I1), then (I1 + C -> T)
    Route 2: (B + C -> I2), then (I2 + A -> T)
    These are fundamentally different syntheses and MUST NOT be deduplicated.
    """
    # Arrange
    target_info = TargetInfo(id="T", smiles="T")

    # --- Route 1 Build ---
    i1_tree = _build_simple_tree("I1", ["A", "B"]).retrosynthetic_tree
    c_node = MoleculeNode(
        id="c", molecule_hash=generate_molecule_hash("C"), smiles="C", is_starting_material=True, reactions=[]
    )
    r1_final_reaction = ReactionNode(id="r1-final", reaction_smiles="C.I1>>T", reactants=[i1_tree, c_node])
    r1_root = MoleculeNode(
        id="r1-root",
        molecule_hash=generate_molecule_hash("T"),
        smiles="T",
        is_starting_material=False,
        reactions=[r1_final_reaction],
    )
    route1 = BenchmarkTree(target=target_info, retrosynthetic_tree=r1_root)

    # --- Route 2 Build ---
    i2_tree = _build_simple_tree("I2", ["B", "C"]).retrosynthetic_tree
    a_node = MoleculeNode(
        id="a", molecule_hash=generate_molecule_hash("A"), smiles="A", is_starting_material=True, reactions=[]
    )
    r2_final_reaction = ReactionNode(id="r2-final", reaction_smiles="A.I2>>T", reactants=[i2_tree, a_node])
    r2_root = MoleculeNode(
        id="r2-root",
        molecule_hash=generate_molecule_hash("T"),
        smiles="T",
        is_starting_material=False,
        reactions=[r2_final_reaction],
    )
    route2 = BenchmarkTree(target=target_info, retrosynthetic_tree=r2_root)

    # Act
    unique_routes = deduplicate_routes([route1, route2])

    # Assert
    assert len(unique_routes) == 2


def test_deduplicate_handles_identical_subtrees_in_different_branches() -> None:
    """
    Tests deduplication of a complex route where the same intermediate
    synthesis (A+B>>C) is used twice.
    Route: (A+B>>C) + (A+B>>C) >> T
    """
    # Arrange
    target_info = TargetInfo(id="T", smiles="T")

    # --- Build two identical sub-trees ---
    # We must build them as separate objects even if they are identical
    # to simulate a real tree traversal.
    subtree1 = _build_simple_tree("C", ["A", "B"]).retrosynthetic_tree
    subtree2 = _build_simple_tree("C", ["A", "B"]).retrosynthetic_tree
    # Make their IDs different to be more realistic
    subtree2.id = "root-clone"

    # --- Build two identical final routes using these sub-trees ---
    route1_reaction = ReactionNode(id="r1-rxn", reaction_smiles="C.C>>T", reactants=[subtree1, subtree2])
    route1_root = MoleculeNode(
        id="r1-root",
        molecule_hash=generate_molecule_hash("T"),
        smiles="T",
        is_starting_material=False,
        reactions=[route1_reaction],
    )
    route1 = BenchmarkTree(target=target_info, retrosynthetic_tree=route1_root)

    route2_reaction = ReactionNode(
        id="r2-rxn", reaction_smiles="C.C>>T", reactants=[subtree2, subtree1]
    )  # Note swapped order
    route2_root = MoleculeNode(
        id="r2-root",
        molecule_hash=generate_molecule_hash("T"),
        smiles="T",
        is_starting_material=False,
        reactions=[route2_reaction],
    )
    route2 = BenchmarkTree(target=target_info, retrosynthetic_tree=route2_root)

    # Act
    unique_routes = deduplicate_routes([route1, route2])

    # Assert
    assert len(unique_routes) == 1
