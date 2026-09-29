"""
Yieldix Command Line Interface (CLI).
Enterprise execution, lead testing, L2 human review, and Monte Carlo simulation.
"""

from __future__ import annotations

import asyncio
import json
import random
from decimal import Decimal

import click

from yieldix.core.engine import YieldixEngine
from yieldix.core.types import InboundLeadPayload, LeadSource, PipelineConfig
from yieldix.telemetry.reporter import MonthlyReportGenerator


@click.group()
@click.version_option("16.0.0", prog_name="yieldix")
def main():
    """🦄 Yieldix: Autonomous B2B Revenue Engine CLI."""


@main.command(name="status")
@click.option("--tenant", default="cust_enterprise_01", help="Tenant ID")
def status(tenant: str):
    """Displays engine and circuit breaker status."""
    engine = YieldixEngine(PipelineConfig(tenant_id=tenant))
    cycle = asyncio.run(engine.run_daily_cycle())
    click.echo(f"=== YIELDIX ENGINE STATUS: {tenant} ===")
    click.echo(f"Active Components: {', '.join(cycle['active_components'])}")
    click.echo(f"Shed Components: {', '.join(cycle['shed_components']) if cycle['shed_components'] else 'None'}")
    click.echo(f"Circuit Breaker Tripped: {cycle['circuit_breaker_tripped']}")


@main.command(name="ingest")
@click.option("--tenant", default="cust_enterprise_01", help="Tenant ID")
@click.option("--name", required=True, help="Contact name")
@click.option("--phone", required=True, help="Contact phone")
@click.option("--intent", default="Kurumsal B2B teklif talebi", help="Lead intent")
def ingest(tenant: str, name: str, phone: str, intent: str):
    """Ingests a lead and triggers the sub-60s speed-to-lead flow."""
    engine = YieldixEngine(PipelineConfig(tenant_id=tenant))
    lead = InboundLeadPayload(
        tenant_id=tenant,
        lead_id=f"lead_{int(random.random()*10000)}",
        contact_name=name,
        contact_phone=phone,
        source=LeadSource.WEB_FORM,
        intent_summary=intent,
    )
    result = asyncio.run(engine.ingest_inbound_lead(lead))
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


@main.command(name="simulate")
@click.option("--runs", default=10000, help="Number of Monte Carlo simulation runs")
@click.option("--retainer", default="2500.00", help="Monthly retainer in USD")
def simulate(runs: int, retainer: str | float):
    """Executes N=10,000 Monte Carlo financial stress simulation."""
    retainer_dec = Decimal(str(retainer))
    click.echo(f"Running Monte Carlo simulation ({runs} runs, Retainer=${retainer_dec:.2f})...")
    profits = []
    base_cogs = Decimal("90.00")
    for _ in range(runs):
        leads = max(100.0, random.gauss(450.0, 90.0))
        api_multiplier = Decimal(str(round(random.uniform(0.85, 1.40), 4)))
        escalation_pct = max(1.0, min(30.0, random.gauss(8.5, 3.2)))
        lead_ratio = Decimal(str(round(leads / 450.0, 4)))
        variable_cogs = base_cogs * lead_ratio * api_multiplier
        penalty = Decimal("0.00")
        if escalation_pct > 20.0:
            esc_excess = Decimal(str(round((escalation_pct - 20.0) / 10.0, 4)))
            penalty = Decimal("150.00") * esc_excess
        net_profit = retainer_dec - (variable_cogs + penalty)
        profits.append(net_profit)

    profits.sort()
    p5 = profits[int(runs * 0.05)]
    p50 = profits[int(runs * 0.50)]
    p95 = profits[int(runs * 0.95)]
    loss_count = sum(1 for p in profits if p <= Decimal("0.00"))

    click.echo("=== SIMULATION RESULTS ===")
    click.echo(f"P5 (Worst Case): ${p5:.2f}")
    click.echo(f"P50 (Median):     ${p50:.2f} (Margin: %{(p50/retainer_dec)*100:.2f})")
    click.echo(f"P95 (Best Case):  ${p95:.2f}")
    click.echo(f"Loss Probability: %{(loss_count/runs)*100:.2f}")


