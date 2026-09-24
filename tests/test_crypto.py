"""
Tests for Ed25519 Asymmetric Cryptography and SHA-256 Digesting.
"""

from decimal import Decimal

from yieldix.crypto.hasher import canonical_json_bytes, sha256_digest_hex
from yieldix.crypto.signer import Ed25519ReportSigner


def test_canonical_json_deterministic():
    payload_a = {"b": 2, "a": 1, "z": [3, 2, 1]}
    payload_b = {"a": 1, "z": [3, 2, 1], "b": 2}
    bytes_a = canonical_json_bytes(payload_a)
    bytes_b = canonical_json_bytes(payload_b)
    assert bytes_a == bytes_b
    assert sha256_digest_hex(payload_a) == sha256_digest_hex(payload_b)


def test_canonical_json_unsupported_type():
    import pytest
    with pytest.raises(TypeError):
        canonical_json_bytes({"bad": object()})


def test_ed25519_sign_and_verify():
    signer = Ed25519ReportSigner()
    payload = {
        "report_id": "yrpt_202610_cust01",
        "total_leads": 120,
        "qualified_sql": 45,
        "cost_per_lead_try": Decimal("110.50"),
    }

    digest_hex, sig_hex = signer.sign_dict(payload)
    assert len(digest_hex) == 64
    assert len(sig_hex) == 128

    # Verify valid
    is_valid = Ed25519ReportSigner.verify_signature(
        payload=payload,
        signature_hex=sig_hex,
        public_key_hex=signer.public_key_hex,
    )
    assert is_valid is True

    # Tamper test
    tampered_payload = payload.copy()
    tampered_payload["qualified_sql"] = 999  # Fake SQL count
    is_tampered_valid = Ed25519ReportSigner.verify_signature(
        payload=tampered_payload,
        signature_hex=sig_hex,
        public_key_hex=signer.public_key_hex,
    )
    assert is_tampered_valid is False
