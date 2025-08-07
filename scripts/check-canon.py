"""
Check that the canonicalization of the buyables stock is correct.

Usage:

uv run scripts/check-canon.py

"""

from pathlib import Path

from tqdm import tqdm

from ursa.domain.chem import canonicalize_smiles
from ursa.exceptions import InvalidSmilesError

data_path = Path(__name__).resolve().parent / "data" / "models" / "assets"

buyable_lines = (data_path / "buyables-stock.txt").read_text().splitlines()

old_smi = set()
canon_smi = set()
invalid = set()
pbar = tqdm(buyable_lines, unit="smiles")
for line in pbar:
    smiles = line.split(" ")[0]
    old_smi.add(smiles)
    try:
        canon_smi.add(canonicalize_smiles(smiles))
    except InvalidSmilesError:
        invalid.add(smiles)
    pbar.set_postfix({"canon_smi": len(canon_smi), "invalid": len(invalid)})

print(f"Old: {len(old_smi)}")
print(f"Canon: {len(canon_smi)}")
print(f"Canon & Old: {len(canon_smi & old_smi)}")


# with open(data_path / "buyables-stock-canon.txt", "w") as f:
#     f.write("\n".join(sorted(canon_smi)))
