import hashlib

from ursa.domain.schemas import BenchmarkTree, MoleculeNode
from ursa.utils.logging import logger


def _generate_tree_signature(node: MoleculeNode, memo: dict[str, str]) -> str:
    """
    Recursively generates a canonical, order-invariant signature for a molecule node and its entire history.

    Args:
        node: The MoleculeNode to generate a signature for.
        memo: A dictionary used for memoization to avoid re-computing signatures.

    Returns:
        A sha256 hash representing the canonical signature of the tree/subtree.
    """
    # If we've already computed the signature for this exact node path, return it.
    if node.id in memo:
        return memo[node.id]

    # Base Case: The node is a starting material. Its signature is its own hash.
    if node.is_starting_material:
        memo[node.id] = node.molecule_hash
        return node.molecule_hash

    # Recursive Step: The node is an intermediate.
    # Its signature depends on the sorted signatures of its reactants.
    reactant_signatures = []
    # Assuming one reaction per node as per our schema
    for reactant_node in node.reactions[0].reactants:
        reactant_signatures.append(_generate_tree_signature(reactant_node, memo))

    # Sort the signatures to ensure order-invariance (A.B>>C is same as B.A>>C)
    sorted_signatures = sorted(reactant_signatures)

    # The final signature string incorporates the history and the result.
    signature_string = "".join(sorted_signatures) + ">>" + node.molecule_hash
    signature_bytes = signature_string.encode("utf-8")

    # Hash the canonical representation to get the final signature
    final_signature = f"tree_sha256:{hashlib.sha256(signature_bytes).hexdigest()}"

    memo[node.id] = final_signature
    return final_signature


def deduplicate_routes(routes: list[BenchmarkTree]) -> list[BenchmarkTree]:
    """
    Filters a list of BenchmarkTree objects, returning only the unique routes.

    Uniqueness is determined by generating a canonical signature for each tree
    that is invariant to the order of reactants.

    Args:
        routes: A list of BenchmarkTree objects to be deduplicated.

    Returns:
        A list of unique BenchmarkTree objects.
    """
    seen_signatures = set()
    unique_routes = []

    logger.debug(f"Deduplicating {len(routes)} routes...")

    for route in routes:
        # memoization cache is fresh for each independent tree
        memo: dict[str, str] = {}
        signature = _generate_tree_signature(route.retrosynthetic_tree, memo)

        if signature not in seen_signatures:
            seen_signatures.add(signature)
            unique_routes.append(route)

    num_removed = len(routes) - len(unique_routes)
    if num_removed > 0:
        logger.debug(f"Removed {num_removed} duplicate routes.")

    return unique_routes