@main.command(name="report")
@click.option("--tenant", default="cust_enterprise_01", help="Tenant ID")
@click.option("--start", default="2026-10-01", help="Period start date")
@click.option("--end", default="2026-10-31", help="Period end date")
def report(tenant: str, start: str, end: str):
    """Generates an Ed25519 signed monthly audit report card."""
    engine = YieldixEngine(PipelineConfig(tenant_id=tenant))
    # Ingest baseline transaction event
    engine.kpi_collector.record_lead_processed("lead_demo", 32.5, is_sql=True, cost_try=Decimal("15.00"))
    rep_gen = MonthlyReportGenerator()
    rep = rep_gen.generate_signed_report(
        tenant_id=tenant,
        period_start=start,
        period_end=end,
        kpi_collector=engine.kpi_collector,
        active_components=engine.config.enabled_components,
    )
    card = rep_gen.export_markdown_card(rep)
    click.echo(card)


@main.command(name="serve")
@click.option("--host", default="127.0.0.1", help="Host interface to bind")
@click.option("--port", default=8088, type=int, help="Port to listen on")
@click.option("--no-block", is_flag=True, default=False, help="Launch non-blocking smoke run")
def serve(host: str, port: int, no_block: bool = False):
    """Launches the sovereign Yieldix web telemetry and cockpit server."""
    from yieldix.server.app import create_server
    click.echo(f"Starting Yieldix Cockpit on http://{host}:{port}")
    server = create_server(host=host, port=port)
    server.start(blocking=not no_block)
    if no_block:
        server.stop()


