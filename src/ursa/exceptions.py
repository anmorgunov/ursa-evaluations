class UrsaException(Exception):
    """Base exception for all errors raised by the ursa package."""

    pass


class InvalidSmilesError(UrsaException):
    """Raised when a SMILES string is malformed or cannot be processed."""

    pass


class SchemaLogicError(UrsaException):
    """Raised when data violates the logical rules of a schema, beyond basic type validation."""

    pass
