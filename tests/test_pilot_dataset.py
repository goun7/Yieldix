"""
Sentetik pilot veri seti testleri ( dürüst-sınır kapatması).

Kullanıcı eleştirisine yanıt: "lead qualification akademik boş — gerçek pilot
CPL/SQL verisi olmalı". Bu testler, pilot veri setinin:
  * 10+ kurgusal şirket içerdiğini ( hedef: 12)
  * CPL/SQL değerlerinin gerçekçi bantlarda olduğunu
  * tamamen deterministik / tekrar-oynanabilir olduğunu
  * imzalı-raporla doğrulanabilir olduğunu ( tahrif-direnci ile)
kanıtlar. Tüm veri SENTETİKTİR — gerçek müşteri verisi DEĞİLDİR.
"""

import json
from decimal import Decimal

import pytest

from yieldix.crypto.signer import Ed25519ReportSigner
from yieldix.telemetry.pilot_dataset import (
    PILOT_COMPANIES, PilotCompany, SyntheticPilotDataset,
)
from yieldix.telemetry.reporter import MonthlyReportGenerator
from yieldix.core.types import InboundLeadPayload, LeadSource


def test_pilot_has_at_least_ten_companies():
    """Görev: '10+ kurgusal şirket' hedefi."""
    assert len(PILOT_COMPANIES) >= 10


def test_all_company_fields_valid():
    for c in PILOT_COMPANIES:
        assert c.company_id and c.company_name and c.sector
        assert 0.0 <= c.intent_weight <= 1.0
        assert 0.0 < c.sql_rate <= 1.0
        assert c.cpl_try > 0.0


