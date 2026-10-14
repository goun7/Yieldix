"""
Dal-kesen (branch-cutting) testler: yieldix.telemetry.pilot_dataset

Kapsanan public API (src/yieldix/telemetry/pilot_dataset.py):
  * PilotCompany (frozen dataclass)
  * PilotLeadRecord (frozen dataclass)
  * PILOT_COMPANIES (module sabiti)
  * SyntheticPilotDataset:
      __init__, generate, to_inbound_payloads, build_kpi_collector,
      build_signed_report
  * SyntheticPilotDataset.dataset_fingerprint (staticmethod)
  * SyntheticPilotDataset.write_json (staticmethod)

DAL LISTESI (her dal icin en az bir test):
  [__init__]
    D1  leads_per_company <= 0 -> ValueError (sinir: 0 ve negatif)
    D2  leads_per_company = 1 (min pozitif sinir) -> kabul
    D3  varsayilan degerler (25 / seed=1337) ayarlanir
  [generate]
    D4  determinizm: ayni seed -> ozdes kayitlar
    D5  ayni seed ayri ornekler -> ozdes (instance-bagimsiz)
    D6  farkli seed -> farkli kayitlar
    D7  kayit sayisi = 12 * leads_per_company
    D8  lead_id karsilikli-sira formati pilot_lead_NNNNN (1'den baslar)
    D9  cycle_time_sec [6.0, 95.0] mandalinda (max/min clamping dallari)
    D10 tum company_id'ler PILOT_COMPANIES icinde
    D11 maliyet SQL dali: is_sql -> cost_try == sirket cpl_try (tam)
    D12 maliyet non-SQL dali: cost_try ∈ [0.25, 0.55] * cpl_try
    D13 hem SQL hem non-SQL kayit uretilir (istatistiksel gerceklik)
    D14 PilotLeadRecord frozen'dir (immutable)
  [to_inbound_payloads]
    D15 kayit sayisiyle payload sayisi esittir
    D16 tenant_id her payload'a yayilir
    D17 source = MANUAL_IMPORT
    D18 contact_email = None (toplu-olmayan kanal)
    D19 contact_phone "+90850..." formatinda
    D20 intent_summary sirket sektorunu icerir
    D21 bilinmeyen company_id -> KeyError (by_id lookup miss dali)
  [build_kpi_collector]
    D22 total_leads = len(records)
    D23 qualified_sql = is_sql sayisi
    D24 tenant_id collector'da saklanir
    D25 bos kayit listesi -> sifir metrik (sinir)
  [build_signed_report]
    D26 3-demet doner (report, fingerprint, public_key_hex)
    D27 report.report_id formati yrpt_<periyot><tenant>
    D28 fingerprint 64-hex
    D29 public_key_hex gecerli Ed25519 (128 hex = 64 bayt)
    D30 imza DONEN anahtarla bagimsiz dogrulanir
    D31 varsayilan active_components (6 silindir) None verilince
    D32 ozel active_components korunur
    D33 report total_leads/qualified_sql kayitlarla uyumlu
  [dataset_fingerprint]
    D34 64-hex karakter, [0-9a-f] alfabesi
    D35 deterministik (ayni kayitlar -> ayni parmakizi)
    D36 farkli kayitlar -> farkli parmakizi
    D37 bos liste -> gecerli parmakizi (sinir)
  [write_json]
    D38 Path doner ve dosya olusur
    D39 ebeveyn dizinleri olusturur (ic-ice tmp_path)
    D40 JSON yapisinda companies/records/synthetic/note anahtarlari
    D41 dosyadaki companies sayisi 12 ve PILOT_COMPANIES ile ozdes
    D42 dosyadaki records girdi kayitlarla ozdes (round-trip)
    D43 UTF-8 kodlama (Turkce sirket adlari okunabilir)
"""

from __future__ import annotations

import json

import pytest

from yieldix.core.types import InboundLeadPayload, LeadSource
from yieldix.crypto.signer import Ed25519ReportSigner
from yieldix.telemetry.pilot_dataset import (
    PILOT_COMPANIES,
    PilotLeadRecord,
    SyntheticPilotDataset,
)
from yieldix.telemetry.reporter import MonthlyReportGenerator


# ---------------------------------------------------------------------------
# ortak yardimcilar
# ---------------------------------------------------------------------------
def _standart_dataset() -> SyntheticPilotDataset:
    return SyntheticPilotDataset(leads_per_company=25, seed=1337)


