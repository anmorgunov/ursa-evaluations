from pydantic import BaseModel, Field, RootModel, model_validator

from ursa.exceptions import SchemaLogicError
from ursa.typing import ReactionSmilesStr, SmilesStr

# -------------------------------------------------------------------
#  Input Schema (Validates the raw model output)
# -------------------------------------------------------------------


class DMSTree(BaseModel):
    """
    A Pydantic model for the raw output from "DMS" models.

    This recursively validates the structure of a synthetic tree node,
    ensuring it has a 'smiles' string and a list of 'children' nodes.
    """

    smiles: str  # we don't canonicalize yet; this is raw input
    children: list["DMSTree"] = Field(default_factory=list)


class DMSRouteList(RootModel[list[DMSTree]]):
    """
    Represents the raw model output for a single target, which is a list of routes.
    """

    pass


class RunStatistics(BaseModel):
    """A Pydantic model to hold and calculate statistics for a processing run."""

    total_routes_in_raw_files: int = 0
    routes_failed_validation: int = 0
    routes_failed_transformation: int = 0
    successful_routes_before_dedup: int = 0
    final_unique_routes_saved: int = 0
    targets_with_at_least_one_route: set[str] = Field(default_factory=set)

    @property
    def total_failures(self) -> int:
        """Total number of routes that were discarded for any reason."""
        return self.routes_failed_validation + self.routes_failed_transformation

    @property
    def num_targets_with_routes(self) -> int:
        """The count of unique targets that have at least one valid route."""
        return len(self.targets_with_at_least_one_route)

    @property
    def duplication_factor(self) -> float:
        """Ratio of successful routes before and after deduplication. 1.0 means no duplicates."""
        if self.final_unique_routes_saved == 0:
            return 0.0
        ratio = self.successful_routes_before_dedup / self.final_unique_routes_saved
        return round(ratio, 2)

    def to_manifest_dict(self) -> dict[str, int | float]:
        """Generates a dictionary suitable for including in the final manifest."""
        return {
            "total_routes_in_raw_files": self.total_routes_in_raw_files,
            "total_routes_failed_or_duplicate": self.total_failures
            + (self.successful_routes_before_dedup - self.final_unique_routes_saved),
            "final_unique_routes_saved": self.final_unique_routes_saved,
            "num_targets_with_at_least_one_route": self.num_targets_with_routes,
            "duplication_factor": self.duplication_factor,
        }


# -------------------------------------------------------------------
#  Output Schemas (Defines our final, canonical benchmark format)
# -------------------------------------------------------------------


class ReactionNode(BaseModel):
    """
    Represents a single retrosynthetic reaction step in the benchmark tree.
    """

    id: str = Field(..., description="A unique, path-dependent identifier for the reaction.")
    reaction_smiles: ReactionSmilesStr
    reactants: list["MoleculeNode"] = Field(default_factory=list)


class MoleculeNode(BaseModel):
    """
    Represents a single molecule node in the benchmark tree.

    This is the core recursive data structure for the retrosynthetic route.
    It contains the molecule's identity and the reaction(s) that form it.
    """

    id: str = Field(..., description="A unique, path-dependent identifier for this molecule instance.")
    molecule_hash: str = Field(
        ..., description="A content-based hash of the canonical SMILES, identical for identical molecules."
    )
    smiles: SmilesStr
    is_starting_material: bool
    reactions: list[ReactionNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_tree_logic(self) -> "MoleculeNode":
        """
        Enforces the logical consistency of a node in a retrosynthetic tree.
        """
        num_reactions = len(self.reactions)

        # Rule 1: A starting material cannot be the product of a reaction.
        if self.is_starting_material and num_reactions > 0:
            raise SchemaLogicError(
                f"Node {self.id} ({self.smiles}) is a starting material but has {num_reactions} parent reactions."
            )

        # Rule 2: An intermediate must be the product of exactly one reaction in a valid tree.
        if not self.is_starting_material:
            if num_reactions == 0:
                raise SchemaLogicError(f"Node {self.id} ({self.smiles}) is an intermediate but has no parent reaction.")
            if num_reactions > 1:
                raise SchemaLogicError(
                    f"Node {self.id} ({self.smiles}) is part of a DAG (has {num_reactions} reactions), not a tree."
                )
        return self


class TargetInfo(BaseModel):
    """A simple container for the target molecule's identity."""

    smiles: SmilesStr
    id: str = Field(..., description="The original identifier for the target molecule.")


class BenchmarkTree(BaseModel):
    """
    The root schema for a single, complete retrosynthesis benchmark entry.
    """

    target: TargetInfo
    retrosynthetic_tree: MoleculeNode
