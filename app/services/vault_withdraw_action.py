"""
Optimized vault withdrawal action.

Self-contained module: all Plutus types and helpers needed for on-chain
withdrawal are gathered here (originating from vault_client.py).

Only the **manager** signs; the recipient (B) does not sign.
Manager wallet is resolved via ``get_manager_wallet(pkh)``.
"""

from cmath import phase
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from pycardano import (
    Address as CardanoAddress,
    BlockFrostChainContext,
    Network,
    PaymentSigningKey,
    PlutusData,
    PlutusV3Script,
    RawPlutusData,
    Redeemer,
    TransactionBuilder,
    TransactionOutput,
    UTxO,
    Value,
)

from app.core.config import settings
from app.services.manager_wallet import get_manager_wallet
from app.services.contract_scripts import load_contract_script

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blockfrost chain context
# ---------------------------------------------------------------------------

BLOCKFROST_ENDPOINTS = {
    Network.MAINNET: "https://cardano-mainnet.blockfrost.io/api/",
    Network.TESTNET: "https://cardano-preprod.blockfrost.io/api/",
}


def _get_chain_context() -> BlockFrostChainContext:
    return BlockFrostChainContext(
        project_id=settings.BLOCKFROST_API_KEY,
        base_url=BLOCKFROST_ENDPOINTS.get(
            settings.CARDANO_NETWORK,
            BLOCKFROST_ENDPOINTS[Network.MAINNET],
        ),
    )


# ---------------------------------------------------------------------------
# Plutus data types (mirror contracts/vault definitions)
# ---------------------------------------------------------------------------

TAG_WITHDRAW = 8


@dataclass
class VaultConfigDatum(PlutusData):
    state: int  # 0: Open, 1: Trading, 2: Withdrawable, 3: Closed
    manager: bytes
    asset_policy: bytes
    asset_name: bytes
    max_users: int
    t_time: int # trading_time
    w_time: int # withdrawable_time
    cap: int # total_capital (Total ADA contributed)
    pmv: int # post_money_value (Snapshot of tracked asset amount)


@dataclass
class VaultRedeemer(PlutusData):
    tag: int = 0
    i1: int = 0
    i2: int = 0
    i3: int = 0
    b1: bytes = b""
    b2: bytes = b""


# ---------------------------------------------------------------------------
# Helpers (from vault_client.py)
# ---------------------------------------------------------------------------


def _canonicalize_hex(value: str) -> str:
    if value.startswith(("0x", "0X")):
        value = value[2:]
    return value.lower()


def _extract_bytes(key) -> bytes:
    return getattr(key, "payload", key)


def get_utxo_by_ref(
    context: BlockFrostChainContext,
    tx_id: str,
    index: int,
    search_addresses: list[CardanoAddress],
) -> UTxO:
    """Locate a live UTxO by transaction hash and output index."""
    canonical = _canonicalize_hex(tx_id)
    for address in search_addresses:
        for utxo in context.utxos(address):
            utxo_hash = utxo.input.transaction_id.payload.hex().lower()
            if utxo_hash == canonical and utxo.input.index == index:
                return utxo
    raise ValueError(f"UTxO {tx_id}#{index} not found at provided addresses")


def _asset_value(
    policy: bytes,
    name: bytes,
    qty: int,
    min_ada: int = 2_000_000,
) -> Value:
    """Build a ``Value`` holding *qty* of a native asset (or pure lovelace)."""
    if policy == b"" and name == b"":
        return Value(qty)
    return Value(min_ada, {policy: {name: qty}})


