from functools import total_ordering
from pycardano import PaymentSigningKey, PaymentVerificationKey, Address, Network, BlockFrostChainContext, Transaction
from app.core.config import settings
from blockfrost.utils import Namespace

context = BlockFrostChainContext(
    project_id=settings.BLOCKFROST_API_KEY,
    base_url="https://cardano-mainnet.blockfrost.io/api/",
)

def check_minswap_order(tx_hash: str) -> str | None:
    tx = context.api.transaction(tx_hash)
    metadata = context.api.transaction_metadata(tx_hash)
    if metadata[0].label != '674':
        return None
    if metadata[0].json_metadata.msg[0] == "Minswap: Market Order":
        return "create_order"
    elif metadata[0].json_metadata.msg[0] == "Minswap: Order Executed":
        return "execute_order"
    else:
        return None

def sum_utxos_amount(utxos: list[Namespace], only:str=None) -> dict:
    total = {}
    for u in utxos:
        if only is None or u.address == only:
            d = total.get(u.address, {})
            for t in u.amount:
                d[t.unit] = float(d.get(t.unit, 0)) + float(t.quantity)
            total[u.address] = d
    return total

def get_change_amount(tx_hash: str, only:str=None) -> dict:
    utxos = context.api.transaction_utxos(tx_hash)
    total_in = sum_utxos_amount(utxos, only)
    total_out = sum_utxos_amount(utxos, only)
    change = {}
    for addr, amount in total_in.items():
        change[addr] = amount - total_out.get(addr, {}).get('lovelace', 0)
    return change