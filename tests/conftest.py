import pytest

from ursa.adapters.dms_adapter import DMSAdapter
from ursa.domain.schemas import TargetInfo


# fmt:off
@pytest.fixture
def single_dms_aspirin_tree_data() -> dict:
    """Provides the raw dict for a single DMS tree, for testing DMSTree directly."""
    return {"smiles":"CC(=O)OC1=CC=CC=C1C(=O)O","children":[{"smiles":"OC1=CC=CC=C1C(=O)O"},{"smiles":"CC(=O)Cl"}]}

@pytest.fixture
def raw_dms_aspirin_data() -> list[dict]:
    # FIX: The raw data for a target is a LIST of routes.
    return [{"smiles":"CC(=O)OC1=CC=CC=C1C(=O)O","children":[{"smiles":"OC1=CC=CC=C1C(=O)O"},{"smiles":"CC(=O)Cl"}]}]

@pytest.fixture
def raw_dms_vonoprazan_data() -> list[dict]:
    # FIX: The raw data for a target is a LIST of routes.
    return [{"smiles":"CNCc1cc(-c2ccccc2F)n(S(=O)(=O)c2cccnc2)c1","children":[{"smiles":"O=Cc1cc(-c2ccccc2F)n(S(=O)(=O)c2cccnc2)c1","children":[{"smiles":"O=Cc1c[nH]c(-c2ccccc2F)c1"},{"smiles":"O=S(=O)(Cl)c1cccnc1"}]},{"smiles":"CN"}]}]

@pytest.fixture
def raw_dms_daridorexant_data() -> list[dict]:
    # FIX: The raw data for a target is a LIST of routes.
    return [{"smiles":"COc1ccc(-n2nccn2)c(C(=O)N2CCC[C@@]2(C)c2nc3c(C)c(Cl)ccc3[nH]2)c1","children":[{"smiles":"Cc1c(Cl)ccc2[nH]c([C@]3(C)CCCN3)nc12","children":[{"smiles":"Cc1c(Cl)ccc2[nH]c([C@]3(C)CCCN3C(=O)OC(C)(C)C)nc12","children":[{"smiles":"Cc1c(Cl)ccc(NC(=O)[C@]2(C)CCCN2C(=O)OC(C)(C)C)c1N","children":[{"smiles":"CC(C)(C)OC(=O)N1CCC[C@@]1(C)C(=O)O","children":[{"smiles":"C[C@@]1(C(=O)O)CCCN1"},{"smiles":"CC(C)(C)OC(=O)OC(=O)OC(C)(C)C"}]},{"smiles":"Cc1c(Cl)ccc(N)c1N"}]}]}]},{"smiles":"COc1ccc(-n2nccn2)c(C(=O)O)c1","children":[{"smiles":"COc1ccc(I)c(C(=O)O)c1"},{"smiles":"c1cn[nH]n1"}]}]}]

@pytest.fixture
def raw_dms_invalid_smiles_data() -> list[dict]:
    return [{"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "children": [{"smiles": "this is not a smiles"}]}]
# fmt:on


@pytest.fixture
def aspirin_target_info() -> TargetInfo:
    # Note: the SMILES here would be pre-canonicalized
    return TargetInfo(id="aspirin", smiles="CC(=O)Oc1ccccc1C(=O)O")


@pytest.fixture
def vonoprazan_target_info() -> TargetInfo:
    return TargetInfo(id="vonoprazan", smiles="CNCc1cc(-c2ccccc2F)n(S(=O)(=O)c2cccnc2)c1")


@pytest.fixture
def daridorexant_target_info() -> TargetInfo:
    return TargetInfo(id="daridorexant", smiles="COc1ccc(-n2nccn2)c(C(=O)N2CCC[C@@]2(C)c2nc3c(C)c(Cl)ccc3[nH]2)c1")


@pytest.fixture
def dms_adapter() -> DMSAdapter:
    return DMSAdapter()
