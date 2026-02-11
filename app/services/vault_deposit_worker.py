import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import cbor2
from blockfrost.utils import ApiError, Namespace
from pycardano import Address, hash, RawPlutusData

from app.api.endpoints.vault import get_vault_info
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.vault import UserEarning, VaultLog
from app.services.onchain_process import context
from app.services.vault_deployment import get_vault_deployment_info

# Retry and queue configuration
VAULT_DEPOSIT_RETRY_MAX_AGE_SECONDS = 180
VAULT_DEPOSIT_RETRY_SLEEP_SECONDS = 15
VAULT_DEPOSIT_WARN_THRESHOLD = 20

vault_deposit_queue: asyncio.Queue[Tuple[str, str, str, float]] = asyncio.Queue()
vault_deposit_worker_task: Optional[asyncio.Task] = None
vault_deposit_queue_keys: Set[Tuple[str, str]] = set()
# When worker finishes (tx on-chain, checks done), send result to this websocket if registered
vault_deposit_done_callbacks: Dict[Tuple[str, str], Any] = {}


class VaultDepositRetryableError(Exception):
    """Raised when the tx should be retried (e.g., not yet visible on chain)."""


@dataclass
class VaultDepositChainInfo:
    amount: float
    token_id: str
    timestamp: int
    fee: float
    pool_name: str
    contributor_address: str


def register_vault_deposit_done_callback(tx_id: str, vault_id: str, websocket: Any) -> None:
    """Register a websocket to receive the final result when on-chain processing is done."""
    vault_deposit_done_callbacks[(tx_id, vault_id)] = websocket


def send_vault_deposit_done_result(
    tx_id: str,
    vault_id: str,
    message: str,
    reason: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    # ws: Any = None,
) -> None:
    """Send the final result to the client that submitted this vault_deposit (if registered)."""
    # if ws is None:
    ws = vault_deposit_done_callbacks.pop((tx_id, vault_id), None)
    if ws:
        payload = {
            "message": message,
        }
        if reason is not None:
            payload["reason"] = reason
        if data is not None:
            for key, value in data.items():
                payload[key] = value
        asyncio.create_task(_safe_send_done(ws, payload))


async def _safe_send_done(websocket: Any, payload: Dict[str, Any]) -> None:
    try:
        await websocket.send_json(payload)
    except Exception:
        pass


async def queue_vault_deposit_request(
    tx_id: str, wallet_address: str, vault_id: str, done_websocket: Any = None
) -> Tuple[bool, str]:
    """
    Queue a vault deposit for background processing.
    Returns (accepted, reason). Duplicates (pending/completed) return True with descriptive reason.
    If done_websocket is provided, the client will receive a second message when on-chain checks
    finish: { message: "oke" } or { message: "failed", reason: "..." }.
    """
    key = (tx_id, vault_id)
    if key in vault_deposit_queue_keys:
        print(f"[vault-deposit-queue] already queued: {tx_id} {vault_id}")
        if done_websocket:
            await done_websocket.send_json({"message": "already_queued"})
        return True, "already queued"

    loop = asyncio.get_running_loop()
    status = await loop.run_in_executor(
        None, _ensure_vault_log_pending, tx_id, wallet_address, vault_id
    )
    if status == "completed":
        if done_websocket:
            await done_websocket.send_json({"message": "already_completed"})
        return True, "already completed"
    if status == "already_pending":
        if done_websocket:
            await done_websocket.send_json({"message": "already_pending"})
        return True, "already pending (in queue or processing)"
    # # check if the vault is in deposit state
    # vault_info = get_vault_info(vault_id)
    # if vault_info.state != "deposit":
    #     return False, "vault is not in deposit state"
    # status == "inserted": only add to process queue when not already in DB/queue
    vault_deposit_queue_keys.add(key)
    if done_websocket is not None:
        register_vault_deposit_done_callback(tx_id, vault_id, done_websocket)
        await done_websocket.send_json({"message": "accepted"})
    await vault_deposit_queue.put((tx_id, wallet_address, vault_id, time.time()))
    queue_size = vault_deposit_queue.qsize()
    if queue_size >= VAULT_DEPOSIT_WARN_THRESHOLD:
        print(
            f"[vault-deposit-queue] warning: queue size {queue_size} exceeds threshold"
        )
    await _ensure_vault_deposit_worker()
    return True, "queued"


