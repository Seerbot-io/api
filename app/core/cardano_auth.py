"""
Cardano Wallet Authentication Utilities

This module handles Cardano-specific cryptographic operations for wallet authentication.
It implements the signature verification flow using CIP-8 (Cardano Improvement Proposal 8).

Authentication Flow:
1. Backend generates a random nonce -> generate_nonce()
2. Frontend signs the nonce with wallet (CIP-8 signData)
3. Frontend sends: address, nonce, signature, public_key
4. Backend verifies: verify_signature()
   - Verifies ED25519 signature is valid
   - Verifies public key matches the Cardano address
   - Returns normalized address if valid

The signature verification uses:
- ED25519 cryptography (Cardano's signature algorithm)
- pycardano library for address validation and key handling
"""

import base64
import binascii
import secrets
from typing import Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from pycardano import Address
from pycardano.key import VerificationKey


NONCE_NUM_BYTES = 32  # 32 bytes = 64 hex characters


def generate_nonce(num_bytes: int = NONCE_NUM_BYTES) -> str:
    """
    Generate a cryptographically secure random nonce for wallet authentication.
    
    The nonce is a random hex string that the user must sign with their wallet
    to prove ownership. This prevents replay attacks.
    
    Args:
        num_bytes: Number of random bytes to generate (default: 32 = 64 hex chars)
    
    Returns:
        Hex-encoded random string (e.g., "a1b2c3d4...")
    """
    if num_bytes <= 0:
        num_bytes = NONCE_NUM_BYTES
    return secrets.token_hex(num_bytes)


def _decode_hex(value: str) -> bytes:
    """Helper: Decode hex string to bytes."""
    return binascii.unhexlify(value.encode())


def _decode_base64(value: str) -> bytes:
    """Helper: Decode base64 string to bytes."""
    return base64.b64decode(value, validate=True)


def _decode_hex_or_base64(value: str) -> bytes:
    """
    Helper: Decode hex or base64 string to bytes.
    
    Cardano wallets may send signatures/keys in either format, so we support both.
    """
    value = value.strip()
    try:
        return _decode_hex(value)
    except (binascii.Error, ValueError):
        try:
            return _decode_base64(value)
        except (binascii.Error, ValueError):
            raise ValueError("Value must be hex or base64 encoded")


def _message_from_nonce(nonce: str) -> bytes:
    """
    Helper: Convert nonce string to bytes for signature verification.
    
    Tries to decode as hex first, falls back to UTF-8 encoding.
    """
    nonce = nonce.strip()
    try:
        return _decode_hex(nonce)
    except (binascii.Error, ValueError):
        return nonce.encode()


def _public_key_matches_address(address: str, public_key_bytes: bytes) -> bool:
    """
    Helper: Verify that the public key corresponds to the Cardano address.
    
    This ensures the signature was created by the wallet that owns the address.
    Uses pycardano to decode the address and compare payment part hash with key hash.
    
    Args:
        address: Cardano address string (e.g., "addr1...")
        public_key_bytes: ED25519 public key as bytes
    
    Returns:
        True if public key matches address, False otherwise
    """
    try:
        addr = Address.decode(address)
        v_key = VerificationKey.from_primitive(public_key_bytes)
        return addr.payment_part == v_key.hash()
    except Exception:
        return False


def verify_signature(address: str, nonce: str, signature: str, public_key: str) -> Tuple[bool, str]:
    """
    Verify a Cardano wallet signature and return normalized address.
    
    This is the main function called by /auth/verify endpoint. It performs three checks:
    1. Verifies the ED25519 signature is cryptographically valid
    2. Verifies the public key matches the provided Cardano address
    3. Normalizes the address to canonical format
    
    Args:
        address: Cardano wallet address (e.g., "addr1...")
        nonce: The nonce string that was signed
        signature: ED25519 signature (hex or base64 encoded)
        public_key: ED25519 public key (hex or base64 encoded)
    
    Returns:
        Tuple of (is_valid: bool, normalized_address: str)
        - If valid: (True, normalized_address)
        - If invalid: (False, "")
    
    Example:
        is_valid, addr = verify_signature(
            address="addr1...",
            nonce="a1b2c3...",
            signature="sig_hex_or_base64",
            public_key="pubkey_hex_or_base64"
        )
        if is_valid:
            # Create JWT token for addr
    """
    # Decode signature, public key, and nonce to bytes
    signature_bytes = _decode_hex_or_base64(signature)
    public_key_bytes = _decode_hex_or_base64(public_key)
    message_bytes = _message_from_nonce(nonce)

    # Step 1: Verify ED25519 signature is cryptographically valid
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature_bytes, message_bytes)
    except InvalidSignature:
        return False, ""

    # Step 2: Verify public key matches the provided address
    if not _public_key_matches_address(address, public_key_bytes):
        return False, ""

    # Step 3: Normalize address to canonical format
    try:
        normalized_address = Address.decode(address).encode()
    except Exception:
        return False, ""

    return True, normalized_address