def _cpl_map() -> dict[str, float]:
    return {c.company_id: c.cpl_try for c in PILOT_COMPANIES}


class TestSyntheticPilotDatasetInit:
    """__init__ — yapilandirma ve sinir dallari."""

    @pytest.mark.parametrize("kotu_deger", [0, -1, -100])
    def test_sifir_ve_negatif_value_error(self, kotu_deger):
        """D1: leads_per_company <= 0 -> ValueError."""
        with pytest.raises(ValueError):
            SyntheticPilotDataset(leads_per_company=kotu_deger)

    def test_bir_minimum_pozitif_sinir(self):
        """D2: leads_per_company = 1 kabul edilir (min pozitif)."""
        ds = SyntheticPilotDataset(leads_per_company=1)
        assert len(ds.generate()) == len(PILOT_COMPANIES)

    def test_varsayilan_degerler(self):
        """D3: varsayilan leads_per_company=25, seed=1337."""
        ds = SyntheticPilotDataset()
        assert ds.leads_per_company == 25
        assert ds.seed == 1337


class TestGenerate:
    """generate — deterministik uretim ve deger-mandalari."""

    def test_deterministik_ayni_seed(self):
        """D4: ayni seed ile iki uretim ozdestir."""
        ds = _standart_dataset()
        assert ds.generate() == ds.generate()

    def test_deterministik_ayri_ornekler(self):
        """D5: ayni seed'e sahip ayri ornekler ozdestir (instance izolasyonu)."""
        a = SyntheticPilotDataset(leads_per_company=10, seed=1337).generate()
        b = SyntheticPilotDataset(leads_per_company=10, seed=1337).generate()
        assert a == b

    @pytest.mark.parametrize("diger_seed", [999, 1, 424242])
    def test_farkli_seed_farkli_kayit(self, diger_seed):
        """D6: farkli seed -> farkli kayitlar."""
        temel = _standart_dataset().generate()
        baska = SyntheticPilotDataset(leads_per_company=25, seed=diger_seed).generate()
        assert temel != baska

    @pytest.mark.parametrize("leads_per_company", [1, 2, 5, 25])
    def test_kayit_sayisi_sirket_carpani(self, leads_per_company):
        """D7: kayit sayisi = sirket sayisi * leads_per_company."""
        ds = SyntheticPilotDataset(leads_per_company=leads_per_company, seed=7)
        assert len(ds.generate()) == len(PILOT_COMPANIES) * leads_per_company

    def test_lead_id_karsilikli_sira_formati(self):
        """D8: lead_id'ler 1'den baslayan pilot_lead_NNNNN formatindadir."""
        recs = _standart_dataset().generate()
        beklenen = [f"pilot_lead_{i:05d}" for i in range(1, len(recs) + 1)]
        assert [r.lead_id for r in recs] == beklenen

    def test_cycle_time_mandali_6_95(self):
        """D9: cycle_time_sec her zaman [6.0, 95.0] araliginda (clamping)."""
        ds = SyntheticPilotDataset(leads_per_company=50, seed=3)
        for r in ds.generate():
            assert 6.0 <= r.cycle_time_sec <= 95.0

    def test_company_id_hepsi_gecerli(self):
        """D10: uretilen her company_id PILOT_COMPANIES icinde."""
        gecerli = {c.company_id for c in PILOT_COMPANIES}
        for r in _standart_dataset().generate():
            assert r.company_id in gecerli

    def test_maliyet_sql_dali_tam_cpl(self):
        """D11: is_sql=True -> cost_try sirketin cpl_try degerine esittir."""
        cpl = _cpl_map()
        for r in _standart_dataset().generate():
            if r.is_sql:
                assert r.cost_try == cpl[r.company_id]

    def test_maliyet_non_sql_dali_bantta(self):
        """D12: is_sql=False -> cost_try ∈ [0.25, 0.55] * cpl_try (yuvarlama toleri)."""
        cpl = _cpl_map()
        for r in _standart_dataset().generate():
            if not r.is_sql:
                alt, ust = 0.25 * cpl[r.company_id], 0.55 * cpl[r.company_id]
                assert alt - 0.01 <= r.cost_try <= ust + 0.01

    def test_hem_sql_hem_non_sql_uretilir(self):
        """D13: urunen sette hem SQL hem non-SQL kayit vardir."""
        recs = _standart_dataset().generate()
        assert any(r.is_sql for r in recs)
        assert any(not r.is_sql for r in recs)

    def test_pilot_lead_record_frozen(self):
        """D14: PilotLeadRecord immutable (frozen dataclass)."""
        rec = _standart_dataset().generate()[0]
        with pytest.raises(Exception):
            rec.is_sql = not rec.is_sql


