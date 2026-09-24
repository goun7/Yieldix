"""
Tests for Telemetry, 4-KPI Aggregation, and Monthly Signed Reports.
"""

from decimal import Decimal

from yieldix.telemetry.kpi_collector import KPICollector
from yieldix.telemetry.reporter import MonthlyReportGenerator


def test_kpi_collector_metrics():
    collector = KPICollector(tenant_id="cust_metrics_test")
    
    # Empty
    empty_res = collector.compute_summary_metrics()
    assert empty_res["total_leads"] == 0.0
    assert empty_res["cost_per_lead_try"] == Decimal("0.00")

    # Add 10 events: 4 SQL, 1 error, 1 escalation, cycle times: 10 to 100
    for i in range(10):
        collector.record_lead_processed(
            lead_id=f"lead_{i}",
            cycle_time_sec=float((i + 1) * 10),  # 10, 20, ..., 100
            is_sql=(i % 2 == 0),                # 5 SQLs
            cost_try=Decimal("15.00"),
            has_error=(i == 9),                 # 1 error (10%)
            escalated=(i == 8),                 # 1 escalation (10%)
        )

    metrics = collector.compute_summary_metrics()
    assert metrics["total_leads"] == 10.0
    assert metrics["qualified_sql"] == 5.0
    assert metrics["cost_per_lead_try"] == Decimal("30.00")
    assert metrics["error_rate_pct"] == 10.0
    assert metrics["escalation_rate_pct"] == 10.0
    assert metrics["avg_cycle_time_seconds"] == 55.0
    assert metrics["p95_cycle_time_seconds"] == 100.0


def test_monthly_report_generation_and_export():
    collector = KPICollector(tenant_id="cust_rep_test")
    collector.record_lead_processed("lead_1", 25.0, is_sql=True, cost_try=Decimal("15.00"))

    rep_gen = MonthlyReportGenerator()
    report = rep_gen.generate_signed_report(
        tenant_id="cust_rep_test",
        period_start="2026-10-01",
        period_end="2026-10-31",
        kpi_collector=collector,
        active_components=["c1_receptionist", "c2_speed_to_lead"],
    )

    assert report.tenant_id == "cust_rep_test"
    assert report.sha256_digest is not None
    assert report.ed25519_signature is not None

    card = rep_gen.export_markdown_card(report)
    assert "YIELDIX AYLIK İMZALI PERFORMANS RAPORU" in card
    assert report.sha256_digest in card