def _ensure_vault_log_pending(tx_id: str, wallet_address: str, vault_id: str) -> str:
    """
    Insert a pending vault log or return status if already in DB.
    Returns:
      - "completed": row exists with status completed (do not queue)
      - "already_pending": row exists with status pending (do not queue; already in queue or processing)
      - "inserted": new row created (caller may add to queue)
    """
    db = SessionLocal()
    try:
        row = (
            db.query(VaultLog)
            .filter(VaultLog.txn == tx_id, VaultLog.vault_id == vault_id)
            .first()
        )
        now = int(time.time())
        if row:
            if row.status == "completed":
                return "completed"
            # if row.status == "pending":
            #     return "already_pending"
            # e.g. "failed" or other: refresh and allow re-queue
            row.status = "pending"
            row.amount = 0.0
            row.token_id = ""
            row.timestamp = now
            row.fee = 0.0
            row.extra = None
            row.wallet_address = wallet_address
            db.commit()
            return "inserted"

        new_row = VaultLog(
            vault_id=vault_id,
            wallet_address=wallet_address,
            action="deposit",
            amount=0.0,
            token_id="",  # placeholder until confirmed on-chain; DB has NOT NULL
            txn=tx_id,
            timestamp=now,
            status="pending",
            fee=0.0,
            extra=None,
        )
        db.add(new_row)
        db.commit()
        return "inserted"
    finally:
        db.close()


async def _ensure_vault_deposit_worker() -> None:
    """Ensure the background worker is running."""
    global vault_deposit_worker_task
    if vault_deposit_worker_task is None or vault_deposit_worker_task.done():
        vault_deposit_worker_task = asyncio.create_task(_vault_deposit_worker())
        print("[vault-deposit-queue] worker started")


async def _vault_deposit_worker() -> None:
    global vault_deposit_worker_task
    
    while True:
        try:
            tx_id, wallet_address, vault_id, received_at = (
                vault_deposit_queue.get_nowait()
            )
        except asyncio.QueueEmpty:
            vault_deposit_worker_task = None
            print("[vault-deposit-queue] idle, stopping worker")
            return

        key = (tx_id, vault_id)
        try:
            success = await _process_vault_deposit_item(
                tx_id, wallet_address, vault_id, received_at
            )
        finally:
            vault_deposit_queue.task_done()
            vault_deposit_queue_keys.discard(key)

        if not success:
            age = time.time() - received_at
            if age <= VAULT_DEPOSIT_RETRY_MAX_AGE_SECONDS:
                vault_deposit_queue_keys.add(key)
                await vault_deposit_queue.put((tx_id, wallet_address, vault_id, received_at))
                print(f"[vault-deposit-queue] requeue {tx_id} (age={age:.1f}s), sleeping {VAULT_DEPOSIT_RETRY_SLEEP_SECONDS}s")
                await asyncio.sleep(VAULT_DEPOSIT_RETRY_SLEEP_SECONDS)
                print(f"[vault-deposit-queue] requeued {tx_id} (age={age:.1f}s)")
                continue
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, _mark_vault_log_failed, tx_id, vault_id, "stale"
            )
            send_vault_deposit_done_result(tx_id, vault_id, "failed", "stale")


