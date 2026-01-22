# pyright: reportAttributeAccessIssue=false

import asyncio
import time
import json

from psycopg2 import IntegrityError
import requests
from blockfrost.utils import Namespace
from pycardano import BlockFrostChainContext

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.swaps import Swap

context = BlockFrostChainContext(
    project_id=settings.BLOCKFROST_API_KEY,
    base_url="https://cardano-mainnet.blockfrost.io/api/",
)

MINSWAP_V2_POOL_CONTRACT = "addr1z84q0denmyep98ph3tmzwsmw0j7zau9ljmsqx6a4rvaau66j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq777e2a"

# Swap async queue worker config
SWAP_RETRY_MAX_AGE_SECONDS = 120
SWAP_RETRY_SLEEP_SECONDS = 15
SWAP_WARN_THRESHOLD = 20
swap_queue: asyncio.Queue[tuple[str, float]] = asyncio.Queue()
swap_worker_task: asyncio.Task | None = None
swap_queue_tx_ids: set[str] = set()  # Track tx_ids in queue to avoid duplicates


# not use
def sum_utxos_amount(utxos: list[Namespace], only: list[str] = []) -> dict:
    total = {}
    try:
        for u in utxos:
            if len(only) == 0 or u.address in only:
                d = total.get(u.address, {})
                for t in u.amount:
                    d[t.unit] = float(d.get(t.unit, 0)) + float(t.quantity)
                total[u.address] = d
    except Exception as e:
        raise ValueError(f"Failed to sum UTXOs: {str(e)}")
    return total


# not use
def get_change_amount_utxo(
    utxo_inputs: list[Namespace], utxo_outputs: list[Namespace], only: list[str] = []
) -> dict:
    total_in = sum_utxos_amount(utxo_inputs, only)
    total_out = sum_utxos_amount(utxo_outputs, only)
    # change = {}
    for addr, amount in total_in.items():
        addr_out = total_out.get(addr, {})
        for t, v in amount.items():
            amount_change = addr_out.get(t, 0) - v
            if amount_change == 0:
                addr_out.pop(t)
            else:
                addr_out[t] = amount_change
        if len(addr_out.keys()) == 0:
            total_out.pop(addr)
    change = total_out
    return change


# not use
def get_change_amount(tx_list: list[str], only: list[str] = []) -> dict:
    global context
    utxo_inputs = []
    utxo_outputs = []
    for tx_hash in tx_list:
        utxo = context.api.transaction_utxos(tx_hash)
        utxo_inputs += utxo.inputs
        utxo_outputs += utxo.outputs
    return get_change_amount_utxo(utxo_inputs, utxo_outputs, only)


# not use
def get_executed_tx(
    user: str, market_order_tx: str, token_in: str, token_out: str
) -> str:
    """"""
    url = "https://monorepo-mainnet-prod.minswap.org/aggregator/trading-histories"
    body = {"owner_address": user, "token_b": token_out, "token_a": token_in}
    response = requests.post(url, json=body)
    if response.status_code != 200:
        raise Exception(
            f"Failed to get executed tx: {response.status_code} {response.text}"
        )
    data = response.json()

    for order in data.get("orders", []):
        if order.get("created_tx_id", "") == market_order_tx:
            executed_tx_id = order.get("updated_tx_id", None)
            if executed_tx_id is not None:
                return executed_tx_id
            else:
                raise Exception(f"Order not executed: {market_order_tx}")
    raise Exception(f"Market order tx not found: {market_order_tx}")


# not use
def extract_swap_info_v0(
    market_order_tx: str,
    order_executed_tx: str = "",
    token_in: str = "",
    token_out: str = "",
) -> dict:
    global context
    try:
        mo_utxos = context.api.transaction_utxos(market_order_tx)
        user = mo_utxos.inputs[0].address
        if order_executed_tx == "":
            order_executed_tx = get_executed_tx(
                user, market_order_tx, token_in, token_out
            )
        timestamp = context.api.transaction(order_executed_tx).block_time
        oe_utxos = context.api.transaction_utxos(order_executed_tx)
    except Exception as e:
        print("[Error: extract_swap_info]", e)
        raise ValueError(f"Failed to get UTXOs: {str(e)}")
    user_change = get_change_amount_utxo(
        mo_utxos.inputs, mo_utxos.outputs + oe_utxos.outputs, [user]
    )
    fee = -user_change.get(user, {}).get("lovelace", 0)

    exchange_data = get_change_amount_utxo(
        oe_utxos.inputs, oe_utxos.outputs, [MINSWAP_V2_POOL_CONTRACT]
    )
    exchange_data = exchange_data.get(MINSWAP_V2_POOL_CONTRACT, {})
    if len(exchange_data.keys()) == 0:
        raise ValueError("No output")
    token_in = token_out = ""
    amount_in = amount_out = 0
    for t, v in exchange_data.items():
        if t == "lovelace":
            fee = fee - v
        if v < 0:
            token_out = t
            amount_out = -v
        else:
            token_in = t
            amount_in = v

    return {
        "transaction_id": order_executed_tx,
        "user": user,
        "token_in": token_in,
        "amount_in": amount_in,
        "token_out": token_out,
        "amount_out": amount_out,
        "fee": fee,
        "timestamp": int(timestamp),
    }


