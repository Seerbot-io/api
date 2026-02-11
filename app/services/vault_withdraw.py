from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional
import time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.vault import UserEarning, VaultConfigUtxo
from app.services.onchain_process import vault_withdraw_on_chain
from app.services.vault_deployment import get_vault_deployment_info


@dataclass
class VaultWithdrawOutcome:
    tx_hash: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


def _normalize_address(address: str) -> str:
    return address.strip().lower() if address else ""


def _ada_to_lovelace(amount_ada: float) -> int:
    try:
        ada_decimal = Decimal(str(amount_ada))
    except InvalidOperation:
        ada_decimal = Decimal(0)
    if ada_decimal <= 0:
        return 0
    return int(ada_decimal * Decimal(1_000_000))


def perform_vault_withdraw(
    db: Session,
    vault_id: str,
    wallet_address: str,
    requested_amount_ada: Optional[float] = None,
) -> VaultWithdrawOutcome:
    """
    Withdraw ADA from the vault to the user's address.

    One-time redeem semantics:
    - Always withdraw the full `earning.current_value` (ignore `requested_amount_ada`).
    - After a successful on-chain withdraw, set `earning.is_redeemed = True` and zero `current_value`.
    """
    vault_id = (vault_id or "").strip().lower()
    wallet = _normalize_address(wallet_address)
    if not vault_id or not wallet:
        return VaultWithdrawOutcome(error="vault_id and wallet_address are required")
    deployment = get_vault_deployment_info(db, vault_id)
    if not deployment or not deployment.config_utxo_tx_id:
        return VaultWithdrawOutcome(error="vault deployment info is incomplete")
    manager_pkh = deployment.manager_pkh
    if not manager_pkh:
        return VaultWithdrawOutcome(error="vault manager public key hash is missing")
    earning = (
        db.query(UserEarning)
        .with_for_update()
        .filter(
            func.lower(UserEarning.wallet_address) == wallet,
            UserEarning.vault_id == vault_id,
        )
        .first()
    )
    if not earning:
        return VaultWithdrawOutcome(error="no earnings record for this vault and wallet")
    if earning.is_redeemed:
        return VaultWithdrawOutcome(error="vault already redeemed for this wallet")
    withdrawable_ada = float(earning.current_value or 0.0)
    if withdrawable_ada <= 0:
        return VaultWithdrawOutcome(error="current value is zero or negative")
    # One-time redeem: withdraw all current_value
    target_ada = withdrawable_ada
    withdraw_amount = _ada_to_lovelace(target_ada)
    # 0.5 ADA minimum
    if withdraw_amount < 500_000:
        return VaultWithdrawOutcome(error="withdraw amount must be greater than 0.5 ADA")
    config_tx = deployment.config_utxo_tx_id
    config_index = deployment.config_utxo_index or 0
    try:
        chain_result = vault_withdraw_on_chain(
            vault_address=deployment.script_address,
            config_utxo_info=(config_tx, config_index),
            withdraw_amount=withdraw_amount,
            manager_pkh=manager_pkh,
            wallet_address=wallet,
            contract_name=deployment.contract,
        )
    except Exception as exc:
        return VaultWithdrawOutcome(error=f"on-chain withdraw failed: {exc}")
    # Update vault_config_utxo with the new config UTxO reference from the withdraw tx
    config_row = (
        db.query(VaultConfigUtxo)
        .filter(VaultConfigUtxo.vault_id == vault_id)
        .first()
    )
    if config_row:
        config_row.vault_address = deployment.script_address
        config_row.tx_hash = chain_result.new_config_tx
        config_row.utxo_id = chain_result.new_config_index
        config_row.update_time = int(time.time())

    earning.total_withdrawal = (earning.total_withdrawal or 0.0) + target_ada
    # earning.current_value = 0.0
    earning.is_redeemed = True
    earning.last_updated_timestamp = int(time.time())
    db.commit()

    return VaultWithdrawOutcome(tx_hash=chain_result.tx_hash, message=f"withdrawn {target_ada} ADA")
