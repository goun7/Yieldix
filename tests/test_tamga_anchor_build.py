"""YENI test: yieldix.mesh.tamga_anchor.build_anchor_record — kanit-imzasi
Yieldix → Tamga hash-zincirine sabitleyen kritik kopru fonksiyonu.

Kapsanan test-disi public fonksiyon (58 satir):
  - build_anchor_record (tamga_anchor.py:295-352)

Mevcut tests/test_tamga_anchor.py bu fonksiyonu DOGRUDAN hic cagirmiyor
(yalnizca sabitle_raporlar/anchor_report uzerinden dolayli). Burada
fonksiyonun KENDI mantigi test edildi: imzasiz kanit reddi (fail-closed),
varsayilan degerler (genesis prev / seq=1), ozellestirilmis seq/ts/issuer,
hash-yeniden-hesaplama paritesi, zincir-merkezleme ve capraz-capa
Ed25519 imza dogrulamasi. HICBIR dis cagri yok (stdlib + yieldic kendi
kripto yuzeyi).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from yieldix.core.types import MonthlyReportPayload
from yieldix.crypto.signer import Ed25519ReportSigner
from yieldix.mesh.tamga_anchor import (
    ANCHOR_OP,
    KAYNAK_PROJE,
    TAMGA_GENESIS_H,
    build_anchor_record,
    compute_record_hash,
    verify_chain,
)
from yieldix.telemetry.reporter import MonthlyReportGenerator


def _imzali_rapor(signer: Ed25519ReportSigner,
                  report_id: str = "yrpt_202610_t99",
                  tenant_id: str = "tenant-abc") -> MonthlyReportPayload:
    """Gercek uretim yoluyla imzali kanit uret (signer.sign_dict)."""
    payload = {
        "report_id": report_id,
        "tenant_id": tenant_id,
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "total_leads": 120,
        "qualified_sql": 45,
        "p95_speed_to_lead_seconds": 41.7,
        "cost_per_lead_try": "110.50",
        "error_rate_pct": 0.85,
        "escalation_rate_pct": 6.25,
        "circuit_breaker_triggered": False,
        "active_components": ["c1_receptionist", "c2_speed_to_lead"],
        "engine_version": "16.0.0",
    }
    digest, sig = signer.sign_dict(payload)
    return MonthlyReportPayload(
        report_id=report_id,
        tenant_id=tenant_id,
        period_start="2026-09-01",
        period_end="2026-09-30",
        total_leads=120,
        qualified_sql=45,
        p95_speed_to_lead_seconds=41.7,
        cost_per_lead_try=Decimal("110.50"),
        error_rate_pct=0.85,
        escalation_rate_pct=6.25,
        circuit_breaker_triggered=False,
        active_components=["c1_receptionist", "c2_speed_to_lead"],
        engine_version="16.0.0",
        sha256_digest=digest,
        ed25519_signature=sig,
    )


@pytest.fixture
def signer():
    return Ed25519ReportSigner()


@pytest.fixture
def rapor(signer):
    return _imzali_rapor(signer)


# ---------------------------------------------------------------------------
# imzasiz kanit reddi (fail-closed)
# ---------------------------------------------------------------------------
def test_imzasiz_kanit_reddedilir_build(signer, rapor):
    """sha256_digest/ed25519_signature eksikse sabitleme yapilmaz (AT-077)."""
    imzasiz = rapor.model_copy(update={"sha256_digest": None,
                                       "ed25519_signature": None})
    with pytest.raises(ValueError, match="imzasiz-kanit"):
        build_anchor_record(imzasiz)


def test_yalnizca_sha_eksikse_reddedilir(signer, rapor):
    eksik = rapor.model_copy(update={"sha256_digest": None})
    with pytest.raises(ValueError, match="imzasiz-kanit"):
        build_anchor_record(eksik)


# ---------------------------------------------------------------------------
# kayit semasi + varsayilan degerler
# ---------------------------------------------------------------------------
def test_varsayilan_degerler_ve_sema(rapor):
    rec = build_anchor_record(rapor)
    assert rec["op"] == ANCHOR_OP
    assert rec["kaynak"] == KAYNAK_PROJE
    assert rec["seq"] == 1
    assert rec["prev"] == TAMGA_GENESIS_H == "0" * 64
    assert rec["report_id"] == rapor.report_id
    assert rec["tenant_id"] == rapor.tenant_id
    assert rec["period_start"] == rapor.period_start
    assert rec["period_end"] == rapor.period_end
    assert rec["sha256_digest"] == rapor.sha256_digest
    assert rec["ed25519_signature"] == rapor.ed25519_signature
    assert rec["public_key_hex"] is None  # verilmezse null (imza dogrulanamaz)
    assert rec["ts"]  # ISO timestamp uretilmeli
    assert "issuer" not in rec  # verilmedikce alan yok
    assert set(rec) >= {"h", "kanit"}


def test_prev_hash_none_genesis_olarak_cozulur(rapor):
    rec = build_anchor_record(rapor, prev_hash=None)
    assert rec["prev"] == TAMGA_GENESIS_H


# ---------------------------------------------------------------------------
# hash-yeniden-hesaplama paritesi (Tamga ile bayt-uyumlu kural)
# ---------------------------------------------------------------------------
def test_hash_bagimsiz_yeniden_hesaplanabilir(rapor):
    """verify_chain/_verify_chain ayni baytlari uretmeli (h degismez)."""
    rec = build_anchor_record(rapor)
    assert rec["h"] == compute_record_hash(rec["prev"], rec)
    assert len(rec["h"]) == 64
    assert all(c in "0123456789abcdef" for c in rec["h"])
    # h, kaydin disinda bir alandir
    assert "h" not in {k for k in rec["kanit"]}


def test_hesaplanan_h_prev_e_bagli(rapor):
    """Aynı kanıt farklı prev → farklı h (zincir sirasi hash'e gomulur)."""
    r1 = build_anchor_record(rapor, prev_hash=TAMGA_GENESIS_H, seq=1)
    r2 = build_anchor_record(rapor, prev_hash="e" * 64, seq=2)
    assert r1["h"] != r2["h"]


# ---------------------------------------------------------------------------
# kanit icerigi (to_signable_dict paritesi)
# ---------------------------------------------------------------------------
def test_kanit_imzalanabilir_dict_birebir_tasinir(rapor):
    """kanit, reporter'in imzalanabilir dict'iyle birebir olmali."""
    rec = build_anchor_record(rapor)
    beklenen = MonthlyReportGenerator.to_signable_dict(rapor)
    assert rec["kanit"] == beklenen
    assert rec["kanit"]["cost_per_lead_try"] == "110.50"  # Decimal → str


# ---------------------------------------------------------------------------
# ozellestirilmis argumanlar
# ---------------------------------------------------------------------------
def test_ozellestirilmis_seq_ts_issuer_public_key(signer, rapor):
    pub = signer.public_key_hex
    ts = "2026-10-07T17:00:00+00:00"
    rec = build_anchor_record(rapor, prev_hash="a" * 64, seq=7, ts=ts,
                              issuer="mesh-lead", public_key_hex=pub)
    assert rec["seq"] == 7
    assert rec["prev"] == "a" * 64
    assert rec["ts"] == ts
    assert rec["issuer"] == "mesh-lead"
    assert rec["public_key_hex"] == pub
    assert rec["h"] == compute_record_hash("a" * 64, rec)


# ---------------------------------------------------------------------------
# zincir merkezleme + tahrirat tespiti
# ---------------------------------------------------------------------------
def test_iki_kayit_zincir_merkezlenir_ve_dogrulanir(rapor):
    r1 = build_anchor_record(rapor, prev_hash=TAMGA_GENESIS_H, seq=1)
    r2 = build_anchor_record(rapor, prev_hash=r1["h"], seq=2, ts=r1["ts"])
    assert r2["prev"] == r1["h"]
    tip, reason = verify_chain([r1, r2])
    assert reason == "ok"
    assert tip == r2["h"]


def test_kurcalanan_kayit_zincir_kirilir(rapor):
    r1 = build_anchor_record(rapor, prev_hash=TAMGA_GENESIS_H, seq=1)
    r2 = build_anchor_record(rapor, prev_hash=r1["h"], seq=2)
    # kanit icerigi degistirilirse h eslesmemeli
    r2["kanit"]["total_leads"] = 9999
    tip, reason = verify_chain([r1, r2])
    assert reason.startswith("broken@")
    assert tip is None


def test_yanlis_seq_zinciri_kirar(rapor):
    r1 = build_anchor_record(rapor, seq=1)
    r2 = build_anchor_record(rapor, prev_hash=r1["h"], seq=5)
    tip, reason = verify_chain([r1, r2])
    assert reason.startswith("broken@")


# ---------------------------------------------------------------------------
# capraz-capa imza dogrulamasi (Yieldix kurmadan dogrulanabilirlik)
# ---------------------------------------------------------------------------
def test_capraz_capa_imza_dogrulanir(signer, rapor):
    """Kaydin tasiydigi imza, kanit icerigi uzerinde dogrulanabilir."""
    rec = build_anchor_record(rapor, public_key_hex=signer.public_key_hex)
    dogru = Ed25519ReportSigner.verify_signature(
        rec["kanit"], rec["ed25519_signature"], rec["public_key_hex"])
    assert dogru is True
    # baska anahtarla dogrulanmamali
    baska = Ed25519ReportSigner()
    yanlis = Ed25519ReportSigner.verify_signature(
        rec["kanit"], rec["ed25519_signature"], baska.public_key_hex)
    assert yanlis is False


def test_public_key_yoksa_imza_dogrulanamaz_ama_zincir_tamdir(rapor):
    """public_key_hex=null → imza dogrulanamaz; zincir-butunlugu yine tam."""
    rec = build_anchor_record(rapor)
    assert rec["public_key_hex"] is None
    tip, reason = verify_chain([rec])
    assert reason == "ok"
    assert tip == rec["h"]
