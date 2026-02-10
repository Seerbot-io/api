from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pycardano import Address, Network, PaymentSigningKey, PaymentVerificationKey

from app.core.config import settings


class ManagerWalletError(Exception):
    """Raised when the manager wallet cannot be resolved."""


@dataclass(frozen=True)
class ManagerWallet:
    signing_key: PaymentSigningKey
    verification_key: PaymentVerificationKey
    address: Address


NETWORK_KEY_MAP: Dict[Network, str] = {
    Network.MAINNET: "mainnet",
    Network.TESTNET: "preprod",
}

_cached: Dict[Optional[str], ManagerWallet] = {}
_cached_network: Optional[Network] = None
_cached_path: Optional[Path] = None


def _network_key() -> str:
    key = NETWORK_KEY_MAP.get(settings.CARDANO_NETWORK)
    if not key:
        raise ManagerWalletError(
            f"unsupported Cardano network for manager wallet: {settings.CARDANO_NETWORK}"
        )
    return key


def _first_wallet_entry(network_wallets: Any) -> Dict[str, Any]:
    """Manager is the first wallet in the list for the network."""
    if not isinstance(network_wallets, list) or len(network_wallets) == 0:
        raise ManagerWalletError("no wallet list or empty list for current network")
    first = network_wallets[0]
    if not isinstance(first, dict):
        raise ManagerWalletError("first wallet entry must be a mapping")
    if len(first) == 1:
        return next(iter(first.values()))
    if "private_key" in first:
        return first
    raise ManagerWalletError("first wallet entry must include private_key or a single key with address/private_key")


def get_manager_wallet(pkh: str = None) -> ManagerWallet:
    global _cached, _cached_network, _cached_path
    network = settings.CARDANO_NETWORK
    path = Path(settings.VAULT_WALLETS_PATH)

    # Invalidate entire cache when network or path changes
    if _cached_network != network or _cached_path != path:
        _cached = {}
        _cached_network = network
        _cached_path = path

    # Return cached wallet for this pkh if available
    if pkh in _cached:
        return _cached[pkh]

    network_key = _network_key()
    if not path.exists():
        raise ManagerWalletError(f"manager wallet file not found: {path}")
    try:
        with open(path, 'r') as file:
            manager_wallet_data = yaml.safe_load(file).get(network_key)
    except yaml.YAMLError as exc:
        raise ManagerWalletError(f"failed to parse manager wallet file: {exc}") from exc

    if manager_wallet_data is None:
        raise ManagerWalletError(f"no wallet data for network '{network_key}'")

    if pkh:
        entry = manager_wallet_data.get(pkh)
        if not entry:
            raise ManagerWalletError(f"no wallet data for pkh: {pkh}")
    else:
        entry = _first_wallet_entry(manager_wallet_data)

    private_key = entry.get("private_key")
    if not isinstance(private_key, str):
        raise ManagerWalletError("manager wallet entry must include a private_key")

    signing_key = PaymentSigningKey.from_primitive(bytes.fromhex(private_key))
    verification_key = signing_key.to_verification_key()
    address = Address(verification_key.hash(), network=network)

    wallet = ManagerWallet(
        signing_key=signing_key,
        verification_key=verification_key,
        address=address,
    )
    _cached[pkh] = wallet
    return wallet
