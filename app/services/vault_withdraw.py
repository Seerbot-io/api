from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.vault import UserEarning
from app.services.onchain_process import vault_withdraw_on_chain
from app.services.vault_deployment import VaultDeploymentInfo, get_vault_deployment_info


@dataclass
class VaultWithdrawOutcome:
    tx_hash: Optional[str]
    error: Optional[str]


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
    Evaluate if the user can withdraw (total_withdrawal < total_deposit) for given vault.
    When the user is eligible, call the on-chain withdraw stub and return the tx hash.
    """
    vault_id = (vault_id or "").strip().lower()
    wallet = _normalize_address(wallet_address)
    if not vault_id or not wallet:
        return VaultWithdrawOutcome(None, "vault_id and wallet_address are required")

    deployment = get_vault_deployment_info(db, vault_id)
    if not deployment or not deployment.reference_utxo_tx_id:
        return VaultWithdrawOutcome(None, "vault deployment info is incomplete")

    manager_pkh = deployment.manager_pkh
    if not manager_pkh:
        return VaultWithdrawOutcome(None, "vault manager public key hash is missing")

    earning = (
        db.query(UserEarning)
        .filter(
            func.lower(UserEarning.wallet_address) == wallet,
            UserEarning.vault_id == vault_id,
        )
        .first()
    )
    if not earning:
        return VaultWithdrawOutcome(None, "no earnings record for this vault and wallet")

    total_deposit = float(earning.total_deposit or 0.0)
    total_withdrawal = float(earning.total_withdrawal or 0.0)
    withdrawable_ada = total_deposit - total_withdrawal
    if withdrawable_ada <= 0:
        return VaultWithdrawOutcome(None, "withdrawals already match deposits")

    if requested_amount_ada is None or requested_amount_ada <= 0:
        target_ada = withdrawable_ada
    else:
        target_ada = min(requested_amount_ada, withdrawable_ada)

    withdraw_amount = _ada_to_lovelace(target_ada)
    if withdraw_amount <= 0:
        return VaultWithdrawOutcome(None, "withdraw amount must be greater than zero")

    config_tx = deployment.reference_utxo_tx_id
    config_index = deployment.reference_utxo_index or 0

    try:
        tx_hash = vault_withdraw_on_chain(
            vault_address=deployment.script_address,
            config_utxo_info=(config_tx, config_index),
            withdraw_amount=withdraw_amount,
            manager_pkh=manager_pkh,
        )
    except Exception as exc:
        return VaultWithdrawOutcome(None, f"on-chain withdraw failed: {exc}")

    return VaultWithdrawOutcome(tx_hash, None)
