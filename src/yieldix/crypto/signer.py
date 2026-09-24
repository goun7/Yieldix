"""
Yieldix Ed25519 Asymmetric Cryptographic Signer & Verifier.
Compliant with RFC 8032 and Mergen Journal Integrity.
"""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric import ed25519

from yieldix.crypto.hasher import canonical_json_bytes, sha256_digest_hex


class Ed25519ReportSigner:
    """
    Signs and verifies monthly SLA reports using genuine Ed25519 asymmetric cryptography.
    """

    def __init__(self, private_key: ed25519.Ed25519PrivateKey | None = None):
        self._private_key = private_key or ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

    @property
    def public_key_hex(self) -> str:
        from cryptography.hazmat.primitives import serialization
        raw_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return raw_bytes.hex()

    def sign_dict(self, payload: dict) -> tuple[str, str]:
        """
        Hashes canonical payload and signs it.
        Returns: (sha256_digest_hex, ed25519_signature_hex)
        """
        digest_hex = sha256_digest_hex(payload)
        payload_bytes = canonical_json_bytes(payload)
        signature_bytes = self._private_key.sign(payload_bytes)
        return digest_hex, signature_bytes.hex()

    @staticmethod
    def verify_signature(payload: dict, signature_hex: str, public_key_hex: str) -> bool:
        """
        Verifies an Ed25519 signature against payload bytes.
        """
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric import ed25519

            pub_bytes = bytes.fromhex(public_key_hex)
            sig_bytes = bytes.fromhex(signature_hex)
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            payload_bytes = canonical_json_bytes(payload)
            pub_key.verify(sig_bytes, payload_bytes)
            return True
        except (InvalidSignature, ValueError):
            return False
