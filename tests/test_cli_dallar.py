"""
Dal-kesen (branch-cutting) testler: yieldix.cli.main

Kapsanan public komutlar (src/yieldix/cli/main.py):
  * pilot  — sentetik-pilot veri-seti + imzali-rapor zinciri
  * verify — bagimsiz-dogrulama ( insan-okunur + fail-open tespit dallari)
  * serve  --no-block YOKSA blocking-start dali ( fake-server ile guvenli)

DAL LISTESI (her dal icin en az bir test):
  [pilot]
    D1  varsayilan-cagri — tum govde (142-186) calisir: KPI satirlari,
        imza-bagimsiz-dogrulama gecer, tahrif-reddi gecer
    D2  --out <tmp> — veri-seti disa-aktarim dali (183-185) + gecerli JSON
    D3  --seed/--leads-per-company — deterministik lead-sayisi uyumlu
    D4  leads-per-company=0 — bos veri-seti ( ZeroDivision-gardı: max(1,.))
  [verify]
    D5  insan-okunur cikti dali (407-416) — SONUÇ: PASS + cikis-kodu 0
    D6  toplam-lead-anahtari-yok dali (265->267) — fail-closed: kontrol-FAIL
        ve cikis-kodu 1 ( sessiz-gecis YOK)
    D7  configsiz-engine KABUL-edilirse fail-open saptanir (282-283) —
        tenant-izolasyon kontrolu FAIL, cikis-kodu 1
    D8  YIELDIX_TENANT_ID env-geri-yukleme dali (288-289) — komut sonrasi
        env-degeri bozulmadan kalir
    D9  YIELDIX_ALLOW_DEFAULT_TENANT yan-etkisi — verify pop'lar ve
        GERI-koymaz ( BulgU: env-mutasyonu; test-belgesiyle sabitlenmistir)
  [serve]
    D10 --no-block YOKSA blocking-start (124->exit) — fake-server ile
        gercek-soket ACILMADAN calisir ( Kural-4: pure-bellek)
"""

from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner

from yieldix.cli.main import main