@main.command(name="verify")
@click.option("--tenant", default="verify-tenant", help="Tenant ID for the verification run")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine-readable JSON output")
def verify(tenant: str, as_json: bool):
    """
    Bağımsız-doğrulama CLI'si ( kanıt-entegrasyonu).

    lead → silindirler → KPI → imzalı-rapor zincirini sıfırdan-oynar ve
    Ed25519-imzasını bağımsız olarak yeniden-doğrular. Demo-komutlarının
    paylaştığı-durumu kullanmaz; her-geçidi ayrı-ölçer.

    Exit-code: 0 = hepsi-geçti, 1 = en-az-bir-bozuk.
    """
    checks: list[dict] = []

    def record(name, ok, detail):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    # 1) Pipeline-koşusu: lead-ingest → döngü → KPI-toplandı
    try:
        engine = YieldixEngine(PipelineConfig(tenant_id=tenant))
        lead = InboundLeadPayload(
            tenant_id=tenant,
            lead_id="lead_verify_001",
            contact_name="Verification Contact",
            contact_phone="+15550001111",
            source=LeadSource.WEB_FORM,
            intent_summary="Verification intent — enterprise B2B quote",
        )
        ingest_res = asyncio.run(engine.ingest_inbound_lead(lead))
        cycle = asyncio.run(engine.run_daily_cycle())
        ok = bool(ingest_res) and len(cycle.get("active_components", [])) > 0
        record("pipeline_runs_lead_to_cycle", ok,
               f"ingested={bool(ingest_res)} active={len(cycle.get('active_components', []))} "
               f"shed={len(cycle.get('shed_components', []))}")
    except Exception as e:  # pragma: no cover - diagnostic
        record("pipeline_runs_lead_to_cycle", False, f"exception: {type(e).__name__}: {e}")

    # 2) Kanıt-üretimi: imzalı-rapor-üretiliyor + SHA-256-özeti-var
    try:
        engine = YieldixEngine(PipelineConfig(tenant_id=tenant))
        engine.kpi_collector.record_lead_processed(
            "lead_verify_001", 32.5, is_sql=True, cost_try=Decimal("15.00"))
        gen = MonthlyReportGenerator()
        rep = gen.generate_signed_report(
            tenant_id=tenant, period_start="2026-10-01", period_end="2026-10-31",
            kpi_collector=engine.kpi_collector,
            active_components=engine.config.enabled_components,
        )
        digest = getattr(rep, "sha256_digest", None)
        sig = getattr(rep, "ed25519_signature", None)
        pubkey = gen.signer.public_key_hex if gen.signer else None
        ok = bool(digest) and bool(sig) and bool(pubkey)
        record("signed_report_produced", ok,
               f"digest={(digest or 'YOK')[:24]}… sig={'var' if sig else 'YOK'} key={'var' if pubkey else 'YOK'}")
    except Exception as e:  # pragma: no cover - diagnostic
        record("signed_report_produced", False, f"exception: {type(e).__name__}: {e}")

    # 3) Bağımsız-imza-doğrulaması: imza, payload-üzerinden yeniden-teyit
    try:
        engine = YieldixEngine(PipelineConfig(tenant_id=tenant))
        engine.kpi_collector.record_lead_processed(
            "lead_verify_001", 32.5, is_sql=True, cost_try=Decimal("15.00"))
        gen = MonthlyReportGenerator()
        rep = gen.generate_signed_report(
            tenant_id=tenant, period_start="2026-10-01", period_end="2026-10-31",
            kpi_collector=engine.kpi_collector,
            active_components=engine.config.enabled_components,
        )
        from yieldix.crypto.signer import Ed25519ReportSigner
        payload = MonthlyReportGenerator.to_signable_dict(rep)
        sig = getattr(rep, "ed25519_signature", None)
        pubkey = gen.signer.public_key_hex if gen.signer else None
        verified = Ed25519ReportSigner.verify_signature(payload, sig, pubkey)
        # Tahrif-direnci: imzalı-payload-değiştirilince imza artık-onaylanmamalı
        tampered = dict(payload)
        if "total_leads" in tampered:
            tampered["total_leads"] = (tampered["total_leads"] or 0) + 999
        tampered_ok = not Ed25519ReportSigner.verify_signature(tampered, sig, pubkey)
        ok = bool(verified) and tampered_ok
        record("signature_verifies_and_tamper_resistant", ok,
               f"verify={bool(verified)} tamper-rejected={tampered_ok}")
    except Exception as e:  # pragma: no cover - diagnostic
        record("signature_verifies_and_tamper_resistant", False,
               f"exception: {type(e).__name__}: {e}")

    # 4) Tenant-izolasyonu: AT-179 — configsiz-motor-default-tenant-reddeder
    try:
        import os
        old = os.environ.pop("YIELDIX_TENANT_ID", None)
        os.environ.pop("YIELDIX_ALLOW_DEFAULT_TENANT", None)
        try:
            YieldixEngine()
            ok = False
            detail = "configsiz-engine-KABUL-EDİLDİ ( cross-tenant-açık!)"
        except ValueError:
            ok = True
            detail = "configsiz-engine-reddedildi ( tenant-zorunlu-sağlam)"
        finally:
            if old is not None:
                os.environ["YIELDIX_TENANT_ID"] = old
        record("tenant_isolation_enforced", ok, detail)
    except Exception as e:  # pragma: no cover - diagnostic
        record("tenant_isolation_enforced", False, f"exception: {type(e).__name__}: {e}")

    # 5) Circuit-breaker: aşırı-ihlal → component-shed-edilir
    try:
        from yieldix.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(max_escalation_pct=10.0, max_consecutive_breaches=3)
        for _ in range(4):
            cb.record_interaction("c_verify", has_error=False, was_escalated=True)
            cb.evaluate_cycle("c_verify")
        shed = cb.get_shed_components()
        ok = "c_verify" in shed
        record("circuit_breaker_sheds_on_breach", ok,
               f"shed={shed}")
    except Exception as e:  # pragma: no cover - diagnostic
        record("circuit_breaker_sheds_on_breach", False,
               f"exception: {type(e).__name__}: {e}")

    n_pass = sum(1 for c in checks if c["result"] == "PASS")
    n_all = len(checks)
    verdict = "PASS" if n_pass == n_all else "FAIL"

    if as_json:
        click.echo(json.dumps({"verdict": verdict, "passed": n_pass, "total": n_all,
                               "checks": checks}, ensure_ascii=False, indent=2))
    else:
        click.echo("=" * 70)
        click.echo("  YIELDIX BAĞIMSIZ-DOĞRULAMA ( independent-verify)")
        click.echo("=" * 70)
        for c in checks:
            mark = "✓" if c["result"] == "PASS" else "✗"
            click.echo(f"  [{mark}] {c['result']:<4} {c['check']}")
            click.echo(f"         {c['detail']}")
        click.echo("-" * 70)
        click.echo(f"  SONUÇ: {verdict} — {n_pass}/{n_all} kontrol-geçti")
        click.echo("=" * 70)
    ctx = click.get_current_context()
    ctx.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()

