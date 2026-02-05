"""Resolve vault_id to on-chain deployment params from DB (vault + vault_config_utxo)."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.vault import Vault, VaultConfigUtxo


@dataclass
class VaultDeploymentInfo:
    """On-chain params for a vault: script address, pool policy/asset ids (from pool_id), reference UTXO."""

    script_address: str
    factory_policy_id: str
    factory_nft_asset_name: str
    reference_utxo_tx_id: Optional[str]
    reference_utxo_index: Optional[int]
    manager_pkh: Optional[str]


def parse_pool_id(pool_id: Optional[str]) -> tuple[str, str]:
    """Split vault.pool_id ('policy_id.asset_name') into policy_id and asset_name hex."""
    if not pool_id or "." not in pool_id:
        return "", ""
    parts = pool_id.strip().split(".", 1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("", "")


def get_vault_deployment_info(db: Session, vault_id: str) -> Optional[VaultDeploymentInfo]:
    """
    Load deployment info for a vault from proddb.vault and proddb.vault_config_utxo.
    Returns None if vault not found or missing required fields (address, pool_id).
    """
    vault_id = (vault_id or "").strip().lower()
    if not vault_id:
        return None

    vault = db.query(Vault).filter(Vault.id == vault_id).first()
    if not vault or not vault.address:
        return None

    factory_policy_id, factory_nft_asset_name = parse_pool_id(vault.pool_id)
    if not factory_policy_id or not factory_nft_asset_name:
        return None

    ref_tx_id: Optional[str] = None
    ref_index: Optional[int] = None
    config_utxo = db.query(VaultConfigUtxo).filter(VaultConfigUtxo.vault_id == vault_id).first()
    if config_utxo and config_utxo.tx_hash is not None:
        ref_tx_id = config_utxo.tx_hash.strip()
        ref_index = config_utxo.utxo_id if config_utxo.utxo_id is not None else 0

    return VaultDeploymentInfo(
        script_address=vault.address.strip(),
        factory_policy_id=factory_policy_id,
        factory_nft_asset_name=factory_nft_asset_name,
        reference_utxo_tx_id=ref_tx_id,
        reference_utxo_index=ref_index,
        manager_pkh=vault.manager_pkh.strip() if vault.manager_pkh else None,
    )