def test_companies_unique_ids():
    ids = [c.company_id for c in PILOT_COMPANIES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("band", ["cpl_try", "sql_rate"])
def test_company_params_in_realistic_band(band):
    """CPL 10–400 ₺, SQL oranı %2–35 — gerçek B2B lead-pazarı bandı."""
    vals = [getattr(c, band) for c in PILOT_COMPANIES]
    assert min(vals) > 0.0
    if band == "cpl_try":
        assert 10.0 <= min(vals) and max(vals) <= 400.0
    else:
        assert 0.02 <= min(vals) and max(vals) <= 0.35


def test_dataset_deterministic_same_seed():
    a = SyntheticPilotDataset(leads_per_company=10, seed=42).generate()
    b = SyntheticPilotDataset(leads_per_company=10, seed=42).generate()
    assert a == b


def test_dataset_seed_changes_output():
    a = SyntheticPilotDataset(leads_per_company=10, seed=1).generate()
    b = SyntheticPilotDataset(leads_per_company=10, seed=2).generate()
    assert a != b


def test_dataset_lead_count():
    ds = SyntheticPilotDataset(leads_per_company=15, seed=7)
    records = ds.generate()
    assert len(records) == 15 * len(PILOT_COMPANIES)


def test_dataset_rejects_nonpositive_leads():
    with pytest.raises(ValueError, match="leads_per_company > 0"):
        SyntheticPilotDataset(leads_per_company=0)


def test_dataset_cycle_time_within_realistic_bounds():
    records = SyntheticPilotDataset(leads_per_company=8, seed=11).generate()
    for r in records:
        assert 5.0 <= r.cycle_time_sec <= 100.0


def test_dataset_sql_conversion_in_realistic_band():
    """Üretilen SQL oranı %2–40 arasında olmalı ( gerçek B2B bandı)."""
    records = SyntheticPilotDataset(leads_per_company=30, seed=99).generate()
    rate = sum(r.is_sql for r in records) / len(records)
    assert 0.02 <= rate <= 0.40


def test_dataset_sql_costs_more_than_non_sql():
    """SQL'ler insan-dokunuşu gerektirir — maliyet daha yüksek olmalı."""
    records = SyntheticPilotDataset(leads_per_company=20, seed=5).generate()
    by_company = {}
    for r in records:
        by_company.setdefault(r.company_id, {"sql": [], "nonsql": []})
        (by_company[r.company_id]["sql"] if r.is_sql
         else by_company[r.company_id]["nonsql"]).append(r.cost_try)
    checked = 0
    for cid, groups in by_company.items():
        if groups["sql"] and groups["nonsql"]:
            assert sum(groups["sql"]) / len(groups["sql"]) >= \
                   sum(groups["nonsql"]) / len(groups["nonsql"])
            checked += 1
    assert checked > 0, "en az bir şirkette hem SQL hem non-SQL olmalı"


def test_dataset_fingerprint_stable_and_unique():
    a = SyntheticPilotDataset(leads_per_company=10, seed=3).generate()
    b = SyntheticPilotDataset(leads_per_company=10, seed=3).generate()
    c = SyntheticPilotDataset(leads_per_company=10, seed=4).generate()
    fa = SyntheticPilotDataset.dataset_fingerprint(a)
    fb = SyntheticPilotDataset.dataset_fingerprint(b)
    fc = SyntheticPilotDataset.dataset_fingerprint(c)
    assert fa == fb            # deterministic
    assert fa != fc            # farklı veri → farklı parmakizi
    assert len(fa) == 64


def test_dataset_fingerprint_detects_tamper():
    records = SyntheticPilotDataset(leads_per_company=6, seed=8).generate()
    before = SyntheticPilotDataset.dataset_fingerprint(records)
    # Kayıtlar donuk ( frozen); tahrifi kanonik-listeden yeniden-üreterek simüle et
    tampered = list(records)
    first = tampered[0]
    import dataclasses
    tampered[0] = dataclasses.replace(first, is_sql=not first.is_sql)
    after = SyntheticPilotDataset.dataset_fingerprint(tampered)
    assert before != after


def test_build_signed_report_quantifies_cpl_and_sql():
    records = SyntheticPilotDataset(leads_per_company=25, seed=1337).generate()
    report, fingerprint, pubkey = SyntheticPilotDataset().build_signed_report(
        records, tenant_id="pilot-test")

    assert report.total_leads == len(records)
    assert report.qualified_sql == sum(r.is_sql for r in records)
    assert report.cost_per_lead_try > Decimal("0.00")
    assert report.ed25519_signature is not None
    assert report.sha256_digest is not None
    assert len(fingerprint) == 64
    assert len(pubkey) == 64


def test_signed_report_independently_verifies():
    """Rapor imzası bağımsız olarak yeniden-doğrulanabilmeli."""
    records = SyntheticPilotDataset(leads_per_company=12, seed=2024).generate()
    report, _, pubkey = SyntheticPilotDataset().build_signed_report(
        records, tenant_id="pilot-verify")
    payload = MonthlyReportGenerator.to_signable_dict(report)
    ok = Ed25519ReportSigner.verify_signature(
        payload, report.ed25519_signature, pubkey)
    assert ok is True


def test_signed_report_tamper_resistant():
    """Pilot CPL değeri değiştirilince imza artık onaylanmamalı."""
    records = SyntheticPilotDataset(leads_per_company=12, seed=2024).generate()
    report, _, pubkey = SyntheticPilotDataset().build_signed_report(
        records, tenant_id="pilot-verify")
    payload = MonthlyReportGenerator.to_signable_dict(report)
    tampered = dict(payload)
    tampered["qualified_sql"] = (tampered["qualified_sql"] or 0) + 999
    bad = Ed25519ReportSigner.verify_signature(
        tampered, report.ed25519_signature, pubkey)
    assert bad is False


def test_wrong_public_key_rejects_report():
    """Farklı bir anahtar, doğru imzayı reddetmeli ( anahtar-anahtarı)."""
    records = SyntheticPilotDataset(leads_per_company=12, seed=2024).generate()
    report, _, _ = SyntheticPilotDataset().build_signed_report(
        records, tenant_id="pilot-verify")
    payload = MonthlyReportGenerator.to_signable_dict(report)
    other = Ed25519ReportSigner().public_key_hex
    ok = Ed25519ReportSigner.verify_signature(
        payload, report.ed25519_signature, other)
    assert ok is False


def test_to_inbound_payloads_shapes():
    records = SyntheticPilotDataset(leads_per_company=3, seed=31).generate()
    payloads = SyntheticPilotDataset().to_inbound_payloads(
        records, tenant_id="t-1")
    assert len(payloads) == len(records)
    assert all(isinstance(p, InboundLeadPayload) for p in payloads)
    assert all(p.tenant_id == "t-1" for p in payloads)
    assert all(p.source == LeadSource.MANUAL_IMPORT for p in payloads)
    assert len({p.lead_id for p in payloads}) == len(payloads)


def test_write_json_roundtrip(tmp_path):
    records = SyntheticPilotDataset(leads_per_company=4, seed=55).generate()
    out = SyntheticPilotDataset.write_json(records, tmp_path / "pilot.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["synthetic"] is True
    assert "SENTETIK" in data["note"]
    assert len(data["records"]) == len(records)
    assert len(data["companies"]) == len(PILOT_COMPANIES)


def test_pilot_company_is_frozen():
    import dataclasses
    c = PILOT_COMPANIES[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.cpl_try = 1.0


def test_cli_pilot_command_runs(tmp_path):
    """CLI 'pilot' komutu uçtan-uca çalışmalı ve imzalı-rapor üretmeli."""
    import subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    out = tmp_path / "pilot_out.json"
    res = subprocess.run(
        [sys.executable, "-m", "yieldix.cli.main", "pilot",
         "--leads-per-company", "5", "--out", str(out)],
        capture_output=True, text=True, cwd=str(root),
        env={"PYTHONPATH": str(root / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert res.returncode == 0, res.stderr
    assert "12 kurgusal B2B şirket" in res.stdout
    assert "CPL" in res.stdout
    assert out.exists()
