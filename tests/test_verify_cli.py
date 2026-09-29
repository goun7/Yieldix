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
    assert "5/5" in p.stdout


def test_verify_json_shape():
    """--json makine-okunabilir-yapı."""
    p = _run_cli("verify", "--json", "--tenant", "verify-test-tenant")
    assert p.returncode == 0, p.stderr
    d = json.loads(p.stdout)
    assert d["verdict"] == "PASS"
    assert d["passed"] == d["total"] == 5
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
