"""
RC-pin testleri ( DALGA-D1): yieldix.cli.main çıkış-kodu matrisi.

Her-test, docs/CLI_RC_MATRISI.md'deki bir matris-satırını sabitler ( pin).
Ölçüm-yöntemi ( matris ile aynı): komut çalışır, çıkış-kodu doğrulanır.
Kural: CLIRunner kullanılır ( gerçek-proses-fork YOK — hızlı + deterministik).

MATRİS (27 satır — tamamı beklenen-rc ile UYUMLU, kırmızı-YOK):
  [global]  G1 --help=0 | G2 --version=0 | G3 --bilinmeyen-flag=2 | G4 bilinmeyen-komut=2
  [status]  S1 =0 | S2 --tenant OLMAYAN=0 | S3 --bilinmeyen=2 | S4 --tenant ""=0
  [ingest]  I1 =0 | I2 --phone-yok=2 | I3 --phone abc=0 | I4 boş-alanlar=0
  [simulate] M1 =0 | M2 runs=1=0 | M3 runs=10=0 | M4 runs=0=2 | M5 runs=-5=2
            M6 runs abc=2 | M7 retainer abc=2 | M8 retainer ""=2
            M9 devasa-runs: CliRunner-ile-ölçülemez ( sonsuz-CPU) — atlandı,
            yerine üst-sınır-YOK belgeleyici-test ( M9-DOC)
  [report]  R1 =0 | R2 --tenant OLMAYAN=0 | R3 --start wrong=0 | R4 2026-13-45=0
  [verify]  V1 =0 | V2 --json=0 | V3 --bilinmeyen=2 | V4 --tenant OLMAYAN=0
  [serve]   SV1 --no-block=0 | SV2 --port abc=2
  [pilot]   P1 =0 | P2 --leads-per-company abc=2

NOT: S2/S4/R2/I3/I4/R3/R4 "geçersiz"-girdiler rc=0 verir — bunlar ZAYIF-DOĞRULAMA
davranışlarıdır ( traceable docs/CLI_RC_MATRISI.md "Bilinen-Sonuçlar" bölümünde).
Bu-testler ölçülen-davranışı sabitler; DALGA-D2'ye-rafta-düzeltme-bırakılır.
"""

from __future__ import annotations

import inspect
import json

from click.testing import CliRunner

from yieldix.cli.main import main


# ---------------------------------------------------------------------------
# Global — grup-bayrakları ( G1-G4)
# ---------------------------------------------------------------------------
class TestGlobalRCPinleri:
    """Global-bayrak çıkış-kodları ( G1-G4)."""

    def test_g1_help_rc0(self):
        result = CliRunner().invoke(main, ["--help"])
        assert result.exit_code == 0, result.output
        assert "Commands:" in result.output
        # Komut-listesi tam: 7 komut-un hepsi --help'te-listelenmis
        for komut in ("ingest", "pilot", "report", "serve",
                      "simulate", "status", "verify"):
            assert komut in result.output

    def test_g2_version_rc0(self):
        result = CliRunner().invoke(main, ["--version"])
        assert result.exit_code == 0, result.output
        assert "16.0.0" in result.output
        assert "yieldix" in result.output

    def test_g3_bilinmeyen_flag_rc2(self):
        result = CliRunner().invoke(main, ["--bilinmeyen-flag"])
        assert result.exit_code == 2, result.output
        assert "No such option" in result.output

    def test_g4_bilinmeyen_komut_rc2(self):
        result = CliRunner().invoke(main, ["bilinmeyen-komut"])
        assert result.exit_code == 2, result.output
        assert "No such command" in result.output


