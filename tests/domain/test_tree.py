# tests/test_tree.py

from ursa.domain.schemas import BenchmarkTree, MoleculeNode, ReactionNode, TargetInfo
from ursa.domain.tree import calculate_route_length, deduplicate_routes, filter_top_k_per_length
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


def _build_multi_step_tree() -> BenchmarkTree:
    """Helper to build a 3-step tree: A+B>>C, C+D>>E, E+F>>G"""
    target_info = TargetInfo(id="G", smiles="G")

    # Starting materials
    a_node = MoleculeNode(
        id="a", molecule_hash=generate_molecule_hash("A"), smiles="A", is_starting_material=True, reactions=[]
    )
    b_node = MoleculeNode(
        id="b", molecule_hash=generate_molecule_hash("B"), smiles="B", is_starting_material=True, reactions=[]
    )
    d_node = MoleculeNode(
        id="d", molecule_hash=generate_molecule_hash("D"), smiles="D", is_starting_material=True, reactions=[]
    )
    f_node = MoleculeNode(
        id="f", molecule_hash=generate_molecule_hash("F"), smiles="F", is_starting_material=True, reactions=[]
    )

    # Intermediate C: A + B >> C
    c_reaction = ReactionNode(id="rxn-c", reaction_smiles="A.B>>C", reactants=[a_node, b_node])
    c_node = MoleculeNode(
        id="c",
        molecule_hash=generate_molecule_hash("C"),
        smiles="C",
        is_starting_material=False,
        reactions=[c_reaction],
    )

    # Intermediate E: C + D >> E
    e_reaction = ReactionNode(id="rxn-e", reaction_smiles="C.D>>E", reactants=[c_node, d_node])
    e_node = MoleculeNode(
        id="e",
        molecule_hash=generate_molecule_hash("E"),
        smiles="E",
        is_starting_material=False,
        reactions=[e_reaction],
    )

    # Target G: E + F >> G
    g_reaction = ReactionNode(id="rxn-g", reaction_smiles="E.F>>G", reactants=[e_node, f_node])
    g_node = MoleculeNode(
        id="g",
        molecule_hash=generate_molecule_hash("G"),
        smiles="G",
        is_starting_material=False,
        reactions=[g_reaction],
    )

    return BenchmarkTree(target=target_info, retrosynthetic_tree=g_node)


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


def test_calculate_route_length_zero_step() -> None:
    """Test route length calculation for a starting material (0 steps)."""
    target_info = TargetInfo(id="A", smiles="A")
    a_node = MoleculeNode(
        id="a", molecule_hash=generate_molecule_hash("A"), smiles="A", is_starting_material=True, reactions=[]
    )
    tree = BenchmarkTree(target=target_info, retrosynthetic_tree=a_node)

    assert calculate_route_length(tree.retrosynthetic_tree) == 0


def test_calculate_route_length_one_step() -> None:
    """Test route length calculation for a 1-step synthesis."""
    tree = _build_simple_tree("T", ["A", "B"])
    assert calculate_route_length(tree.retrosynthetic_tree) == 1


def test_calculate_route_length_two_step() -> None:
    """Test route length calculation for a 2-step synthesis."""
    # Build: A+B>>C, then C+D>>T
    target_info = TargetInfo(id="T", smiles="T")

    a_node = MoleculeNode(
        id="a", molecule_hash=generate_molecule_hash("A"), smiles="A", is_starting_material=True, reactions=[]
    )
    b_node = MoleculeNode(
        id="b", molecule_hash=generate_molecule_hash("B"), smiles="B", is_starting_material=True, reactions=[]
    )
    c_node = MoleculeNode(
        id="c", molecule_hash=generate_molecule_hash("C"), smiles="C", is_starting_material=True, reactions=[]
    )

    # A+B>>D, then D+C>>T2 (2 steps)
    d_reaction = ReactionNode(id="rxn-d", reaction_smiles="A.B>>D", reactants=[a_node, b_node])
    d_node = MoleculeNode(
        id="d",
        molecule_hash=generate_molecule_hash("D"),
        smiles="D",
        is_starting_material=False,
        reactions=[d_reaction],
    )

    t2_reaction = ReactionNode(id="rxn-t2", reaction_smiles="D.C>>T2", reactants=[d_node, c_node])
    t2_node = MoleculeNode(
        id="t2",
        molecule_hash=generate_molecule_hash("T2"),
        smiles="T2",
        is_starting_material=False,
        reactions=[t2_reaction],
    )
    tree = BenchmarkTree(target=target_info, retrosynthetic_tree=t2_node)
    assert calculate_route_length(tree.retrosynthetic_tree) == 2


