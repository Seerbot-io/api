from pathlib import Path
from typing import Optional

from pycardano import PlutusV3Script

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_ROOT = REPO_ROOT / "secret" / "contracts"
DEFAULT_CONTRACT_NAME = "vault_v1"


def load_contract_script(contract_name: Optional[str]) -> PlutusV3Script:
    """Load the contract script for *contract_name* """
    name = (contract_name or "").strip()
    if not name:
        name = DEFAULT_CONTRACT_NAME
    path = CONTRACTS_ROOT / name / "script.cbor"
    if not path.exists():
        raise FileNotFoundError(f"Contract script not found: {path}")
    with open(path, "r") as f:
        return PlutusV3Script(bytes.fromhex(f.read().strip()))

