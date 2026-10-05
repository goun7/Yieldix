"""
Yieldix ↔ TamgaProtocol mesh-anchor testleri.

Kanıt-imzalarının (AT-077) Tamga'nın hash-zincirine bayt-uyumlu
sabitlenmesini doğrular. Üç bağımsız doğrulama katmanı:

1. Yieldix'in kendi zincir-yeniden-hesabı ( ``verify_chain``).
2. **Tamga'nın kendi bağımsız verifier'ı** ( ``tests/conformance/verify.py``)
   — bu, RFC 8785 JCS bayt-paritesinin tek-gerçek kanıtıdır: verifier
   ``sha256(prev ‖ jcs(rec))``'yi kendi JCS uygulamasıyla yeniden hesaplar,
   GREEN çıkması ancak bayt-bayt aynı canonicalization ile mümkündür.
3. ``tamga_canon.jcs`` ile doğrudan bayt-paritesi ( edge-case corpus).

Tamga kurulumu yoksa 2/3 katman skip'lenir ( zarar vermez); 1. katman her
zaman çalışır.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from yieldix.core.types import MonthlyReportPayload
from yieldix.crypto.hasher import sha256_digest_hex
from yieldix.crypto.signer import Ed25519ReportSigner
from yieldix.telemetry.reporter import MonthlyReportGenerator
from yieldix.mesh.tamga_anchor import (
    ANCHOR_OP,
    KAYNAK_PROJE,
    TAMGA_GENESIS_H,
    BozukTamgaZinciriError,
    KanitTamgaSabitleyici,
    TamgaLedger,
    anchor_report,
    jcs,
    sabitle_raporlar,
    verify_chain,
)

# --- Tamga kurulumunu keşfet ( varsa gerçek parite-testi için) -------------
_YIELDIX_ROOT = Path(__file__).resolve().parent.parent


def _tamga_root() -> Path | None:
    """TamgaProtocol kök dizinini keşfet: env → göreli-yol → mutlak-yol."""
    adaylar = [
        os.environ.get("TAMGA_ROOT"),
        str(_YIELDIX_ROOT.parent.parent / "05_acik_kaynak" / "TamgaProtocol"),
        "/home/gokun/projects/05_acik_kaynak/TamgaProtocol",
    ]
    for a in adaylar:
        if a and Path(a, "tamga_canon.py").is_file():
            return Path(a)
    return None


TAMGA_ROOT = _tamga_root()


def _imzali_rapor(signer: Ed25519ReportSigner, report_id="yrpt_202610_t01",
                  total_leads=120, qualified_sql=45,
                  p95=41.7, tenant_id="tenant-abc") -> MonthlyReportPayload:
    """Gerçek üretim yoluyla imzalı kanıt üret ( signer.sign_dict → AT-077)."""
    payload = {
        "report_id": report_id,
        "tenant_id": tenant_id,
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "total_leads": total_leads,
        "qualified_sql": qualified_sql,
        "p95_speed_to_lead_seconds": p95,
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
        total_leads=total_leads,
        qualified_sql=qualified_sql,
        p95_speed_to_lead_seconds=p95,
        cost_per_lead_try=Decimal("110.50"),
        error_rate_pct=0.85,
        escalation_rate_pct=6.25,
        circuit_breaker_triggered=False,
        active_components=payload["active_components"],
        engine_version="16.0.0",
        sha256_digest=digest,
        ed25519_signature=sig,
    )


def _uc_rapor(signer: Ed25519ReportSigner):
    return [
        _imzali_rapor(signer, "yrpt_202610_t01", 120, 45, 41.7),
        _imzali_rapor(signer, "yrpt_202610_t02", 98, 31, 55.0),
        _imzali_rapor(signer, "yrpt_202610_t03", 150, 52, 38.25),
    ]


# ---------------------------------------------------------------------------
# 1) Zincir bütünlüğü + şema ( her zaman çalışır)
# ---------------------------------------------------------------------------
def test_sabitleme_zinciri_dogrulanir():
    """3 imzalı kanıt → 1-based seq + genesis-prev + hash-tekrar-hesabı."""
    signer = Ed25519ReportSigner()
    s = sabitle_raporlar(_uc_rapor(signer), signer=signer)

    kayitlar = s.tamga.disa_aktar()
    assert len(kayitlar) == 3

    # şema: her kayıt tamga-sim/1 gramerinde
    for n, rec in enumerate(kayitlar, start=1):
        assert rec["seq"] == n
        assert rec["op"] == ANCHOR_OP
        assert rec["kaynak"] == KAYNAK_PROJE
        assert rec["h"] != rec["prev"]
        assert len(rec["h"]) == 64
        assert set(rec) >= {"seq", "prev", "h", "kanit", "sha256_digest",
                            "ed25519_signature", "public_key_hex"}
    assert kayitlar[0]["prev"] == TAMGA_GENESIS_H
    for onceki, sonraki in zip(kayitlar, kayitlar[1:]):
        assert sonraki["prev"] == onceki["h"]

    # bağımsız zincir-yeniden-hesabı GREEN
    tip, reason = verify_chain(kayitlar)
    assert reason == "ok", f"zincir kırık: {reason}"
    assert tip == kayitlar[-1]["h"]
    assert s.dogrula() is True


def test_sabitleme_idempotent_ve_tamlik():
    """sabitle() tekrar çağrıldığında tekrarlı kayıt eklemez; dogrula()
    tamlık kontrolü yapar ( kaçırılmış kanıt → False)."""
    signer = Ed25519ReportSigner()
    raporlar = _uc_rapor(signer)
    s = KanitTamgaSabitleyici(raporlar, signer=signer)

    ozet1 = s.sabitle()
    assert ozet1["sabitlelenen"] == 3
    ozet2 = s.sabitle()
    assert ozet2["sabitlelenen"] == 0  # hepsi zaten sabitli
    assert len(s.tamga) == 3
    assert s.dogrula() is True

    # tamlık: 3 rapordan yalnızca 2'si sabitliyse dogrula() False
    kismi = KanitTamgaSabitleyici(raporlar[:2], signer=signer)
    kismi.sabitle()
    assert len(kismi.tamga) == 2
    s3 = KanitTamgaSabitleyici(raporlar, tamga=kismi.tamga, signer=signer)
    assert s3.dogrula() is False          # 3. rapor sabitlenmemiş
    # ve idempotent- yakalama: eksik raporu tamamlar → sağlam
    assert s3.sabitle()["sabitlelenen"] == 1
    assert s3.dogrula() is True


def test_kanit_imzasi_dogrulanir_ve_kurcalama_yakalanir():
    """Çapraz-çapa imza-bütünlüğü: kayıttaki Ed25519 imzası kanıt içeriğinde
    geçerli olmalı; KPI içeriği kurcalanınca dogrula() → False."""
    signer = Ed25519ReportSigner()
    s = sabitle_raporlar([_imzali_rapor(signer)], signer=signer)
    assert s.dogrula() is True

    rec = s.tamga.entries[0]
    # imza, kayıttaki kanıt içeriği üzerinde gerçekten doğrulanır
    assert Ed25519ReportSigner.verify_signature(
        rec["kanit"], rec["ed25519_signature"], rec["public_key_hex"]
    ) is True
    # digest birebir ( mevcut kripto yüzeyiyle aynı hesap)
    assert sha256_digest_hex(rec["kanit"]) == rec["sha256_digest"]

    # kurcalama: SQL sayısını değiştir → imza artık o içerikte geçersiz
    rec["kanit"]["qualified_sql"] = 999
    assert s.dogrula() is False


def test_zincir_kirilinca_fail_closed(tmp_path):
    """anchor_report kırık bir Tamga zincirine asla kayıt eklemez."""
    signer = Ed25519ReportSigner()
    ledger = tmp_path / "ledger.jsonl"
    anchor_report(_imzali_rapor(signer), ledger, signer=signer)

    # zinciri kır: ilk kaydın KPI içeriğini geriye-dönük değiştir
    satirlar = ledger.read_text(encoding="utf-8").splitlines()
    rec = json.loads(satirlar[0])
    rec["kanit"]["total_leads"] = 0
    # h'yi KURALDIŞI yeniden hesapla ( kurcalama): hash artık zincirle uyumsuz
    satirlar[0] = json.dumps(rec, ensure_ascii=False)
    ledger.write_text("\n".join(satirlar) + "\n", encoding="utf-8")

    with pytest.raises(BozukTamgaZinciriError):
        anchor_report(_imzali_rapor(signer, "yrpt_202610_t02"), ledger,
                      signer=signer)

    # ve hiçbir şey eklenmedi
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_jsonl_roundtrip_fail_closed(tmp_path):
    """jsonl_yaz → jsonl_oku roundtrip doğrular; kurcalı JSONL yüklenmez."""
    signer = Ed25519ReportSigner()
    s = sabitle_raporlar(_uc_rapor(signer), signer=signer)
    p = tmp_path / "ledger.jsonl"
    s.tamga.jsonl_yaz(p)

    geri = TamgaLedger()
    geri.jsonl_oku(p)
    assert len(geri) == 3
    assert geri.verify() is True
    assert [r["h"] for r in geri.entries] == [r["h"] for r in s.tamga.entries]

    # kurcalama: son kaydın seq'sini boz → fail-closed
    satirlar = p.read_text(encoding="utf-8").splitlines()
    rec = json.loads(satirlar[-1])
    rec["seq"] = 99
    satirlar[-1] = json.dumps(rec, ensure_ascii=False)
    p.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    with pytest.raises(BozukTamgaZinciriError):
        TamgaLedger().jsonl_oku(p)


def test_imzasiz_kanit_reddedilir():
    """sha256_digest/ed25519_signature eksik kanıt sabitlenemez ( fail-closed)."""
    signer = Ed25519ReportSigner()
    rapor = _imzali_rapor(signer)
    rapor_imzasiz = rapor.model_copy(update={"sha256_digest": None,
                                             "ed25519_signature": None})
    with pytest.raises(ValueError, match="imzasiz-kanit"):
        sabitle_raporlar([rapor_imzasiz], signer=signer)


def test_mevcut_kripto_yuzey_degismedi():
    """Sabitleme, Yieldix'in mevcut kanıt-imzası modelini DEĞİŞTİRMEZ:
    digest/imza mevcut signer+hasher ile birebir hesaplanır ve doğrulanır."""
    signer = Ed25519ReportSigner()
    rapor = _imzali_rapor(signer)
    s = sabitle_raporlar([rapor], signer=signer)
    rec = s.tamga.entries[0]

    # reporter'ın imzalanabilir dict'i birebir taşınmış ( uydurma değil)
    beklenen = MonthlyReportGenerator.to_signable_dict(rapor)
    assert rec["kanit"] == {k: v for k, v in beklenen.items()}

    # mevcut yüzeyle aynı digest + geçerli imza
    assert rec["sha256_digest"] == sha256_digest_hex(beklenen)
    assert Ed25519ReportSigner.verify_signature(
        beklenen, rapor.ed25519_signature, signer.public_key_hex
    ) is True


# ---------------------------------------------------------------------------
# 2) Tamga'nın KENDİ bağımsız verifier'ı — JCS bayt-paritesinin kanıtı
# ---------------------------------------------------------------------------
@pytest.mark.skipif(TAMGA_ROOT is None, reason="TamgaProtocol kurulu değil")
def test_tamga_kendi_verifierinda_green(tmp_path):
    """Üretilen ledger, Tamga'nın kendi conformance verifier'ında GREEN.

    ``tests/conformance/verify.py`` bağımsız JCS uygulamasıyla
    ``sha256(prev ‖ jcs(rec))``'yi yeniden hesaplar — GREEN çıkması ancak
    bayt-bayt RFC 8785 paritesiyle mümkündür.
    """
    signer = Ed25519ReportSigner()
    s = sabitle_raporlar(_uc_rapor(signer), signer=signer)
    ledger = tmp_path / "yieldix_anchor.jsonl"
    s.tamga.jsonl_yaz(ledger)

    verify_py = TAMGA_ROOT / "tests" / "conformance" / "verify.py"
    proc = subprocess.run(
        [sys.executable, str(verify_py), str(ledger)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"Tamga verifier RED:\n{proc.stdout}\n{proc.stderr}"
    sonuc = json.loads(proc.stdout)
    assert sonuc["ok"] is True
    assert sonuc["reason"] == "ok"
    assert sonuc.get("broken_line") is None


@pytest.mark.skipif(TAMGA_ROOT is None, reason="TamgaProtocol kurulu değil")
def test_tamga_kendi_verifierinda_kirik_zincir_red(tmp_path):
    """Kurcalı ledger, Tamga'nın verifier'ında RED — parite her iki yönde."""
    signer = Ed25519ReportSigner()
    s = sabitle_raporlar([_imzali_rapor(signer)], signer=signer)
    ledger = tmp_path / "broken.jsonl"
    s.tamga.jsonl_yaz(ledger)

    satirlar = ledger.read_text(encoding="utf-8").splitlines()
    rec = json.loads(satirlar[0])
    rec["kanit"]["qualified_sql"] = 999  # geriye-dönük kurcalama
    satirlar[0] = json.dumps(rec, ensure_ascii=False)
    ledger.write_text("\n".join(satirlar) + "\n", encoding="utf-8")

    verify_py = TAMGA_ROOT / "tests" / "conformance" / "verify.py"
    proc = subprocess.run(
        [sys.executable, str(verify_py), str(ledger)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    sonuc = json.loads(proc.stdout)
    assert sonuc["ok"] is False
    assert sonuc["broken_line"] == 1


# ---------------------------------------------------------------------------
# 3) Doğrudan JCS bayt-paritesi ( tamga_canon.jcs ile)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(TAMGA_ROOT is None, reason="TamgaProtocol kurulu değil")
def test_jcs_bayt_paritesi_tamga_canon():
    """``yieldix.mesh.tamga_anchor.jcs`` == ``tamga_canon.jcs`` bayt-bayt.

    RFC 8785 edge-case'leri + gerçek anchor kayıt yükleri.
    """
    sys.path.insert(0, str(TAMGA_ROOT))
    try:
        from tamga_canon import jcs as tamga_jcs
    finally:
        sys.path.pop(0)

    corpus = [
        # §3.2.2.2 ECMAScript number-to-string
        {"a": 1.0, "b": 2.93e-07, "c": 1e16, "d": 1e21, "e": -0.0,
         "f": 1234567890000000.0, "g": 5e-8, "h": -1.5e10},
        # §3.2.3 UTF-16 code-unit sıralaması ( code-point sırasından ayrılır)
        {"A": 1, "Z": 2, "_": 3, "é": 4, "😀": 5},
        # kaçışlar + raw UTF-8 ( non-ASCII kaçışlanmaz)
        {"esc": 'a"b\\c\ntab', "tr": "ğüşıöç", "bmp": "a😀中"},
        {"n": None, "t": True, "f": False, "arr": [1, [2, 3], {"deep": "v"}]},
        # gerçek anchor kayıt yükü
        {"kanit": {"report_id": "yrpt_202610_t01", "tenant_id": "tenant-abc",
                   "total_leads": 120, "qualified_sql": 45,
                   "p95_speed_to_lead_seconds": 41.7,
                   "cost_per_lead_try": "110.50", "error_rate_pct": 0.85,
                   "escalation_rate_pct": 6.25,
                   "circuit_breaker_triggered": False,
                   "active_components": ["c1_receptionist", "c2_speed_to_lead"],
                   "engine_version": "16.0.0"}},
    ]
    for i, obj in enumerate(corpus):
        beklenen = tamga_jcs(obj)
        gercek = jcs(obj)
        assert gercek == beklenen, (
            f"JCS bayt-parite-başarısız case{i}:\n  tamga  ={beklenen!r}"
            f"\n  yieldix={gercek!r}"
        )


def test_jcs_sayi_gosterim_kurallari():
    """RFC 8785 §3.2.2.2 sayı gösterimleri ( dil-bağımsızlık)."""
    assert jcs({"x": 1.0}) == b'{"x":1}'          # Python "1.0" der, JCS "1"
    assert jcs({"x": 2.93e-07}) == b'{"x":2.93e-7}'
    assert jcs({"x": 1e16}) == b'{"x":10000000000000000}'
    assert jcs({"x": 1e21}) == b'{"x":1e+21}'
    assert jcs({"x": -0.0}) == b'{"x":0}'
    # NaN/Inf I-JSON'da değil ( RFC 7493) — sessiz "null" değil RED
    with pytest.raises(ValueError):
        jcs({"x": float("nan")})
    with pytest.raises(ValueError):
        jcs({"x": float("inf")})
    # 2^53 dışı tamsayı ECMAScript Number'da temsil edilemez → RED
    with pytest.raises(ValueError):
        jcs({"x": 2 ** 53 + 1})
