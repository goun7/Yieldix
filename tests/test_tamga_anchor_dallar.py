"""
Dal-kesen ( branch-cutting) testler: yieldix.mesh.tamga_anchor ( ledger +
sabitleyici + anchor_report katmani)

Mevcut testlerin kapsamadigi hata-dallarini keser ( JCS-dallari
test_tamga_anchor_jcs_dallar.py'de ayrica dusunulmustur).

DAL LISTESI (her dal icin en az bir test):
  [jcs _encode]
    J1  bool alt-sinifi ornegi — savunma-dali ( 208-209: bool int'in
       alt-sinifidir; True/False-tekil-nesnelerinden ayri)
  [verify_chain]
    L1  istisna-dali ( 376-377): jcs-desteklenmeyen-tip → broken@N
  [TamgaLedger.verify]
    L2  seq-uyumsuzlugu → False ( 434)
    L3  prev-baglanti-uyumsuzlugu → False ( 436)
  [TamgaLedger.yukle — fail-closed]
    L4  seq/prev/h tip-kontrolu → BozukTamgaZinciriError ( 449-452)
    L5  seq-sirasi-bozuk → BozukTamgaZinciriError ( 454-457)
    L6  prev-baglanti-bozuk → BozukTamgaZinciriError ( 458-461)
    L7  h-dogrulamasi-basarisiz → BozukTamgaZinciriError ( 462-466)
    L8  jsonl_oku bos-satir-atlar ( 501->499) + fail-closed-yukleme
  [KanitTamgaSabitleyici.__init__]
    S1  public_key_hex direkt-verilirse ( 538)
    S2  hem-pk-hem-signer-YOK → None ( 542)
    S3  mevcut-ledger'da yabanci-op kayitlari → yalnizca anchor-op'lar
       toplanir ( 546->545)
  [KanitTamgaSabitleyici.dogrula]
    S4  yabanci-kayitlar atlanir-ve-zincir-saglam ( 622 continue)
    S5  kanit dict-degil → False ( 626)
    S6  sha256-digest uyumsuzlugu → False ( 628)
    S7  imza/anahtar tip-dogrulama → False ( 632)
    S8  gecersiz-Ed25519-imzasi → False ( 634)
    S9  ozet() — denetim-raporu-anahtarlari ( 646)
  [anchor_report]
    S10 mevcut-gecerli-zincire-ekleme ( 684->689: raise-YOK, seq-2)
    S11 public_key_hex-verilirse ( 692->695: signer-YOK-dali)
    S12 bos-satirli-ledger-dosyasi okuma ( 680->678)
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from yieldix.core.types import MonthlyReportPayload
from yieldix.crypto.hasher import sha256_digest_hex
from yieldix.crypto.signer import Ed25519ReportSigner
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
from yieldix.telemetry.reporter import MonthlyReportGenerator


def _imzali_rapor(signer: Ed25519ReportSigner, report_id="yrpt_dallar_01",
                  total_leads=120, qualified_sql=45,
                  tenant_id="tenant-dallar") -> MonthlyReportPayload:
    """Gerçek imza-yoluyla kanit uret ( signer.sign_dict — AT-077)."""
    payload = {
        "report_id": report_id,
        "tenant_id": tenant_id,
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "total_leads": total_leads,
        "qualified_sql": qualified_sql,
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
        total_leads=total_leads,
        qualified_sql=qualified_sql,
        p95_speed_to_lead_seconds=41.7,
        cost_per_lead_try=Decimal("110.50"),
        error_rate_pct=0.85,
        escalation_rate_pct=6.25,
        circuit_breaker_triggered=False,
        active_components=payload["active_components"],
        engine_version="16.0.0",
        sha256_digest=digest,
        ed25519_signature=sig,
    )


class TestJcsBoolDallari:
    """jcs — bool serilestirme dallari (J1).

    BULGU ( YIELDIX-3): _encode icindeki ``elif isinstance(o, bool)``
    savunma-dali ( satir 208-209) olculemez-oldugundan ÖLÜ-KOD'dur —
    modern-Python'da ``bool`` alt-siniflandirilamaz ( TypeError: type
    'bool' is not an acceptable base type) ve her-bool-degeri `is True`/
    `is False` tekil-nesnelerinden-biridir. Bu test gercekte-calisan
    dallari ( 204-207) keser; 208-209 erisilemez ( uretime-dokunulmadi).
    """

    def test_j1_bool_true_false_ayri_serilesir(self):
        assert jcs({"a": True, "b": False}) == b'{"a":true,"b":false}'
        # bool → true/false, int → rakam ( 210-dalina KAYMAZ)
        assert jcs({"a": True}) != b'{"a":1}'
        assert jcs({"a": False}) != b'{"a":0}'

    def test_j1b_bool_alt_siniflandirilamaz_olu_kod_kaniti(self):
        # bool alt-sinifi Python'da YOK → 208-209-dali erisilemez
        with pytest.raises(TypeError):
            type("TrueAlt", (bool,), {})


class TestVerifyChainIstisnaDali:
    """verify_chain — istisna-dalı fail-closed (L1)."""

    def test_l1_jcs_desteklenmeyen_tip_broken(self):
        # kanit icinde desteklenmeyen-tip ( object) → jcs TypeError
        # → except-dalı: ( None, "broken@N") — sessiz-geçiş YOK
        kayit = {
            "op": ANCHOR_OP,
            "seq": 1,
            "prev": TAMGA_GENESIS_H,
            "h": "ab" * 32,
            "kaynak": KAYNAK_PROJE,
            "kanit": object(),  # jcs-desteklenmeyen-tip
        }
        tip, sebep = verify_chain([kayit])
        assert tip is None
        assert sebep == "broken@1"

    def test_l2_gecerli_zincir_ok(self):
        # saglikli-zemin: dogru-zincir "ok" donmeli
        signer = Ed25519ReportSigner()
        s = sabitle_raporlar([_imzali_rapor(signer)], signer=signer)
        tip, sebep = verify_chain(s.tamga.disa_aktar())
        assert sebep == "ok"
        assert tip == s.tamga.tip()


class TestLedgerVerifyDallari:
    """TamgaLedger.verify — seq/prev uyumsuzluk dallari (L2-L3)."""

    def _ledger(self) -> TamgaLedger:
        l = TamgaLedger()
        l.append({"op": ANCHOR_OP, "kaynak": KAYNAK_PROJE, "payload": "x"})
        return l

    def test_l2_seq_bozuklugu_false(self):
        l = self._ledger()
        l.entries[0]["seq"] = 99  # kurcala
        assert l.verify() is False

    def test_l3_prev_baglantisi_bozuk_false(self):
        l = self._ledger()
        l.entries[0]["prev"] = "ff" * 32  # kurcala
        assert l.verify() is False


class TestLedgerYukleFailClosed:
    """TamgaLedger.yukle — bozuk-zincir belleğe HİÇ girmez (L4-L8)."""

    def test_l4_tip_kontrolu_seq_str_h_none(self):
        l = TamgaLedger()
        for hatali in (
            {"seq": "1", "prev": TAMGA_GENESIS_H, "h": "ab" * 32},   # seq str
            {"seq": 1, "prev": TAMGA_GENESIS_H, "h": None},          # h None
            {"seq": 1.0, "prev": TAMGA_GENESIS_H, "h": "ab" * 32},   # seq float
            {"seq": 1, "prev": 64, "h": "ab" * 32},                  # prev int
        ):
            with pytest.raises(BozukTamgaZinciriError):
                l.yukle([hatali])
        assert len(l) == 0  # hicbir-kayit-bellege-girmedi

    def test_l5_seq_sirasi_bozuk(self):
        l = TamgaLedger()
        kayit = {"seq": 2, "prev": TAMGA_GENESIS_H, "h": "ab" * 32,
                 "op": ANCHOR_OP, "kaynak": KAYNAK_PROJE}
        with pytest.raises(BozukTamgaZinciriError, match="seq-sırası"):
            l.yukle([kayit])
        assert len(l) == 0

    def test_l6_prev_baglantisi_bozuk(self):
        l = TamgaLedger()
        gecerli = l.append({"op": ANCHOR_OP, "kaynak": KAYNAK_PROJE})
        ikinci = dict(gecerli)
        ikinci["seq"] = 2
        ikinci["prev"] = "cc" * 32  # yanlis-prev ( dogrusu gecerli["h"])
        ikinci["h"] = l._hashla(2, "cc" * 32,
                                {k: v for k, v in ikinci.items()
                                 if k not in ("h",)})
        with pytest.raises(BozukTamgaZinciriError, match="prev-bağlantısı"):
            l.yukle([ikinci])
        assert len(l) == 1  # ikinci-kayit-almadi

    def test_l7_h_dogrulamasi_basarisiz(self):
        l = TamgaLedger()
        kayit = {"seq": 1, "prev": TAMGA_GENESIS_H, "h": "00" * 32,
                 "op": ANCHOR_OP, "kaynak": KAYNAK_PROJE}
        with pytest.raises(BozukTamgaZinciriError, match="h-doğrulaması"):
            l.yukle([kayit])
        assert len(l) == 0

    def test_l8_jsonl_oku_bos_satir_atlar(self, tmp_path):
        # jsonl_yaz + elle-bos-satir → bos-satir-atlanip-yuklenir ( 501->499)
        l = TamgaLedger()
        l.append({"op": ANCHOR_OP, "kaynak": KAYNAK_PROJE, "x": 1})
        l.append({"op": ANCHOR_OP, "kaynak": KAYNAK_PROJE, "x": 2})
        yol = tmp_path / "ledger.jsonl"
        kayitlar = l.disa_aktar()
        # araya ve sona bos-satir koy
        icerik = (json.dumps(kayitlar[0], ensure_ascii=False) + "\n\n"
                  + json.dumps(kayitlar[1], ensure_ascii=False) + "\n\n")
        yol.write_text(icerik, encoding="utf-8")

        l2 = TamgaLedger()
        l2.jsonl_oku(yol)
        assert len(l2) == 2
        assert l2.tip() == l.tip()
        assert l2.verify() is True


class TestSabitleyiciKurucuDallari:
    """KanitTamgaSabitleyici.__init__ — public_key-cozum dallari (S1-S3)."""

    def test_s1_public_key_hex_direkt(self):
        s = KanitTamgaSabitleyici([], public_key_hex="pk-dallar-01")
        assert s.public_key_hex == "pk-dallar-01"

    def test_s2_hicbiri_yok_none_ve_dogrulama_false(self):
        signer = Ed25519ReportSigner()
        raporlar = [_imzali_rapor(signer)]
        s = KanitTamgaSabitleyici(raporlar)  # pk da signer da YOK
        assert s.public_key_hex is None
        ozet = s.sabitle()
        assert ozet["sabitlelenen"] == 1
        # kayitta public_key_hex None → imza-dogrulanamaz → dogrula() False
        assert s.dogrula() is False

    def test_s3_mevcut_ledger_yabanci_kayitlar_atilmaz(self):
        signer = Ed25519ReportSigner()
        rep = _imzali_rapor(signer)
        ledger = TamgaLedger()
        # yabanci-op kaydi ( bizim-anchor-op'umuz DEGIL)
        ledger.append({"op": "baska.modul.op", "kaynak": "baska-proje",
                       "payload": 1})
        s = KanitTamgaSabitleyici([rep], tamga=ledger, signer=signer)
        # ctor yalnizca anchor-op'lari toplar → yabanci-dislanmis
        assert s._sabitlenen == set()
        ozet = s.sabitle()
        assert ozet["sabitlelenen"] == 1
        assert s._sabitlenen == {rep.report_id}
        assert len(s.tamga) == 2


class TestSabitleyiciDogrulaDallari:
    """KanitTamgaSabitleyici.dogrula — 3-katmanli-dogrulama hata-dallari
    (S4-S8)."""

    def _anchor_kaydi(self, kanit, sha256_digest, sig, pk, report_id="r1"):
        """Elle-craft edilmis anchor-kaydi ( kurcalama-similasyonu)."""
        return {
            "op": ANCHOR_OP,
            "kaynak": KAYNAK_PROJE,
            "ts": "2026-10-15T00:00:00+00:00",
            "report_id": report_id,
            "tenant_id": "tenant-dallar",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "kanit": kanit,
            "sha256_digest": sha256_digest,
            "ed25519_signature": sig,
            "public_key_hex": pk,
        }

    def test_s4_yabanci_kayitlar_atlanir_saglam(self):
        signer = Ed25519ReportSigner()
        rep = _imzali_rapor(signer)
        ledger = TamgaLedger()
        ledger.append({"op": "baska.modul.op", "kaynak": "baska-proje",
                       "payload": 1})
        s = KanitTamgaSabitleyici([rep], tamga=ledger, signer=signer)
        s.sabitle()
        # yabanci-kayit atlanir ( 622 continue), rapor-dogrulanir → True
        assert s.dogrula() is True

    def test_s5_kanit_dict_degil_false(self):
        signer = Ed25519ReportSigner()
        rep = _imzali_rapor(signer)
        kanit = MonthlyReportGenerator.to_signable_dict(rep)
        kayit = self._anchor_kaydi(kanit="kanit-metin-degil",
                                   sha256_digest=rep.sha256_digest,
                                   sig=rep.ed25519_signature,
                                   pk=signer.public_key_hex)
        ledger = TamgaLedger()
        ledger.append({k: v for k, v in kayit.items() if k != "h"})
        s = KanitTamgaSabitleyici([], tamga=ledger, signer=signer)
        assert s.dogrula() is False

    def test_s6_sha256_uyumsuzlugu_false(self):
        signer = Ed25519ReportSigner()
        rep = _imzali_rapor(signer)
        kanit = MonthlyReportGenerator.to_signable_dict(rep)
        kayit = self._anchor_kaydi(kanit=kanit,
                                   sha256_digest="ff" * 32,  # kurcalanmis
                                   sig=rep.ed25519_signature,
                                   pk=signer.public_key_hex)
        ledger = TamgaLedger()
        ledger.append({k: v for k, v in kayit.items() if k != "h"})
        s = KanitTamgaSabitleyici([], tamga=ledger, signer=signer)
        assert s.dogrula() is False

    def test_s7_imza_anahtar_tip_dogrulama_false(self):
        signer = Ed25519ReportSigner()
        rep = _imzali_rapor(signer)
        kanit = MonthlyReportGenerator.to_signable_dict(rep)
        for sig, pk in [(None, signer.public_key_hex),   # sig None
                        (rep.ed25519_signature, None),   # pk None
                        (rep.ed25519_signature, 12345)]:  # pk int
            kayit = self._anchor_kaydi(kanit=kanit,
                                       sha256_digest=rep.sha256_digest,
                                       sig=sig, pk=pk)
            ledger = TamgaLedger()
            ledger.append({k: v for k, v in kayit.items() if k != "h"})
            s = KanitTamgaSabitleyici([], tamga=ledger, signer=signer)
            assert s.dogrula() is False

    def test_s8_gecersiz_ed25519_imzasi_false(self):
        signer_a = Ed25519ReportSigner()
        signer_b = Ed25519ReportSigner()  # farkli-anahtar
        rep = _imzali_rapor(signer_a)
        kanit = MonthlyReportGenerator.to_signable_dict(rep)
        # imza A'ya-ait ama kayit B'nin acik-anahtarini tayiyor
        kayit = self._anchor_kaydi(kanit=kanit,
                                   sha256_digest=sha256_digest_hex(kanit),
                                   sig=rep.ed25519_signature,
                                   pk=signer_b.public_key_hex)
        ledger = TamgaLedger()
        ledger.append({k: v for k, v in kayit.items() if k != "h"})
        s = KanitTamgaSabitleyici([], tamga=ledger, signer=signer_a)
        assert s.dogrula() is False

    def test_s9_ozet_denetim_anahtarlari(self):
        signer = Ed25519ReportSigner()
        raporlar = [_imzali_rapor(signer), _imzali_rapor(
            signer, report_id="yrpt_dallar_02", total_leads=55)]
        s = sabitle_raporlar(raporlar, signer=signer)
        o = s.ozet()
        assert set(o) >= {"kaynak_rapor", "tamga_kayit", "sabitlenen",
                          "tamga_tip", "tamga_format", "dogru"}
        assert o["kaynak_rapor"] == 2
        assert o["tamga_kayit"] == 2
        assert o["sabitlenen"] == 2
        assert o["tamga_format"] == "tamga-sim/1"
        assert o["dogru"] is True
        assert len(o["tamga_tip"]) == 64


class TestAnchorReportDallari:
    """anchor_report — mevcut-zincire-ekleme + anahtar-cozum dallari
    (S10-S12)."""

    def test_s10_mevcut_gecerli_zincire_ekleme(self, tmp_path):
        signer = Ed25519ReportSigner()
        yol = tmp_path / "anchor.jsonl"
        rep1 = _imzali_rapor(signer, report_id="yrpt_a1")
        rep2 = _imzali_rapor(signer, report_id="yrpt_a2")
        k1 = anchor_report(rep1, yol, public_key_hex=signer.public_key_hex)
        # 684->689: mevcut-zincir-gecerli → raise-YOK → uzerine-eklenir
        k2 = anchor_report(rep2, yol, public_key_hex=signer.public_key_hex)
        assert k2["seq"] == 2
        assert k2["prev"] == k1["h"]
        satirlar = yol.read_text(encoding="utf-8").strip().splitlines()
        assert len(satirlar) == 2
        # bagimsiz-yeniden-dogrulama
        kayitlar = [json.loads(s) for s in satirlar]
        tip, sebep = verify_chain(kayitlar)
        assert sebep == "ok"
        assert tip == k2["h"]

    def test_s11_public_key_hex_verilirse_signer_yok(self, tmp_path):
        signer = Ed25519ReportSigner()
        rep = _imzali_rapor(signer)
        yol = tmp_path / "anchor2.jsonl"
        # 692->695: public_key_hex-verildi → signer-dalina-GIRMEZ
        k = anchor_report(rep, yol, public_key_hex="pk-tek-basina")
        assert k["public_key_hex"] == "pk-tek-basina"
        assert ("ed25519_signature" in k) and k["ed25519_signature"]

    def test_s12_bos_satirli_ledger_dosyasi_okunur(self, tmp_path):
        signer = Ed25519ReportSigner()
        yol = tmp_path / "anchor3.jsonl"
        rep1 = _imzali_rapor(signer, report_id="yrpt_b1")
        k1 = anchor_report(rep1, yol, public_key_hex=signer.public_key_hex)
        # dosyaya elle-bos-satir ekle ( 680->678)
        icerik = yol.read_text(encoding="utf-8")
        yol.write_text("\n" + icerik + "\n\n", encoding="utf-8")
        rep2 = _imzali_rapor(signer, report_id="yrpt_b2")
        # bos-satirler-atlanir → mevcut-zincir-ok → ekleme-yapilir
        k2 = anchor_report(rep2, yol, public_key_hex=signer.public_key_hex)
        assert k2["seq"] == 2
        assert k2["prev"] == k1["h"]

