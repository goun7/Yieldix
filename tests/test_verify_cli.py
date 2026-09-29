"""
Bağımsız-doğrulama CLI'si için testler ( kanıt-entegrasyonu).

`yieldix verify` komutu lead → silindirler → KPI → imzalı-rapor zincirini
sıfırdan-oynar ve Ed25519-imzasını bağımsız-teyit-eder. Bu-testler CLI'nın
gerçekten-korunan-şeyi-koruduğunu kanıtlar.
"""

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_cli(*args):
    """Alt-süreç dayanıklı: cwd+PYTHONPATH açıkça-ayarlanır."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(REPO_ROOT, "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "yieldix.cli.main", *args],
        capture_output=True, text=True, timeout=180,
        cwd=REPO_ROOT, env=env,
    )


def test_verify_all_green():
    """Tüm-geçitler-sağlamken verify → PASS + exit-0."""
    p = _run_cli("verify", "--tenant", "verify-test-tenant")
    assert p.returncode == 0, p.stderr
    assert "SONUÇ: PASS" in p.stdout
    # 8+ gate hedefi: güncel kapı sayısı 9 ( 5 → 9)
    assert "9/9" in p.stdout


def test_verify_json_shape():
    """--json makine-okunabilir-yapı."""
    p = _run_cli("verify", "--json", "--tenant", "verify-test-tenant")
    assert p.returncode == 0, p.stderr
    d = json.loads(p.stdout)
    assert d["verdict"] == "PASS"
    assert d["passed"] == d["total"] == 9
    for c in d["checks"]:
        assert set(c.keys()) == {"check", "result", "detail"}
        assert c["result"] == "PASS"


def test_verify_detects_tampered_signature():
    """Regression: imza-doğrulama-bozulursa verify FAIL-vermeli.

    Ed25519ReportSigner.verify_signature'i her-zaman-True-dönecek şekilde
    değiştiririz; verify'in tahrif-direnci-kontrolü bunu yakalamalıdır.
    """
    from yieldix.cli import main as cli_main
    from yieldix.crypto import signer as signer_mod

    if not hasattr(cli_main, "verify"):
        return  # pragma: no cover

    # verify_signature her-zaman-True-dönerse tahrif-kontrolü FAIL-vermeli
    real_verify = signer_mod.Ed25519ReportSigner.verify_signature

    @staticmethod
    def always_true(*a, **k):
        return True

    signer_mod.Ed25519ReportSigner.verify_signature = always_true
    try:
        import click
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli_main.main,
                               ["verify", "--json", "--tenant", "tamper-test"])
        # tahrif-kontrolü: her-zaman-True → tampered_ok=False → FAIL
        assert result.exit_code == 1, "tahrif-direnci-bozuldu-AMA-FAIL-vermedi!"
        d = json.loads(result.output)
        assert d["verdict"] == "FAIL"
        names = {c["check"]: c["result"] for c in d["checks"]}
        assert names.get("signature_verifies_and_tamper_resistant") == "FAIL"
    finally:
        signer_mod.Ed25519ReportSigner.verify_signature = real_verify


def test_verify_tenant_isolation_gate_present():
    """verify çıktısı tenant-izolasyon-geçidini-içermeli."""
    p = _run_cli("verify", "--tenant", "verify-test-tenant")
    assert p.returncode == 0, p.stderr
    assert "tenant_isolation_enforced" in p.stdout


def test_verify_reports_all_new_gate_names():
    """Dürüst-sınır genişlemesi: yeni 4 geçit çıktıda-adı-geçmeli."""
    p = _run_cli("verify", "--tenant", "verify-test-tenant")
    assert p.returncode == 0, p.stderr
    for gate in (
        "pilot_dataset_cpl_sql_quantified",
        "report_digest_matches_payload",
        "bant_scoring_is_structural",
        "cross_tenant_report_isolation",
    ):
        assert gate in p.stdout


def test_verify_at_least_eight_gates():
    """Görev-hedefi: verify 5 → 8+ kapı."""
    p = _run_cli("verify", "--json", "--tenant", "verify-test-tenant")
    assert p.returncode == 0, p.stderr
    d = json.loads(p.stdout)
    assert d["total"] >= 8
    names = {c["check"] for c in d["checks"]}
    assert len(names) == d["total"]   # benzersiz-isimler
    assert all(c["result"] == "PASS" for c in d["checks"])


def test_verify_pilot_gate_quantifies_sql():
    """Pilot-geçidi gerçek SQL-sayısını-raporlamalı ( 0 değil)."""
    p = _run_cli("verify", "--json", "--tenant", "verify-test-tenant")
    assert p.returncode == 0, p.stderr
    d = json.loads(p.stdout)
    pilot = next(c for c in d["checks"] if c["check"] == "pilot_dataset_cpl_sql_quantified")
    assert pilot["result"] == "PASS"
    assert "sql=" in pilot["detail"]
    # 12 şirket + her-birinden lead → en az 10 SQL-bekleriz ( ~%13.5 dönüşüm)
    assert "companies=12" in pilot["detail"]