async def _process_vault_deposit_item(
    tx_id: str, wallet_address: str, vault_id: str, received_at: float
) -> bool:
    """Return True if processed (success or permanent failure), False to retry."""
    loop = asyncio.get_running_loop()
    try:
        chain_info = await loop.run_in_executor(
            None, _validate_vault_deposit_onchain, tx_id, wallet_address, vault_id
        )
        await loop.run_in_executor(
            None,
            _finalize_vault_deposit,
            tx_id,
            wallet_address,
            vault_id,
            chain_info,
        )
        print(f"[vault-deposit-queue] processed {tx_id} for vault {vault_id}")
        send_vault_deposit_done_result(
            tx_id, vault_id, "oke", data={"depositAmount": chain_info.amount}
        )
        return True
    except VaultDepositRetryableError as e:
        print(f"[vault-deposit-queue] will retry {tx_id}: {e}")
        return False
    except Exception as e:
        print(f"[vault-deposit-queue] error processing {tx_id}: {e}")
        await loop.run_in_executor(
            None, _mark_vault_log_failed, tx_id, vault_id, str(e)
        )
        send_vault_deposit_done_result(tx_id, vault_id, "failed", str(e))
        return True

# todo: optimize skip decoded.value, from raw to fields and normalize
def _parse_datum(datum_cbor: bytes=None, datum_hex: str=None) -> Tuple[int, List[any]]:
    """
    Parse vault deposit datum CBOR.
    Expected: Constr 0 with fields [hash (28 bytes), pool_asset (policy_id + pool_name as bytes)].
    Raw hex decodes as tag 121 (Constr) then either:
      - [field0, field1] (two byte strings), or
      - [constructor_index, [field0, field1]].
    Returns (constructor, list of field bytes).
    """
    if datum_hex:
        datum = RawPlutusData.from_cbor(bytes.fromhex(datum_hex)).to_dict()
    else:
        datum = RawPlutusData.from_cbor(datum_cbor).to_dict()

    if not datum["fields"]:
        raise ValueError("datum has no fields")

    fields = []
    for field in datum["fields"]:
        for k, v in field.items():
            # if k == 'bytes':
            fields.append(v)
            break
    return {
        "constructor": datum["constructor"],
        "fields": fields
    }