# ---------------------------------------------------------------------------
# status ( S1-S4)
# ---------------------------------------------------------------------------
class TestStatusRCPinleri:
    """status çıkış-kodu pin'leri ( S1-S4)."""

    def test_s1_varsayilan_rc0(self):
        result = CliRunner().invoke(main, ["status"])
        assert result.exit_code == 0, result.output
        assert "YIELDIX ENGINE STATUS" in result.output
        assert "Circuit Breaker Tripped" in result.output

    def test_s2_olmayan_tenant_rc0(self):
        # ZAYIF-DOĞRULAMA: tenant varlığı doğrulanmaz ( S2-notu)
        result = CliRunner().invoke(main, ["status", "--tenant", "OLMAYAN"])
        assert result.exit_code == 0, result.output
        assert "OLMAYAN" in result.output

    def test_s3_bilinmeyen_secenek_rc2(self):
        result = CliRunner().invoke(main, ["status", "--bilinmeyen"])
        assert result.exit_code == 2, result.output
        assert "No such option" in result.output

    def test_s4_bos_tenant_rc0(self):
        result = CliRunner().invoke(main, ["status", "--tenant", ""])
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# ingest ( I1-I4)
# ---------------------------------------------------------------------------
class TestIngestRCPinleri:
    """ingest çıkış-kodu pin'leri ( I1-I4)."""

    def test_i1_gecerli_rc0(self):
        result = CliRunner().invoke(
            main, ["ingest", "--name", "Test Contact",
                   "--phone", "+15551234567"])
        assert result.exit_code == 0, result.output
        veri = json.loads(result.output)
        assert veri["is_sql"] is True
        assert "cycle_time_seconds" in veri

    def test_i2_phone_eksik_rc2(self):
        result = CliRunner().invoke(main, ["ingest", "--name", "X"])
        assert result.exit_code == 2, result.output
        assert "Missing option '--phone'" in result.output

    def test_i3_phone_abc_rc0_zayif_dogrulama(self):
        # ZAYIF-DOĞRULAMA: telefon-format-kontrolu YOK ( I3-notu)
        result = CliRunner().invoke(
            main, ["ingest", "--name", "X", "--phone", "abc"])
        assert result.exit_code == 0, result.output

    def test_i4_bos_alanlar_rc0_zayif_dogrulama(self):
        result = CliRunner().invoke(
            main, ["ingest", "--name", "", "--phone", ""])
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# simulate ( M1-M9)
# ---------------------------------------------------------------------------
class TestSimulateRCPinleri:
    """simulate çıkış-kodu pin'leri ( M1-M9)."""

    def test_m1_varsayilan_rc0(self):
        result = CliRunner().invoke(main, ["simulate"])
        assert result.exit_code == 0, result.output
        assert "SIMULATION RESULTS" in result.output
        assert "Loss Probability" in result.output

    def test_m2_runs_bir_rc0(self):
        # Sınır-değer: runs=1 ( IntRange(min=1) alt-sınırı)
        result = CliRunner().invoke(main, ["simulate", "--runs", "1"])
        assert result.exit_code == 0, result.output
        assert "P5 (Worst Case)" in result.output

    def test_m3_runs_on_rc0(self):
        result = CliRunner().invoke(main, ["simulate", "--runs", "10"])
        assert result.exit_code == 0, result.output

    def test_m4_runs_sifir_rc2(self):
        # DALGA-C-2 düzeltmesi: IntRange(min=1) — 'simulate --runs 0' rc=2
        result = CliRunner().invoke(main, ["simulate", "--runs", "0"])
        assert result.exit_code == 2, result.output
        assert "Invalid value for '--runs'" in result.output

    def test_m5_runs_negatif_rc2(self):
        result = CliRunner().invoke(main, ["simulate", "--runs", "-5"])
        assert result.exit_code == 2, result.output
        assert "Invalid value for '--runs'" in result.output

    def test_m6_runs_harita_rc2(self):
        result = CliRunner().invoke(main, ["simulate", "--runs", "abc"])
        assert result.exit_code == 2, result.output
        assert "Invalid value for '--runs'" in result.output

    def test_m7_retainer_abc_rc2(self):
        # DALGA-C-2 düzeltmesi: _DecimalParam — UsageError ( rc=2)
        result = CliRunner().invoke(
            main, ["simulate", "--runs", "5", "--retainer", "abc"])
        assert result.exit_code == 2, result.output
        assert "Invalid value for '--retainer'" in result.output

    def test_m8_retainer_bos_rc2(self):
        result = CliRunner().invoke(
            main, ["simulate", "--runs", "1", "--retainer", ""])
        assert result.exit_code == 2, result.output
        assert "Invalid value for '--retainer'" in result.output

    def test_m9_devasa_runs_ust_sinir_yok_belgeleme(self):
        # M9-DOC: devasa-run sayısı ( 10^20) IntRange-üst-sınırı NOKSASLIĞI
        # nedeniyle kabul-edilir ( ölçümde timeout rc=124). Bu-test davranışı
        # belgeler: IntRange'de max YOK — sonsuz-CPU riski ( D2'ye-rafta).
        # NOT: 10^20 çalıştırılmaz ( testi-sonsuz-yapmaması-için).
        # click Command-sarmalayicisindan-gercek-fonksiyonu-al
        from yieldix.cli.main import simulate as simulate_command
        kaynak = inspect.getsource(simulate_command.callback)
        # 'max=' IntRange-parametresi YOK — pin-belgesi
        assert "IntRange(min=1)" in kaynak
        assert "max=" not in kaynak.split("IntRange(min=1)")[0].rsplit("\n", 1)[-1]


