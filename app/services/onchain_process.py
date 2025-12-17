# pyright: reportAttributeAccessIssue=false

from datetime import datetime

import requests
from blockfrost.utils import Namespace
from pycardano import BlockFrostChainContext

from app.core.config import settings

context = BlockFrostChainContext(
    project_id=settings.BLOCKFROST_API_KEY,
    base_url="https://cardano-mainnet.blockfrost.io/api/",
)

MINSWAP_V2_POOL_CONTRACT = "addr1z84q0denmyep98ph3tmzwsmw0j7zau9ljmsqx6a4rvaau66j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq777e2a"


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


def get_change_amount(tx_list: list[str], only: list[str] = []) -> dict:
    global context
    utxo_inputs = []
    utxo_outputs = []
    for tx_hash in tx_list:
        utxo = context.api.transaction_utxos(tx_hash)
        utxo_inputs += utxo.inputs
        utxo_outputs += utxo.outputs
    return get_change_amount_utxo(utxo_inputs, utxo_outputs, only)


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
        # print(user, market_order_tx, order_executed_tx, token_in, token_out)
        if order_executed_tx == "":
            order_executed_tx = get_executed_tx(
                user, market_order_tx, token_in, token_out
            )
        # print(order_executed_tx)
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
    ada_price = price_res.json().get("value", {"price": 1}).get("price")
    mo_utxos = context.api.transaction_utxos(
        "ab79c2bdc3890c1cc6097dc16dbdce2a3819d7f246669b0aa5f767a43a1a68f3"
    )
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
    order = data.get("orders", [])[0]
    detail = order.get("details", {})
    amount_in = float(detail.get("input_amount", 0))
    amount_out = float(detail.get("executed_amount", 0))
    fee = round(
        float(order.get("batcher_fee", 0)) + float(detail.get("trading_fee", 0)), 6
    )  # not all the fee

    asset_a = order.get("asset_a", {})
    asset_b = order.get("asset_b", {})
    if detail.get("direction", "") == "A_TO_B":
        token_in = asset_a.get("ticker")
        token_out = asset_b.get("ticker")
        value = asset_a.get("price_by_ada", 1) * amount_in
        price = asset_b.get("price_by_ada", 1) / asset_a.get("price_by_ada", 1)
    else:
        token_in = asset_b.get("ticker")
        token_out = asset_a.get("ticker")
        value = asset_b.get("price_by_ada", 1) * amount_out
        price = asset_a.get("price_by_ada", 1) / asset_b.get("price_by_ada", 1)
    return {
        "transaction_id": order.get("updated_tx_id", ""),
        "user": user,
        "token_in": token_in,
        "amount_in": amount_in,
        "token_out": token_out,
        "amount_out": amount_out,
        "price": price,
        "value": value,
        "fee": fee,
        "fee_price": ada_price,
        "timestamp": int(datetime.fromisoformat(order.get("updated_at")).timestamp()),
    }