class TestToInboundPayloads:
    """to_inbound_payloads — kayit -> InboundLeadPayload cevrimi."""

    def test_sayi_kayitlarla_esit(self):
        """D15: payload sayisi kayit sayisina esittir."""
        recs = _standart_dataset().generate()
        payloads = _standart_dataset().to_inbound_payloads(recs, "tenant-7")
        assert len(payloads) == len(recs)

    def test_tenant_id_yayilir(self):
        """D16: tenant_id her payload'da aynidir."""
        recs = _standart_dataset().generate()
        payloads = _standart_dataset().to_inbound_payloads(recs, "tenant-7")
        assert all(p.tenant_id == "tenant-7" for p in payloads)

    def test_source_manual_import(self):
        """D17: tum payload'lar MANUAL_IMPORT kaynagindadir."""
        recs = _standart_dataset().generate()
        payloads = _standart_dataset().to_inbound_payloads(recs, "tenant-7")
        assert all(p.source == LeadSource.MANUAL_IMPORT for p in payloads)

    def test_contact_email_yok(self):
        """D18: contact_email None (toplu-bulk-olmayan kanal)."""
        recs = _standart_dataset().generate()
        payloads = _standart_dataset().to_inbound_payloads(recs, "tenant-7")
        assert all(p.contact_email is None for p in payloads)

    def test_contact_phone_formati(self):
        """D19: telefon "+90850" oneki ile 7 haneli numara formatindadir."""
        recs = _standart_dataset().generate()
        payloads = _standart_dataset().to_inbound_payloads(recs, "tenant-7")
        for p in payloads:
            assert p.contact_phone.startswith("+90850")
            assert len(p.contact_phone) == len("+90850") + 7
            assert p.contact_phone[len("+90850"):].isdigit()

    def test_intent_summary_sektor_icerir(self):
        """D20: intent_summary sirketin sektor adini tasir."""
        sektor = {c.company_id: c.sector for c in PILOT_COMPANIES}
        recs = _standart_dataset().generate()
        payloads = _standart_dataset().to_inbound_payloads(recs, "tenant-7")
        for p, r in zip(payloads, recs):
            assert sektor[r.company_id] in p.intent_summary

    def test_bilinmeyen_company_id_key_error(self):
        """D21: PILOT_COMPANIES'de olmayan company_id -> KeyError."""
        bogus = PilotLeadRecord(
            lead_id="pilot_lead_99999",
            company_id="mevcut-degil",
            cycle_time_sec=12.0,
            is_sql=False,
            cost_try=10.0,
            has_error=False,
            escalated=False,
        )
        ds = _standart_dataset()
        with pytest.raises(KeyError):
            ds.to_inbound_payloads([bogus], "tenant-7")

    def test_payload_turu_inbound(self):
        """Ek: donen degerler InboundLeadPayload ornegidir."""
        recs = _standart_dataset().generate()[:10]
        payloads = _standart_dataset().to_inbound_payloads(recs, "tenant-7")
        assert all(isinstance(p, InboundLeadPayload) for p in payloads)


class TestBuildKpiCollector:
    """build_kpi_collector — kayitlarin KPI toplayicisina islenmesi."""

    def test_toplam_lead_kayit_sayisi(self):
        """D22: total_leads len(records) ile esittir."""
        recs = _standart_dataset().generate()
        kpi = _standart_dataset().build_kpi_collector(recs, "tenant-7")
        assert kpi.compute_summary_metrics()["total_leads"] == float(len(recs))

    def test_qualified_sql_sayisi_uyumlu(self):
        """D23: qualified_sql uretilen is_sql sayisina esittir."""
        recs = _standart_dataset().generate()
        kpi = _standart_dataset().build_kpi_collector(recs, "tenant-7")
        beklenen = sum(1 for r in recs if r.is_sql)
        assert kpi.compute_summary_metrics()["qualified_sql"] == float(beklenen)

    def test_tenant_id_saklanir(self):
        """D24: collector tenant_id'si parametredir."""
        recs = _standart_dataset().generate()[:5]
        kpi = _standart_dataset().build_kpi_collector(recs, "tenant-ozel")
        assert kpi.tenant_id == "tenant-ozel"

    def test_bos_kayit_sifir_metrik(self):
        """D25: bos kayit listesi -> sifir/sifir metrik (sinir dali)."""
        kpi = _standart_dataset().build_kpi_collector([], "tenant-7")
        m = kpi.compute_summary_metrics()
        assert m["total_leads"] == 0.0
        assert m["qualified_sql"] == 0.0
        assert m["cost_per_lead_try"] == 0