def extract_swap_info(market_order_tx: str) -> dict:
    price_res = requests.get(
        "https://agg-api.minswap.org/aggregator/ada-price?currency=usd"
    )
    price_ada = float(price_res.json().get("value", {"price": 1}).get("price", 1))
    mo_utxos = context.api.transaction_utxos(market_order_tx)
    user = mo_utxos.inputs[0].address

    url = "https://monorepo-mainnet-prod.minswap.org/aggregator/orders"
    body = {
        "owner_address": user,
        "limit": 1,
        "amount_in_decimal": True,
        "tx_id": market_order_tx,
    }
    response = requests.post(url, json=body)
    if response.status_code != 200:
        raise Exception(
            f"Failed to get executed tx: {response.status_code} {response.text}"
        )
    data = response.json()
    if len(data.get("orders", [])) == 0:
        raise Exception(f"Order not found: {market_order_tx}")
    order = data.get("orders", [])
    if len(order) == 0:
        raise Exception(f"Order not found: {market_order_tx}")
    order = order[0]
    detail = order.get("details", {})
    amount_in = float(detail.get("input_amount", 0))
    amount_out = float(detail.get("executed_amount", 0))
    if amount_in == 0 or amount_out == 0:
        raise Exception(f"Invalid amounts in order: {market_order_tx}")
    price = amount_out / amount_in
    fee = round(
        float(order.get("batcher_fee", 0)) + float(detail.get("trading_fee", 0)), 6
    )  # not all the fee

    asset_a = order.get("asset_a", {})
    asset_b = order.get("asset_b", {})
    if detail.get("direction", "") == "A_TO_B":
        token_in = asset_a.get("ticker")
        token_out = asset_b.get("ticker")
        value_ada = asset_a.get("price_by_ada", 1) * amount_in
    else:
        token_in = asset_b.get("ticker")
        token_out = asset_a.get("ticker")
        value_ada = asset_b.get("price_by_ada", 1) * amount_in
    return {
        "transaction_id": market_order_tx,
        "execution_tx_id": order.get("updated_tx_id", ""),
        "user": user,
        "token_in": token_in,
        "amount_in": amount_in,
        "token_out": token_out,
        "amount_out": amount_out,
        "price": price,
        "value_ada": value_ada,
        "fee": fee,
        "price_ada": price_ada,
    }


async def add_swap_to_queue(order_tx_id: str) -> None:
    """Add a swap order tx ID to the processing queue."""
    global swap_queue, swap_worker_task, swap_queue_tx_ids
    
    # Check if tx_id already exists in queue
    if order_tx_id in swap_queue_tx_ids:
        print(f"[swap-queue] skip: {order_tx_id} already in queue")
        return
    
    # Check if already completed in DB
    def _check_db():
        db = SessionLocal()
        try:
            existing = db.query(Swap).filter(Swap.transaction_id == order_tx_id).first()
            if existing and existing.status == "completed":
                return True
            return False
        finally:
            db.close()
    
    loop = asyncio.get_running_loop()
    is_completed = await loop.run_in_executor(None, _check_db)
    if is_completed:
        print(f"[swap-queue] skip: {order_tx_id} already completed in DB")
        return
    
    # Add to queue tracking set
    swap_queue_tx_ids.add(order_tx_id)
    
    # Write to DB with status pending
    current_timestamp = int(time.time())
    user = ""
    try:
        mo_utxos = context.api.transaction_utxos(order_tx_id)
        user = mo_utxos.inputs[0].address
    except Exception as e:
        print(f"[swap-queue] error getting user: {e}")
    pending_swap_info = {
        "transaction_id": order_tx_id,
        "execution_tx_id": "",
        "user": user,
        "token_in": "",
        "amount_in": 0,
        "token_out": "",
        "amount_out": 0,
        "price": 0,
        "value_ada": 0,
        "fee": 0,
        "price_ada": 0,
        "timestamp": current_timestamp,
    }
    await _persist_swap(pending_swap_info, status="pending")
    
    # Add to queue
    await swap_queue.put((order_tx_id, time.time()))
    queue_size = swap_queue.qsize()
    if queue_size >= SWAP_WARN_THRESHOLD:
        print(f"[swap-queue] warning: queue size {queue_size} exceeds threshold")
    await _ensure_swap_worker()