# ---------------------------------------------------------------------------
# pilot
# ---------------------------------------------------------------------------
class TestPilotDallari:
    """pilot — sentetik-pilot + imzali-kanit zinciri dallari (D1-D4)."""

    def test_d1_varsayilan_cagri_tum_govde(self):
        runner = CliRunner()
        result = runner.invoke(main, ["pilot"])
        assert result.exit_code == 0, result.output
        # baslik + KPI satirlari
        assert "SENTETİK" in result.output
        assert "Şirket başına lead" in result.output
        assert "CPL (lead başı)" in result.output
        # imza-bagimsiz-dogrulama + tahrif-reddi ( her-ikiside gecer)
        assert "İmza-bağımsız-doğrula" in result.output
        assert "✓ geçti" in result.output
        assert "Tahrif-reddi" in result.output
        assert "✓ reddetti" in result.output
        # imzali-kanit uretilmis ( iddia-degil-kanit: her-ucu dolu)
        assert "Ed25519 imza" in result.output
        assert "var" in result.output

    def test_d2_out_dosyaya_yazar_gecerli_json(self, tmp_path):
        runner = CliRunner()
        out = tmp_path / "pilot.json"
        result = runner.invoke(main, ["pilot", "--out", str(out)])
        assert result.exit_code == 0, result.output
        assert "Veri seti yazıldı" in result.output
        assert out.is_file()
        veri = json.loads(out.read_text(encoding="utf-8"))
        # write_json sarmalayici-dondurur: {companies, records, synthetic, note}
        kayitlar = veri["records"]
        assert isinstance(kayitlar, list)
        assert len(kayitlar) > 0
        assert veri["synthetic"] is True  # dürüst-etiket ( gercek-veri-degil)
        # her kayit pilot-sablonunun zorunlu alanlarini tasiyor
        for r in kayitlar:
            assert "lead_id" in r
            assert "is_sql" in r
            assert "cost_try" in r

    def test_d3_seed_leads_per_company_deterministik(self):
        from yieldix.telemetry.pilot_dataset import SyntheticPilotDataset
        runner = CliRunner()
        result = runner.invoke(main, ["pilot", "--seed", "7",
                                      "--leads-per-company", "3"])
        assert result.exit_code == 0, result.output
        beklenen = len(SyntheticPilotDataset(
            leads_per_company=3, seed=7).generate())
        assert f"Lead sayısı:          {beklenen}" in result.output
        assert "Şirket başına lead:   3" in result.output

    def test_d4_sifir_lead_fail_closed_gardi(self):
        # leads-per-company=0 — SyntheticPilotDataset ValueError-atar
        # ( fail-closed-gard: gecersiz-giris sessiz-bos-veri URETMEZ)
        runner = CliRunner()
        result = runner.invoke(main, ["pilot", "--leads-per-company", "0"])
        assert result.exit_code == 1
        assert isinstance(result.exception, ValueError)
        assert "leads_per_company" in str(result.exception)


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------
class TestVerifyDallari:
    """verify — bagimsiz-dogrulama insan-okunur + fail-open dallari (D5-D9)."""

    def test_d5_insan_okunur_cikti_pass(self):
        runner = CliRunner()
        result = runner.invoke(main, ["verify"])
        assert result.exit_code == 0, result.output
        # 407-416: insan-okunur cikti govdesi
        assert "YIELDIX BAĞIMSIZ-DOĞRULAMA" in result.output
        assert "SONUÇ: PASS" in result.output
        # her-kontrol ayrintili-listelenmis ( JSON-dali degil)
        assert "pipeline_runs_lead_to_cycle" in result.output
        assert "circuit_breaker_sheds_on_breach" in result.output
        assert "cross_tenant_report_isolation" in result.output

    def test_d6_toplam_lead_anahtari_yok_fail_closed(self, monkeypatch):
        # 265->267: imzali-payload'da "total_leads" YOKSA tahrif-kontrolu
        # yine-de-calismali ( sessiz-gecis-ve-yanlis-PASS YOK)
        from yieldix.telemetry.reporter import MonthlyReportGenerator
        gercek = MonthlyReportGenerator.to_signable_dict

        def fake(report):
            d = dict(gercek(report))
            d.pop("total_leads", None)
            return d

        monkeypatch.setattr(MonthlyReportGenerator, "to_signable_dict",
                            staticmethod(fake))
        runner = CliRunner()
        result = runner.invoke(main, ["verify"])
        # fail-closed: imza-payload'u degisince kontrol FAIL → cikis 1
        assert result.exit_code == 1, result.output
        assert "signature_verifies_and_tamper_resistant" in result.output
        assert "✗" in result.output
        assert "SONUÇ: FAIL" in result.output

    def test_d7_configsiz_engine_kabul_fail_open_saptanir(self, monkeypatch):
        # 282-283: YieldixEngine() configsiz-KABUL-edilirse verify bunu
        # cross-tenant-acik olarak FAIL-etmeli ( fail-open-gecistirmez)
        import yieldix.cli.main as cli_main

        class _KabulEdenMotor:
            def __init__(self, config=None):
                self.config = config

        monkeypatch.setattr(cli_main, "YieldixEngine", _KabulEdenMotor)
        runner = CliRunner()
        result = runner.invoke(main, ["verify"])
        assert result.exit_code == 1, result.output
        assert "tenant_isolation_enforced" in result.output
        assert "KABUL-EDİLDİ" in result.output
        assert "cross-tenant-açık" in result.output

    def test_d8_env_tenant_geri_yuklenir(self, monkeypatch):
        # 288-289: verify YIELDIX_TENANT_ID'yi pop'lar-ve-GERI-koyar
        monkeypatch.setenv("YIELDIX_TENANT_ID", "env-tenant-dallar")
        runner = CliRunner()
        result = runner.invoke(main, ["verify"])
        assert result.exit_code == 0, result.output
        assert os.environ.get("YIELDIX_TENANT_ID") == "env-tenant-dallar"

    def test_d9_allow_default_env_geri_konulmaz(self, monkeypatch):
        # BULGU-belgeleme: verify YIELDIX_ALLOW_DEFAULT_TENANT'yi pop'lar
        # ANCAK geri-koymaz ( yan-etki: env-mutasyonu). Kontrol kendisi
        # closed-degil; bu test davranisi sabitler ( uretime-dokunulmadi).
        monkeypatch.setenv("YIELDIX_ALLOW_DEFAULT_TENANT", "1")
        runner = CliRunner()
        result = runner.invoke(main, ["verify"])
        assert result.exit_code == 0, result.output
        # komut calistiktan sonra env-degeri KAYBOLMUS ( mutasyon-kaniti)
        assert os.environ.get("YIELDIX_ALLOW_DEFAULT_TENANT") is None


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------
class TestServeDallari:
    """serve — blocking-start dali, fake-server ile saf-bellek (D10)."""

    def test_d10_blocking_start_fake_server(self, monkeypatch):
        import yieldix.server.app as app_mod
        cagri = {}

        class _FakeServer:
            def start(self, blocking=True):
                cagri["blocking"] = blocking

            def stop(self):
                cagri["stopped"] = True

        monkeypatch.setattr(app_mod, "create_server",
                            lambda host, port: _FakeServer())
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--port", "8996"])
        assert result.exit_code == 0, result.output
        assert "Starting Yieldix Cockpit on http://127.0.0.1:8996" \
            in result.output
        # --no-block YOK → blocking=True ( 124->exit: stop cagrilmaz)
        assert cagri.get("blocking") is True
        assert "stopped" not in cagri
