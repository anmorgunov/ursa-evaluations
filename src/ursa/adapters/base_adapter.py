# src/ursa/adapters/base_adapter.py

from abc import ABC, abstractmethod

from ursa.domain.schemas import BenchmarkTree, DMSTree, TargetInfo


class BaseAdapter(ABC):
    """
    Abstract base class for all model output adapters.

    An adapter's role is to transform a model's raw output format into the
    canonical `BenchmarkTree` schema.
    """

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