# ---------------------------------------------------------------------------
# report ( R1-R4)
# ---------------------------------------------------------------------------
class TestReportRCPinleri:
    """report çıkış-kodu pin'leri ( R1-R4)."""

    def test_r1_varsayilan_rc0(self):
        result = CliRunner().invoke(main, ["report"])
        assert result.exit_code == 0, result.output
        assert "Ed25519" in result.output
        assert "Doğrulama Anahtarı" in result.output

    def test_r2_olmayan_tenant_rc0(self):
        result = CliRunner().invoke(main, ["report", "--tenant", "OLMAYAN"])
        assert result.exit_code == 0, result.output
        assert "Ed25519" in result.output

    def test_r3_gecersiz_tarih_rc0_zayif_dogrulama(self):
        # ZAYIF-DOĞRULAMA: tarih-format-kontrolu YOK ( R3-notu)
        result = CliRunner().invoke(main, ["report", "--start", "wrong"])
        assert result.exit_code == 0, result.output

    def test_r4_mantiksiz_tarih_rc0_zayif_dogrulama(self):
        # 2026-13-45 — format-uygun-AMA-mantıksız ( 45. gün) sessiz-kabul
        result = CliRunner().invoke(
            main, ["report", "--start", "2026-13-45"])
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# verify ( V1-V4 + --json yapısı)
# ---------------------------------------------------------------------------
class TestVerifyRCPinleri:
    """verify çıkış-kodu pin'leri + --json yapı-sabitleme ( V1-V4)."""

    def test_v1_varsayilan_rc0(self):
        result = CliRunner().invoke(main, ["verify"])
        assert result.exit_code == 0, result.output
        assert "SONUÇ: PASS" in result.output
        assert "9/9" in result.output

    def test_v2_json_yapisi_alan_tipleri(self):
        result = CliRunner().invoke(main, ["verify", "--json"])
        assert result.exit_code == 0, result.output
        # Çıktı saf-JSON-değIL: motor CB-uyarıları ile karışıktır
        # ( matris-notu). İlk '{' konumundan-başla.
        baslangic = result.output.index("{")
        veri = json.loads(result.output[baslangic:])
        # Üst-düzey alan-adları + tipler
        assert set(veri.keys()) == {"verdict", "passed", "total", "checks"}
        assert isinstance(veri["verdict"], str)
        assert veri["verdict"] == "PASS"
        assert isinstance(veri["passed"], int)
        assert isinstance(veri["total"], int)
        assert isinstance(veri["checks"], list)
        # Her-check: alan-adları + tipler + sonuç-değerleri
        for c in veri["checks"]:
            assert set(c.keys()) == {"check", "result", "detail"}
            assert isinstance(c["check"], str)
            assert isinstance(c["result"], str)
            assert isinstance(c["detail"], str)
            assert c["result"] in ("PASS", "FAIL")
        # 9 bağımsız-kontrolün-tümü-PASS
        assert veri["passed"] == veri["total"] == 9

    def test_v3_bilinmeyen_secenek_rc2(self):
        result = CliRunner().invoke(main, ["verify", "--bilinmeyen"])
        assert result.exit_code == 2, result.output
        assert "No such option" in result.output

    def test_v4_olmayan_tenant_rc0(self):
        result = CliRunner().invoke(main, ["verify", "--tenant", "OLMAYAN"])
        assert result.exit_code == 0, result.output
        assert "SONUÇ: PASS" in result.output


# ---------------------------------------------------------------------------
# serve ( SV1-SV2)
# ---------------------------------------------------------------------------
class TestServeRCPinleri:
    """serve çıkış-kodu pin'leri ( SV1-SV2)."""

    def test_sv1_no_block_rc0(self):
        # NOT: gerçek-soket açar ( default-port 8088) — test-sürecinde
        # güvenli olan --no-block dali kullanılır ( matris-ölçümü ile aynı).
        result = CliRunner().invoke(main, ["serve", "--no-block"])
        assert result.exit_code == 0, result.output
        assert "Starting Yieldix Cockpit" in result.output

    def test_sv2_port_abc_rc2(self):
        result = CliRunner().invoke(main, ["serve", "--port", "abc"])
        assert result.exit_code == 2, result.output
        assert "Invalid value for '--port'" in result.output


# ---------------------------------------------------------------------------
# pilot ( P1-P2)
# ---------------------------------------------------------------------------
class TestPilotRCPinleri:
    """pilot çıkış-kodu pin'leri ( P1-P2)."""

    def test_p1_varsayilan_rc0(self):
        result = CliRunner().invoke(main, ["pilot"])
        assert result.exit_code == 0, result.output
        assert "SENTETİK" in result.output
        assert "Ed25519 imza" in result.output

    def test_p2_leads_per_company_abc_rc2(self):
        result = CliRunner().invoke(
            main, ["pilot", "--leads-per-company", "abc"])
        assert result.exit_code == 2, result.output
        assert "Invalid value for '--leads-per-company'" in result.output