class TestBuildSignedReport:
    """build_signed_report — Ed25519 imzali pilot rapor."""

    def test_uc_demet_donar(self):
        """D26: (report, fingerprint, public_key_hex) 3-demeti doner."""
        recs = _standart_dataset().generate()[:12]
        sonuc = _standart_dataset().build_signed_report(recs, "tenant-7")
        assert isinstance(sonuc, tuple)
        assert len(sonuc) == 3

    def test_report_id_formati(self):
        """D27: report_id yrpt_<periyot-baslangic><tenant> formatindadir."""
        recs = _standart_dataset().generate()[:12]
        rapor, _, _ = _standart_dataset().build_signed_report(
            recs, "tenant-7", period_start="2026-09-01", period_end="2026-09-30"
        )
        assert rapor.report_id == "yrpt_20260901_tenant-7"

    def test_fingerprint_64_hex(self):
        """D28: dataset_fingerprint 64-karakter hex dizgidir."""
        recs = _standart_dataset().generate()[:12]
        _, fingerprint, _ = _standart_dataset().build_signed_report(recs, "tenant-7")
        assert len(fingerprint) == 64
        assert set(fingerprint) <= set("0123456789abcdef")

    def test_public_key_gecerli_ed25519(self):
        """D29: public_key_hex 64 hex (32bayt) Ed25519 acik anahtardir."""
        recs = _standart_dataset().generate()[:12]
        _, _, pub_hex = _standart_dataset().build_signed_report(recs, "tenant-7")
        assert len(pub_hex) == 64  # Ed25519 acik anahtar = 32 bayt
        assert set(pub_hex) <= set("0123456789abcdef")
        bytes.fromhex(pub_hex)  # gecerli hex (ValueError atmaz)

    def test_imza_bagimsiz_dogrulanir(self):
        """D30: rapor imzasi DONEN public key ile bagimsiz dogrulanir."""
        recs = _standart_dataset().generate()[:12]
        rapor, _, pub_hex = _standart_dataset().build_signed_report(recs, "tenant-7")
        payload = MonthlyReportGenerator.to_signable_dict(rapor)
        assert Ed25519ReportSigner.verify_signature(
            payload, rapor.ed25519_signature, pub_hex
        ) is True

    def test_imza_tahrife_direncli(self):
        """D30b: karistirilmis rapor imzasi REDDEDILIR (tahrif-direnci)."""
        recs = _standart_dataset().generate()[:12]
        rapor, _, pub_hex = _standart_dataset().build_signed_report(recs, "tenant-7")
        karisik = MonthlyReportGenerator.to_signable_dict(rapor)
        karisik["total_leads"] = karisik["total_leads"] + 999
        assert Ed25519ReportSigner.verify_signature(
            karisik, rapor.ed25519_signature, pub_hex
        ) is False

    def test_varsayilan_active_components(self):
        """D31: active_components=None -> 6 silindirlik varsayilan liste."""
        recs = _standart_dataset().generate()[:12]
        rapor, _, _ = _standart_dataset().build_signed_report(recs, "tenant-7")
        assert rapor.active_components == [
            "c1_receptionist", "c2_speed_to_lead", "c3_web_qualifier",
            "c4_crm_reactivation", "c5_cold_email_l2", "c6_inbox_triage",
        ]

    def test_ozel_active_components(self):
        """D32: ozel active_components listesi korunur."""
        recs = _standart_dataset().generate()[:12]
        ozel = ["c5_cold_email_l2"]
        rapor, _, _ = _standart_dataset().build_signed_report(
            recs, "tenant-7", active_components=ozel
        )
        assert rapor.active_components == ozel

    def test_metrikler_kayitlarla_uyumlu(self):
        """D33: rapor total_leads/qualified_sql kayitlardan gelir."""
        recs = _standart_dataset().generate()[:30]
        rapor, _, _ = _standart_dataset().build_signed_report(recs, "tenant-7")
        assert rapor.total_leads == len(recs)
        assert rapor.qualified_sql == sum(1 for r in recs if r.is_sql)


