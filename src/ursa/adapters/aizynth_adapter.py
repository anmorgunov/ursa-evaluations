from __future__ import annotations

from collections.abc import Generator
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, RootModel, ValidationError

from ursa.adapters.base_adapter import BaseAdapter
from ursa.domain.chem import canonicalize_smiles
from ursa.domain.schemas import BenchmarkTree, MoleculeNode, ReactionNode, TargetInfo
from ursa.exceptions import AdapterLogicError, UrsaException
from ursa.typing import ReactionSmilesStr, SmilesStr
from ursa.utils.hashing import generate_molecule_hash
from ursa.utils.logging import logger

# --- Pydantic models for input validation ---
# these models validate the raw aizynthfinder output format before any transformation.


class AizynthBaseNode(BaseModel):
    """A base model for shared fields between node types."""

    smiles: str
    children: list[AizynthNode] = Field(default_factory=list)


class AizynthMoleculeInput(AizynthBaseNode):
    """Represents a 'mol' node in the raw aizynth tree."""

    type: Literal["mol"]
    in_stock: bool = False


class AizynthReactionInput(AizynthBaseNode):
    """Represents a 'reaction' node in the raw aizynth tree."""

    type: Literal["reaction"]
    metadata: dict[str, Any] = Field(default_factory=dict)


# a discriminated union to handle the bipartite graph structure.
AizynthNode = Annotated[AizynthMoleculeInput | AizynthReactionInput, Field(discriminator="type")]


class AizynthRouteList(RootModel[list[AizynthMoleculeInput]]):
    """The top-level object for a single target is a list of potential routes."""

    pass


class AizynthAdapter(BaseAdapter):
    """Adapter for converting AiZynthFinder-style outputs to the BenchmarkTree schema."""

    def adapt(self, raw_target_data: Any, target_info: TargetInfo) -> Generator[BenchmarkTree, None, None]:
        """
        Validates raw AiZynthFinder data, transforms it, and yields BenchmarkTree objects.
        """
        try:
            validated_routes = AizynthRouteList.model_validate(raw_target_data)
        except ValidationError as e:
            logger.warning(f"  - Raw data for target '{target_info.id}' failed AiZynth schema validation. Error: {e}")
            return

        for aizynth_tree_root in validated_routes.root:
            try:
                tree = self._transform(aizynth_tree_root, target_info)
                yield tree
            except UrsaException as e:
                logger.warning(f"  - Route for '{target_info.id}' failed transformation: {e}")
                continue

    def _transform(self, aizynth_root: AizynthMoleculeInput, target_info: TargetInfo) -> BenchmarkTree:
        """
        Orchestrates the transformation of a single AiZynthFinder output tree.
        Raises UrsaException on failure.
        """
        retrosynthetic_tree = self._build_molecule_node(aizynth_mol=aizynth_root, path_prefix="ursa-mol-root")

        if retrosynthetic_tree.smiles != target_info.smiles:
            msg = (
                f"Mismatched SMILES for target {target_info.id}. "
                f"Expected canonical: {target_info.smiles}, but adapter produced: {retrosynthetic_tree.smiles}"
            )
            logger.error(msg)
            raise AdapterLogicError(msg)

        return BenchmarkTree(target=target_info, retrosynthetic_tree=retrosynthetic_tree)

    def _build_molecule_node(self, aizynth_mol: AizynthMoleculeInput, path_prefix: str) -> MoleculeNode:
        """
        Recursively builds a canonical MoleculeNode from a raw aizynth 'mol' node.
        """
        if aizynth_mol.type != "mol":
            raise AdapterLogicError(f"Expected node type 'mol' but got '{aizynth_mol.type}' at path {path_prefix}")

        canon_smiles = canonicalize_smiles(aizynth_mol.smiles)
        is_starting_mat = not bool(aizynth_mol.children)
        reactions = []

        if not is_starting_mat:
            if len(aizynth_mol.children) > 1:
                logger.warning(
                    f"Molecule {canon_smiles} has multiple child reactions; only the first is used in a tree."
                )

            # a molecule node's child must be a reaction node
            reaction_input = aizynth_mol.children[0]
            if not isinstance(reaction_input, AizynthReactionInput):
                raise AdapterLogicError(f"Child of molecule node was not a reaction node at {path_prefix}")

            reaction_node = self._build_reaction_node(
                aizynth_rxn=reaction_input,
                product_smiles=canon_smiles,
                path_prefix=path_prefix,  # reaction takes the parent molecule's path
            )
            reactions.append(reaction_node)

        return MoleculeNode(
            id=path_prefix,
            molecule_hash=generate_molecule_hash(canon_smiles),
            smiles=canon_smiles,
            is_starting_material=is_starting_mat,
            reactions=reactions,
        )

    def _build_reaction_node(
        self, aizynth_rxn: AizynthReactionInput, product_smiles: SmilesStr, path_prefix: str
    ) -> ReactionNode:
        """
        Builds a canonical ReactionNode from a raw aizynth 'reaction' node.
        This is called by _build_molecule_node.
        """
        if aizynth_rxn.type != "reaction":
            raise AdapterLogicError(f"Expected node type 'reaction' but got '{aizynth_rxn.type}'")

        reactants: list[MoleculeNode] = []
        reactant_smiles_list: list[SmilesStr] = []

        for i, reactant_mol_input in enumerate(aizynth_rxn.children):
            if not isinstance(reactant_mol_input, AizynthMoleculeInput):
                raise AdapterLogicError(f"Child of reaction node was not a molecule node at {path_prefix}")

            reactant_node = self._build_molecule_node(aizynth_mol=reactant_mol_input, path_prefix=f"{path_prefix}-{i}")
            reactants.append(reactant_node)
            reactant_smiles_list.append(reactant_node.smiles)

        reaction_smiles = ReactionSmilesStr(f"{'.'.join(sorted(reactant_smiles_list))}>>{product_smiles}")

        return ReactionNode(
            id=path_prefix.replace("ursa-mol", "ursa-rxn"),
            reaction_smiles=reaction_smiles,
            reactants=reactants,
        )
