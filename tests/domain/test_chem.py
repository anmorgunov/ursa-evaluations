import pytest

from ursa.domain.chem import canonicalize_smiles
from ursa.exceptions import InvalidSmilesError


def test_canonicalize_smiles_valid_non_canonical() -> None:
    """Tests that a valid, non-canonical SMILES is correctly canonicalized."""
    # Arrange
    non_canonical_smiles = "C(C)O"  # Ethanol
    expected_canonical = "CCO"

    # Act
    result = canonicalize_smiles(non_canonical_smiles)

    # Assert
    assert result == expected_canonical


def test_canonicalize_smiles_already_canonical() -> None:
    """Tests that an already-canonical SMILES string remains unchanged."""
    # Arrange
    canonical_smiles = "CCO"

    # Act
    result = canonicalize_smiles(canonical_smiles)

    # Assert
    assert result == canonical_smiles


def test_canonicalize_smiles_with_stereochemistry() -> None:
    """Tests that stereochemical information is preserved."""
    # Arrange
    chiral_smiles = "C[C@H](O)C(=O)O"  # (R)-Lactic acid
    # RDKit's canonical form for this might vary, but it should be consistent
    # and contain stereochemical markers. Let's find out what it is.
    expected_canonical = "C[C@H](O)C(=O)O"

    # Act
    result = canonicalize_smiles(chiral_smiles)

    # Assert
    assert result == expected_canonical


def test_canonicalize_smiles_invalid_raises_error() -> None:
    """
    Tests that passing a chemically invalid string raises InvalidSmilesError.
    """
    # Arrange
    invalid_smiles = "this is definitely not a valid smiles string C(C)O"

    # Act / Assert
    with pytest.raises(InvalidSmilesError) as exc_info:
        canonicalize_smiles(invalid_smiles)

    # Optional: check the exception message for clarity
    assert "Invalid SMILES string" in str(exc_info.value)


@pytest.mark.parametrize(
    "bad_input",
    [
        "",  # Empty string
        None,  # None value
        123,  # Not a string
    ],
)
def test_canonicalize_smiles_bad_input_type_raises_error(bad_input) -> None:
    """
    Tests that non-string or empty inputs raise InvalidSmilesError.
    """
    # Arrange (done by parametrize)

    # Act / Assert
    with pytest.raises(InvalidSmilesError) as exc_info:
        canonicalize_smiles(bad_input)

    assert "SMILES input must be a non-empty string" in str(exc_info.value)