def test_calculate_route_length_three_step() -> None:
    """Test route length calculation for a 3-step synthesis."""
    # Build 3-step tree: A+B>>C, C+D>>E, E+F>>G
    target_info = TargetInfo(id="G", smiles="G")

    # Starting materials
    a_node = MoleculeNode(
        id="a", molecule_hash=generate_molecule_hash("A"), smiles="A", is_starting_material=True, reactions=[]
    )
    b_node = MoleculeNode(
        id="b", molecule_hash=generate_molecule_hash("B"), smiles="B", is_starting_material=True, reactions=[]
    )
    d_node = MoleculeNode(
        id="d", molecule_hash=generate_molecule_hash("D"), smiles="D", is_starting_material=True, reactions=[]
    )
    f_node = MoleculeNode(
        id="f", molecule_hash=generate_molecule_hash("F"), smiles="F", is_starting_material=True, reactions=[]
    )

    # Intermediate C: A + B >> C
    c_reaction = ReactionNode(id="rxn-c", reaction_smiles="A.B>>C", reactants=[a_node, b_node])
    c_node = MoleculeNode(
        id="c",
        molecule_hash=generate_molecule_hash("C"),
        smiles="C",
        is_starting_material=False,
        reactions=[c_reaction],
    )

    # Intermediate E: C + D >> E
    e_reaction = ReactionNode(id="rxn-e", reaction_smiles="C.D>>E", reactants=[c_node, d_node])
    e_node = MoleculeNode(
        id="e",
        molecule_hash=generate_molecule_hash("E"),
        smiles="E",
        is_starting_material=False,
        reactions=[e_reaction],
    )

    # Target G: E + F >> G
    g_reaction = ReactionNode(id="rxn-g", reaction_smiles="E.F>>G", reactants=[e_node, f_node])
    g_node = MoleculeNode(
        id="g",
        molecule_hash=generate_molecule_hash("G"),
        smiles="G",
        is_starting_material=False,
        reactions=[g_reaction],
    )

    tree = BenchmarkTree(target=target_info, retrosynthetic_tree=g_node)
    assert calculate_route_length(tree.retrosynthetic_tree) == 3


def test_filter_top_k_per_length_empty_list() -> None:
    """Test filter_top_k_per_length with empty list."""
    result = filter_top_k_per_length([], 5)
    assert result == []


def test_filter_top_k_per_length_zero_k() -> None:
    """Test filter_top_k_per_length with k=0."""
    tree = _build_simple_tree("T", ["A", "B"])
    result = filter_top_k_per_length([tree], 0)
    assert result == []


def test_filter_top_k_per_length_negative_k() -> None:
    """Test filter_top_k_per_length with negative k."""
    tree = _build_simple_tree("T", ["A", "B"])
    result = filter_top_k_per_length([tree], -1)
    assert result == []


def test_filter_top_k_per_length_single_route() -> None:
    """Test filter_top_k_per_length with single route."""
    tree = _build_simple_tree("T", ["A", "B"])
    result = filter_top_k_per_length([tree], 1)
    assert len(result) == 1
    assert result[0] == tree


