# src/ursa/adapters/base_adapter.py

from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any

from ursa.domain.schemas import BenchmarkTree, DMSTree, TargetInfo


class BaseAdapter(ABC):
    """
    Abstract base class for all model output adapters.

    An adapter's role is to transform a model's raw output format into the
    canonical `BenchmarkTree` schema.
    """

    @abstractmethod
    def adapt_raw_target_data(
        self, raw_target_data: Any, target_info: TargetInfo
    ) -> Generator[BenchmarkTree, None, None]:
        """
        Validates, transforms, and yields BenchmarkTrees from raw model data.

        This is the primary method for an adapter. It encapsulates all model-
        specific logic. It should be a generator that yields successful trees
        and handles its own exceptions internally by logging and continuing.

        Args:
            raw_target_data: The raw data blob from a file for a single target.
            target_info: The identity of the target molecule.

        Yields:
            Successfully transformed BenchmarkTree objects.
        """
        raise NotImplementedError

    @abstractmethod
    def transform(self, raw_data: DMSTree, target_info: TargetInfo) -> BenchmarkTree:
        """
        Transforms raw model data into a validated BenchmarkTree.

        This method should be considered 'unsafe' and is expected to raise
        an UrsaException (e.g., InvalidSmilesError, SchemaLogicError) if
        the transformation cannot be completed successfully.

        Args:
            raw_data: The Pydantic-validated raw input data for a single target.
            target_info: The identity of the target molecule.

        Returns:
            A complete and validated BenchmarkTree.

        Raises:
            UrsaException: If any part of the transformation fails.
        """
        raise NotImplementedError
