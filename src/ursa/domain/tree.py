import hashlib

from ursa.domain.schemas import BenchmarkTree, MoleculeNode
from ursa.utils.logging import logger


def _generate_tree_signature(node: MoleculeNode) -> str:
    """
    Recursively generates a canonical, order-invariant signature for a
    molecule node and its entire history.

    This version does not use memoization as tree objects should not be large
    enough to make this a performance bottleneck, and it avoids subtle bugs.

    Args:
        node: The MoleculeNode to generate a signature for.

    Returns:
        A hash representing the canonical signature of the tree/subtree.
    """
    # Base Case: The node is a starting material. Its signature is its own hash.
    if node.is_starting_material:
        return node.molecule_hash

    # Recursive Step: The node is an intermediate.
    # Its signature depends on the sorted signatures of its reactants.
    if not node.reactions:  # Should not happen with validation, but good to be safe
        return node.molecule_hash

    reactant_signatures = []
    # Assuming one reaction per node as per our schema
    for reactant_node in node.reactions[0].reactants:
        reactant_signatures.append(_generate_tree_signature(reactant_node))

    # Sort the signatures to ensure order-invariance (A.B>>C is same as B.A>>C)
    sorted_signatures = sorted(reactant_signatures)

    # The final signature string incorporates the history and the result.
    signature_string = "".join(sorted_signatures) + ">>" + node.molecule_hash
    signature_bytes = signature_string.encode("utf-8")

    # Hash the canonical representation to get the final signature
    return f"tree_sha256:{hashlib.sha256(signature_bytes).hexdigest()}"


def deduplicate_routes(routes: list[BenchmarkTree]) -> list[BenchmarkTree]:
    """
    Filters a list of BenchmarkTree objects, returning only the unique routes.
    """
    seen_signatures = set()
    unique_routes = []

    logger.debug(f"Deduplicating {len(routes)} routes...")

    for route in routes:
        signature = _generate_tree_signature(route.retrosynthetic_tree)

        if signature not in seen_signatures:
            seen_signatures.add(signature)
            unique_routes.append(route)

    num_removed = len(routes) - len(unique_routes)
    if num_removed > 0:
        logger.debug(f"Removed {num_removed} duplicate routes.")

    return unique_routes