def test_filter_top_k_per_length_multiple_lengths() -> None:
    """Test filter_top_k_per_length with routes of different lengths."""
    # Create routes with lengths 1, 2, and 3
    route1 = _build_simple_tree("T1", ["A", "B"])  # length 1
    route2 = _build_simple_tree("T2", ["A", "B"])  # length 1 (duplicate)
    route3 = _build_simple_tree("T3", ["A", "B"])  # length 1 (duplicate)

    # Create 2-step route
    target_info = TargetInfo(id="T4", smiles="T4")
    a_node = MoleculeNode(
        id="a", molecule_hash=generate_molecule_hash("A"), smiles="A", is_starting_material=True, reactions=[]
    )
    b_node = MoleculeNode(
        id="b", molecule_hash=generate_molecule_hash("B"), smiles="B", is_starting_material=True, reactions=[]
    )
    c_node = MoleculeNode(
        id="c", molecule_hash=generate_molecule_hash("C"), smiles="C", is_starting_material=True, reactions=[]
    )

    # A+B>>D, then D+C>>T4 (2 steps)
    d_reaction = ReactionNode(id="rxn-d", reaction_smiles="A.B>>D", reactants=[a_node, b_node])
    d_node = MoleculeNode(
        id="d",
        molecule_hash=generate_molecule_hash("D"),
        smiles="D",
        is_starting_material=False,
        reactions=[d_reaction],
    )

    t4_reaction = ReactionNode(id="rxn-t4", reaction_smiles="D.C>>T4", reactants=[d_node, c_node])
    t4_node = MoleculeNode(
        id="t4",
        molecule_hash=generate_molecule_hash("T4"),
        smiles="T4",
        is_starting_material=False,
        reactions=[t4_reaction],
    )
    route4 = BenchmarkTree(target=target_info, retrosynthetic_tree=t4_node)

    # Create 3-step route
    route5 = _build_simple_tree("T5", ["A", "B"])  # length 1
    route6 = _build_simple_tree("T6", ["A", "B"])  # length 1

    routes = [route1, route2, route3, route4, route5, route6]

    # Test k=2 - should keep 2 routes of length 1, 1 route of length 2, 0 routes of length 3
    result = filter_top_k_per_length(routes, 2)
    assert len(result) == 3  # 2 (length 1) + 1 (length 2) + 0 (length 3)

    # Verify we have the right distribution
    lengths = [calculate_route_length(r.retrosynthetic_tree) for r in result]
    assert lengths.count(1) == 2
    assert lengths.count(2) == 1


def test_filter_top_k_per_length_same_length_routes() -> None:
    """Test filter_top_k_per_length with multiple routes of same length."""
    # Create 5 routes of length 1
    routes = [_build_simple_tree(f"T{i}", [f"A{i}", f"B{i}"]) for i in range(5)]

    # Test k=3 - should keep 3 routes
    result = filter_top_k_per_length(routes, 3)
    assert len(result) == 3

    # Test k=10 - should keep all 5 routes
    result = filter_top_k_per_length(routes, 10)
    assert len(result) == 5


def test_integration_deduplication_and_filtering() -> None:
    """Test integration of deduplication and top-k filtering."""
    # Create routes with duplicates and different lengths
    routes = []

    # 3 identical routes of length 1
    for _ in range(3):
        routes.append(_build_simple_tree("T1", ["A", "B"]))

    # 2 identical routes of length 2
    for i in range(2):
        target_info = TargetInfo(id="T2", smiles="T2")
        a_node = MoleculeNode(
            id=f"a{i}", molecule_hash=generate_molecule_hash("A"), smiles="A", is_starting_material=True, reactions=[]
        )
        b_node = MoleculeNode(
            id=f"b{i}", molecule_hash=generate_molecule_hash("B"), smiles="B", is_starting_material=True, reactions=[]
        )
        c_node = MoleculeNode(
            id=f"c{i}", molecule_hash=generate_molecule_hash("C"), smiles="C", is_starting_material=True, reactions=[]
        )

        d_reaction = ReactionNode(id=f"rxn-d{i}", reaction_smiles="A.B>>D", reactants=[a_node, b_node])
        d_node = MoleculeNode(
            id=f"d{i}",
            molecule_hash=generate_molecule_hash("D"),
            smiles="D",
            is_starting_material=False,
            reactions=[d_reaction],
        )

        t2_reaction = ReactionNode(id=f"rxn-t2_{i}", reaction_smiles="D.C>>T2", reactants=[d_node, c_node])
        t2_node = MoleculeNode(
            id=f"t2_{i}",
            molecule_hash=generate_molecule_hash("T2"),
            smiles="T2",
            is_starting_material=False,
            reactions=[t2_reaction],
        )
        routes.append(BenchmarkTree(target=target_info, retrosynthetic_tree=t2_node))

    # Deduplicate first
    deduped_routes = deduplicate_routes(routes)
    assert len(deduped_routes) == 2  # Should have 1 unique route per length

    # Then apply top-k filtering
    filtered_routes = filter_top_k_per_length(deduped_routes, 1)
    assert len(filtered_routes) == 2  # Should keep 1 route of each length