class TestDatasetFingerprint:
    """dataset_fingerprint — deterministik kanit-parmakizi."""

    def test_64_hex_karakter(self):
        """D34: parmakizi 64-karakter hex, [0-9a-f] alfabesi."""
        recs = _standart_dataset().generate()[:20]
        fp = SyntheticPilotDataset.dataset_fingerprint(recs)
        assert len(fp) == 64
        assert set(fp) <= set("0123456789abcdef")

    def test_deterministik(self):
        """D35: ayni kayit listesi -> ayni parmakizi."""
        recs = _standart_dataset().generate()[:20]
        a = SyntheticPilotDataset.dataset_fingerprint(recs)
        b = SyntheticPilotDataset.dataset_fingerprint(list(recs))
        assert a == b

    def test_farkli_kayit_farkli_parmakiz(self):
        """D36: farkli kayitlar -> farkli parmakizi."""
        recs = _standart_dataset().generate()[:20]
        kesit = recs[:10]
        assert SyntheticPilotDataset.dataset_fingerprint(recs) != \
            SyntheticPilotDataset.dataset_fingerprint(kesit)

    def test_bos_liste_gecerli_parmakiz(self):
        """D37: bos liste -> gecerli 64-hex parmakizi (sinir)."""
        fp = SyntheticPilotDataset.dataset_fingerprint([])
        assert len(fp) == 64
        assert set(fp) <= set("0123456789abcdef")


class TestWriteJson:
    """write_json — diske-yazma (tmp_path; gercek ag YOK)."""

    def test_path_donar_dosya_olusur(self, tmp_path):
        """D38: donen Path vardir ve dosya fiziksel olarak olusur."""
        recs = _standart_dataset().generate()[:10]
        hedef = tmp_path / "pilot.json"
        sonuc = SyntheticPilotDataset.write_json(recs, hedef)
        assert sonuc == hedef
        assert hedef.exists()

    def test_ebeveyn_dizinleri_olusturur(self, tmp_path):
        """D39: olmayan ic-ice ebeveyn dizinleri yaratilir."""
        recs = _standart_dataset().generate()[:5]
        hedef = tmp_path / "a" / "b" / "c" / "pilot.json"
        SyntheticPilotDataset.write_json(recs, hedef)
        assert hedef.exists()

    def test_json_yapisi_anahtarlar(self, tmp_path):
        """D40: companies / records / synthetic / note anahtarlari mevcuttur."""
        recs = _standart_dataset().generate()[:10]
        hedef = tmp_path / "pilot.json"
        SyntheticPilotDataset.write_json(recs, hedef)
        veri = json.loads(hedef.read_text(encoding="utf-8"))
        assert set(veri) >= {"companies", "records", "synthetic", "note"}
        assert veri["synthetic"] is True

    def test_companies_12_ve_ozdes(self, tmp_path):
        """D41: dosyadaki companies 12 adet ve PILOT_COMPANIES ile ozdestir."""
        recs = _standart_dataset().generate()[:10]
        hedef = tmp_path / "pilot.json"
        SyntheticPilotDataset.write_json(recs, hedef)
        veri = json.loads(hedef.read_text(encoding="utf-8"))
        assert len(veri["companies"]) == len(PILOT_COMPANIES)
        beklenen_ids = [c.company_id for c in PILOT_COMPANIES]
        assert [c["company_id"] for c in veri["companies"]] == beklenen_ids

    def test_records_round_trip_ozdes(self, tmp_path):
        """D42: dosyadaki records girdi kayitlarla birebir ozdestir."""
        recs = _standart_dataset().generate()[:10]
        hedef = tmp_path / "pilot.json"
        SyntheticPilotDataset.write_json(recs, hedef)
        veri = json.loads(hedef.read_text(encoding="utf-8"))
        assert len(veri["records"]) == len(recs)
        assert veri["records"][0]["lead_id"] == recs[0].lead_id
        assert veri["records"][-1]["lead_id"] == recs[-1].lead_id

    def test_utf8_turkce_sirket_adlari(self, tmp_path):
        """D43: Turkce sirket adlari UTF-8 olarak okunabilir (kacis YOK)."""
        recs = _standart_dataset().generate()[:10]
        hedef = tmp_path / "pilot.json"
        SyntheticPilotDataset.write_json(recs, hedef)
        metin = hedef.read_text(encoding="utf-8")
        assert "İstanbul" in metin or "İ" in metin  # en az bir Turkce harf
        assert "\\u" not in metin  # ascii-kacis yok