def _validate_vault_deposit_onchain(
    tx_id: str, wallet_address: str, vault_id: str
) -> VaultDepositChainInfo:
    """Fetch the transaction and ensure datum (address hash + pool_name) match expectations."""
    db = SessionLocal()
    try:
        deployment = get_vault_deployment_info(db, vault_id)
    finally:
        db.close()

    if not deployment:
        raise ValueError("vault deployment info missing")

    try:
        utxos = context.api.transaction_utxos(tx_id)
        tx = context.api.transaction(tx_id)
    except ApiError as exc:
        status = getattr(exc, "status_code", None)
        if status == 404:
            raise VaultDepositRetryableError("transaction not found yet") from exc
        raise

    vault_output: Optional[Namespace] = None
    for output in utxos.outputs:
        if output.address == deployment.script_address:
            vault_output = output
            break

    if not vault_output:
        raise VaultDepositRetryableError("vault output not available yet")

    # pool_id is "policy_id.pool_name". pool_name (after the dot) identifies which vault the user
    # is depositing into. Deposit asset is always ADA (lovelace).
    lovelace_amount = 0.0
    # policy_id = deployment.factory_policy_id or ""
    expected_pool_name = (deployment.pool_name or "").strip().lower()

    for entry in vault_output.amount:
        unit = entry.unit
        quantity = float(entry.quantity)
        if unit == "lovelace":
            lovelace_amount = quantity / 1_000_000
            if lovelace_amount < 1:
                raise ValueError("deposit amount must be greater or equal to 1 ADA")

    # Parse inline datum: Constr 0 with fields [hash (28 bytes), pool_asset (policy_id + pool_name)]
    inline_datum = getattr(vault_output, "inline_datum", None)
    if not inline_datum:
        raise ValueError("missing inline datum on vault output")
    datum_parsed = _parse_datum(datum_hex=inline_datum)
    fields = datum_parsed["fields"]

    if len(fields) < 2:
        raise ValueError("invalid datum shape; expected Constr 0 with two fields")
    datum_user_hash = fields[0]
    datum_pool_name = fields[1]
    try:
        if len(datum_user_hash) == 56:
            payment_part = hash.VerificationKeyHash.from_primitive(datum_user_hash)
            staking_part = None
        elif len(datum_user_hash) == 112:
            payment_part = hash.VerificationKeyHash.from_primitive(datum_user_hash[:56])
            staking_part = hash.VerificationKeyHash.from_primitive(datum_user_hash[56:])
        else:
            raise ValueError(f"invalid datum_user_hash length: {len(datum_user_hash)}")

        datum_user_address = str(
            Address(
                payment_part=payment_part,
                staking_part=staking_part,
                network=settings.CARDANO_NETWORK,
            )
        )
    except Exception as e:
        print(f"[vault-deposit-queue] _validate_vault_deposit_onchain: {e}")
        raise ValueError(f"invalid user hash in datum") from e

    if datum_user_address != wallet_address.lower():
        print(f"user hash mismatch in datum; expected user hash from wallet address. Expected: {wallet_address}, Actual: {datum_user_address}")
    if datum_pool_name != expected_pool_name:
        raise ValueError(f"pool_name mismatch in datum; expected pool_name from vault deployment, Expected: {expected_pool_name}, Actual: {datum_pool_name}")

    fee = float(getattr(tx, "fee", getattr(tx, "fees", 0))) / 1_000_000
    # Deposit asset is always ADA (lovelace); vault NFT above only identifies which vault
    return VaultDepositChainInfo(
        amount=lovelace_amount,
        token_id="lovelace",
        timestamp=int(tx.block_time or time.time()),
        fee=fee,
        pool_name=datum_pool_name,
        contributor_address=datum_user_address,
    )


def _finalize_vault_deposit(
    tx_id: str,
    wallet_address: str,
    vault_id: str,
    chain_info: VaultDepositChainInfo,
) -> None:
    """Mark the vault log as completed and bump user earnings."""
    db = SessionLocal()
    try:
        row = (
            db.query(VaultLog)
            .filter(VaultLog.txn == tx_id, VaultLog.vault_id == vault_id)
            .first()
        )

        if not row:
            return

        contributor_address = chain_info.contributor_address
        if row.wallet_address != contributor_address:
            row.wallet_address = contributor_address
        row.amount = chain_info.amount
        row.token_id = chain_info.token_id
        row.timestamp = chain_info.timestamp
        row.status = "completed"
        row.fee = chain_info.fee
        row.extra = None

        earning = (
            db.query(UserEarning)
            .filter(
                UserEarning.vault_id == vault_id,
                UserEarning.wallet_address == contributor_address,
            )
            .first()
        )
        if not earning:
            earning = UserEarning(
                vault_id=vault_id,
                wallet_address=contributor_address,
                total_deposit=chain_info.amount,
                total_withdrawal=0.0,
                current_value=chain_info.amount,
                last_updated_timestamp=int(time.time()),
            )
            db.add(earning)
        else:
            earning.total_deposit = (earning.total_deposit or 0.0) + chain_info.amount
            earning.current_value = (earning.current_value or 0.0) + chain_info.amount
            earning.last_updated_timestamp = int(time.time())
        db.commit()
    finally:
        db.close()


def _mark_vault_log_failed(tx_id: str, vault_id: str, reason: str) -> None:
    """Mark a pending vault log as failed with optional metadata reason."""
    db = SessionLocal()
    try:
        row = (
            db.query(VaultLog)
            .filter(VaultLog.txn == tx_id, VaultLog.vault_id == vault_id)
            .first()
        )
        if not row:
            return
        row.status = "failed"
        row.extra = {"reason": reason}
        db.commit()
    finally:
        db.close()