async def _persist_swap(swap_info: dict, status: str = "completed") -> None:
    """Write a swap row to DB in a thread to avoid blocking the event loop."""
    if status not in ["pending", "completed", "failed"]:
        status = "pending"

    def _write():
        db = SessionLocal()
        try:
            row = Swap(
                transaction_id=swap_info.get("transaction_id"),
                wallet_address=swap_info.get("user"),
                from_token=swap_info.get("token_in"),
                from_amount=swap_info.get("amount_in"),
                to_token=swap_info.get("token_out"),
                to_amount=swap_info.get("amount_out"),
                price=swap_info.get("price"),
                value_ada=swap_info.get("value_ada"),
                timestamp=swap_info.get("timestamp"),
                fee=swap_info.get("fee"),
                price_ada=swap_info.get("price_ada"),
                extend_data=json.dumps(
                    {
                        "order_tx_id": swap_info.get("transaction_id", ""),
                        "execution_tx_id": swap_info.get("execution_tx_id", ""),
                    }
                ),
                status=status,
            )

            db.merge(row)  # on conflict, update existing row
            db.commit()
        finally:
            db.close()

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _write)


async def _process_swap_item(order_tx_id: str, received_at: float) -> bool:
    """Process a single swap; return True on success, False to trigger retry."""
    loop = asyncio.get_running_loop()
    try:
        swap_info = await loop.run_in_executor(None, extract_swap_info, order_tx_id)
        await _persist_swap(swap_info, status="completed")
        print(f"[swap-queue] processed {order_tx_id}")
        return True
    except IntegrityError as e:
        print(f"[swap-queue] duplicate, drop {order_tx_id}: {e}")
        return True  # do not retry duplicates
    except Exception as e:
        print(f"[swap-queue] error processing {order_tx_id}: {e}")
        return False


async def _swap_worker():
    """Drain the swap queue until empty, then stop."""
    global swap_worker_task, swap_queue_tx_ids
    while True:
        try:
            order_tx_id, received_at = swap_queue.get_nowait()
        except asyncio.QueueEmpty:
            print("[swap-queue] idle, stopping worker")
            swap_worker_task = None
            return

        try:
            success = await _process_swap_item(order_tx_id, received_at)
        finally:
            swap_queue.task_done()
            # Remove from tracking set when done processing (success or fail)
            swap_queue_tx_ids.discard(order_tx_id)

        if not success:
            age = time.time() - received_at
            if age <= SWAP_RETRY_MAX_AGE_SECONDS:
                # Re-add to tracking set when requeuing
                swap_queue_tx_ids.add(order_tx_id)
                await swap_queue.put((order_tx_id, received_at))
                print(
                    f"[swap-queue] requeue {order_tx_id} (age={age:.1f}s), sleeping {SWAP_RETRY_SLEEP_SECONDS}s"
                )
                await asyncio.sleep(SWAP_RETRY_SLEEP_SECONDS)
            else:
                print(f"[swap-queue] drop stale {order_tx_id} (age={age:.1f}s)")
                swap_info = {
                    "transaction_id": order_tx_id,
                    "execution_tx_id": "",
                    "user": "",
                    "token_in": "",
                    "amount_in": 0,
                    "token_out": "",
                    "amount_out": 0,
                    "price": 0,
                    "value_ada": 0,
                    "fee": 0,
                    "price_ada": 0,
                    "status": "failed",
                }
                await _persist_swap(swap_info, status="failed")


async def _ensure_swap_worker():
    global swap_worker_task
    if swap_worker_task is None or swap_worker_task.done():
        swap_worker_task = asyncio.create_task(_swap_worker())
        print("[swap-queue] worker started")