def _subtract_asset(
    policy: bytes,
    name: bytes,
    qty: int,
    value: Value,
) -> Value:
    """Return *value* minus *qty* of the given asset."""
    coin = value.coin - qty if policy == b"" and name == b"" else value.coin
    raw_assets = value.multi_asset.copy() if value.multi_asset else {}
    if policy and name:
        remaining: dict = {}
        for pol, amounts in raw_assets.items():
            pol_bytes = _extract_bytes(pol)
            remaining[pol_bytes] = {}
            for asset_name_key, amount in amounts.items():
                name_bytes = _extract_bytes(asset_name_key)
                if pol_bytes == policy and name_bytes == name:
                    amount -= qty
                if amount > 0:
                    remaining[pol_bytes][name_bytes] = amount
            if not remaining[pol_bytes]:
                del remaining[pol_bytes]
        return Value(coin, remaining)
    return Value(coin, raw_assets) if raw_assets else Value(coin)


# ---------------------------------------------------------------------------
# UTxO reference parser
# ---------------------------------------------------------------------------


def _parse_utxo_ref(ref: str) -> Tuple[str, int]:
    """Parse ``'tx_id#index'`` into ``(tx_id, index)``."""
    value = ref.strip()
    if "#" not in value:
        raise ValueError(f"UTxO ref must be 'tx_id#index', got: {ref}")
    tx_id, index_str = value.rsplit("#", 1)
    tx_id = tx_id.strip()
    if len(tx_id) != 64 or not all(c in "0123456789abcdefABCDEF" for c in tx_id):
        raise ValueError(f"Invalid tx_id in UTxO ref: {tx_id}")
    try:
        index = int(index_str.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid index in UTxO ref: {index_str}") from exc
    if index < 0:
        raise ValueError(f"Index must be non-negative: {index}")
    return tx_id, index


# ---------------------------------------------------------------------------
# Core withdraw transaction builder
# ---------------------------------------------------------------------------


def _build_withdraw_tx(
    context: BlockFrostChainContext,
    *,
    script: PlutusV3Script,
    vault_address: CardanoAddress,
    recipient_address: CardanoAddress,
    config_utxo: UTxO,
    amount: int,
    manager_signing_key: PaymentSigningKey,
    manager_address: CardanoAddress,
) -> str:
    """
    Build, sign and submit a withdrawal transaction.

    * Spends the vault config UTxO via script input + ``TAG_WITHDRAW`` redeemer.
    * Sends *amount* lovelace to *recipient_address*.
    * Returns remaining value (with updated datum) to *vault_address*.
    * Only the manager signs; the recipient does **not** sign.

    Returns the submitted transaction hash.
    """
    if amount <= 0:
        raise ValueError("Withdraw amount must be positive")
    if config_utxo.output.datum is None:
        raise ValueError("config_utxo.output.datum is None")
    current_datum = VaultConfigDatum.from_cbor(config_utxo.output.datum.cbor)
    # print(f"current_datum.to_dict(): {current_datum.to_dict()}")

    # Compute output values
    remaining_value = _subtract_asset(b"", b"", amount, config_utxo.output.amount)
    user_value = _asset_value(b"", b"", amount)

    # Datum for the continuing vault UTxO (state preserved)
    next_datum = VaultConfigDatum(
        state=current_datum.state,
        manager=current_datum.manager,
        asset_policy=current_datum.asset_policy,
        asset_name=current_datum.asset_name,
        max_users=current_datum.max_users,
        t_time=current_datum.t_time,
        w_time=current_datum.w_time,
        cap=current_datum.cap,
        pmv=current_datum.pmv,
    )

    redeemer = Redeemer(
        VaultRedeemer(tag=TAG_WITHDRAW, i1=0, i2=0, i3=0, b1=b"", b2=b"")
    )

    builder = TransactionBuilder(context)
    builder.add_input_address(manager_address)
    builder.required_signers = [current_datum.manager]
    builder.add_script_input(config_utxo, script=script, redeemer=redeemer)
    # Output 0 — vault remainder (with datum)
    builder.add_output(
        TransactionOutput(vault_address, amount=remaining_value, datum=next_datum)
    )
    # Output 1 — recipient receives their ADA
    builder.add_output(TransactionOutput(recipient_address, amount=user_value))
    builder.validity_start = context.last_block_slot
    signed_tx = builder.build_and_sign(
        [manager_signing_key], change_address=manager_address
    )
    context.submit_tx(signed_tx)
    return str(signed_tx.id)


# ---------------------------------------------------------------------------
# Public API — withdraw_action
# ---------------------------------------------------------------------------


@dataclass
class WithdrawResult:
    """Structured result returned by ``withdraw_action``."""

    tx_hash: str
    new_config_tx: str
    new_config_index: int


def withdraw_action(
    amount: int,
    network_name: str = "preprod",
    recipient_address: str | None = None,
    manager_pkh: str | None = None,
    vault_address: str = "",
    config_utxo_ref: str = "",
    contract_name: str | None = None,
) -> WithdrawResult:
    """
    Execute a vault withdrawal on-chain using the Plutus script loaded from disk.

    Parameters
    ----------
    amount : int
        Lovelace to withdraw (must be > 0).
    network_name : str
        Cardano network — ``"preprod"`` or ``"mainnet"``.
    recipient_address : str | None
        Bech32 address of the recipient (user B).
    manager_pkh : str | None
        Manager public-key hash.  When *None* the first wallet entry
        from the wallets file is used (see ``get_manager_wallet``).
    vault_address : str
        Vault script address (Bech32).
    config_utxo_ref : str
        Vault config UTxO reference as ``"tx_id#index"``.
    contract_name : str | None
        Optional contract identifier used to locate ``secret/contracts/{contract}/script.cbor``.

    Returns
    -------
    WithdrawResult
        Transaction hash and new config UTxO location.
    """
    # --- validate inputs ---------------------------------------------------
    if not recipient_address or not recipient_address.strip():
        raise ValueError("recipient_address is required")
    recipient_address = recipient_address.strip()
    if "\u2026" in recipient_address or "..." in recipient_address:
        raise ValueError("recipient_address looks truncated")
    if len(recipient_address) < 50:
        raise ValueError("recipient_address is too short for a valid Bech32 address")
    if not vault_address or not vault_address.strip():
        raise ValueError("vault_address is required")
    if not config_utxo_ref or not config_utxo_ref.strip():
        raise ValueError("config_utxo_ref is required")
    if amount <= 0:
        raise ValueError("amount must be positive")

    logger.info(
        "withdraw_action: amount=%d vault=%s config_ref=%s recipient=%s",
        amount,
        vault_address,
        config_utxo_ref,
        recipient_address[:20] + "...",
    )

    # --- chain context -----------------------------------------------------
    context = _get_chain_context()

    # --- manager wallet ----------------------------------------------------
    manager = get_manager_wallet(manager_pkh)

    # --- resolve config UTxO (vault state — this gets spent) ---------------
    resolved_vault_addr = CardanoAddress.from_primitive(vault_address.strip())
    tx_id, index = _parse_utxo_ref(config_utxo_ref)
    config_utxo = get_utxo_by_ref(context, tx_id, index, [resolved_vault_addr])

    vault_coin = config_utxo.output.amount.coin
    if vault_coin < amount:
        raise ValueError(
            f"vault UTxO has {vault_coin} lovelace but withdraw requires {amount}"
        )

    # --- load script from file ----------------------------------------------
    script = load_contract_script(contract_name)

    b_address = CardanoAddress.from_primitive(recipient_address)

    # --- submit tx ---------------------------------------------------------
    tx_hash = _build_withdraw_tx(
        context=context,
        script=script,
        vault_address=resolved_vault_addr,
        recipient_address=b_address,
        config_utxo=config_utxo,
        amount=amount,
        manager_signing_key=manager.signing_key,
        manager_address=manager.address,
    )

    logger.info("withdraw tx submitted: %s", tx_hash)

    # New config UTxO is output 0 (vault remainder)
    return WithdrawResult(
        tx_hash=tx_hash,
        new_config_tx=tx_hash,
        new_config_index=0,
    )
