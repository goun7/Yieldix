"""
Yieldix Monthly Signed SLA Report Generator.
Generates RFC 8032 Ed25519 cryptographically signed reports and JSON-LD provenance.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from yieldix.core.types import MonthlyReportPayload
from yieldix.crypto.signer import Ed25519ReportSigner
from yieldix.telemetry.kpi_collector import KPICollector


class MonthlyReportGenerator:
    """
    Produces tamper-evident monthly SLA reports signed with Ed25519.
    """

    def __init__(self, signer: Ed25519ReportSigner | None = None):
        self.signer = signer or Ed25519ReportSigner()

    def generate_signed_report(
        self,
        tenant_id: str,
        period_start: str,
        period_end: str,
        kpi_collector: KPICollector,
        active_components: list[str],
        circuit_breaker_triggered: bool = False,
    ) -> MonthlyReportPayload:
        metrics = kpi_collector.compute_summary_metrics()

        report_id = f"yrpt_{period_start.replace('-', '')}_{tenant_id}"
        payload_dict = {
            "report_id": report_id,
            "tenant_id": tenant_id,
            "period_start": period_start,
            "period_end": period_end,
            "total_leads": int(metrics["total_leads"]),
            "qualified_sql": int(metrics["qualified_sql"]),
            "p95_speed_to_lead_seconds": metrics["p95_cycle_time_seconds"],
            "cost_per_lead_try": str(metrics["cost_per_lead_try"]),
            "error_rate_pct": metrics["error_rate_pct"],
            "escalation_rate_pct": metrics["escalation_rate_pct"],
            "circuit_breaker_triggered": circuit_breaker_triggered,
            "active_components": active_components,
            "engine_version": "16.0.0",
        }

        digest_hex, sig_hex = self.signer.sign_dict(payload_dict)

        report = MonthlyReportPayload(
            report_id=report_id,
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            total_leads=payload_dict["total_leads"],
            qualified_sql=payload_dict["qualified_sql"],
            p95_speed_to_lead_seconds=payload_dict["p95_speed_to_lead_seconds"],
            cost_per_lead_try=payload_dict["cost_per_lead_try"],
            error_rate_pct=payload_dict["error_rate_pct"],
            escalation_rate_pct=payload_dict["escalation_rate_pct"],
            circuit_breaker_triggered=circuit_breaker_triggered,
            active_components=active_components,
            engine_version=payload_dict["engine_version"],
            sha256_digest=digest_hex,
            ed25519_signature=sig_hex,
        )
        return report

    @staticmethod
    def to_signable_dict(report: MonthlyReportPayload) -> dict[str, Any]:
        return {
            "report_id": report.report_id,
            "tenant_id": report.tenant_id,
            "period_start": report.period_start,
            "period_end": report.period_end,
            "total_leads": report.total_leads,
            "qualified_sql": report.qualified_sql,
            "p95_speed_to_lead_seconds": report.p95_speed_to_lead_seconds,
            "cost_per_lead_try": str(report.cost_per_lead_try),
            "error_rate_pct": report.error_rate_pct,
            "escalation_rate_pct": report.escalation_rate_pct,
            "circuit_breaker_triggered": report.circuit_breaker_triggered,
            "active_components": report.active_components,
            "engine_version": report.engine_version,
        }


    def export_markdown_card(self, report: MonthlyReportPayload) -> str:
        """Produces founder-ready executive markdown report"""
        cpl_status = "✅" if report.cost_per_lead_try <= Decimal("150.00") else "❌"
        sql_status = "✅" if report.qualified_sql >= 20 else "⚠️"
        speed_status = "✅" if report.p95_speed_to_lead_seconds <= 60.0 else "❌"
        err_status = "✅" if report.error_rate_pct < 2.0 else "❌"
        esc_status = "✅" if report.escalation_rate_pct < 20.0 else "🚨"

        return f"""# 📊 YIELDIX AYLIK İMZALI PERFORMANS RAPORU
**Müşteri Kodu:** `{report.tenant_id}` | **Dönem:** {report.period_start} - {report.period_end}
**Rapor No:** `{report.report_id}` | **Durum:** ✅ Ed25519 Mühürlü & Doğrulanabilir

---

### 1. Temel 4-KPI Performans Karnesi
| Metrik | Gerçekleşen | Hedef SLA | Durum |
|---|---|---|---|
| **İşlenen Toplam Lead** | **{report.total_leads}** | - | ✅ |
| **Üretilen SQL (Satış Nitelikli)** | **{report.qualified_sql}** | >= 20 | {sql_status} |
| **P95 Hız-Ajanı Yanıt Süresi** | **{report.p95_speed_to_lead_seconds:.1f} sn** | <= 60 sn | {speed_status} |
| **Nitelikli Lead Başı Maliyet (CPL)** | **{report.cost_per_lead_try:.2f} TL** | <= 150 TL | {cpl_status} |
| **Hata Oranı** | **%{report.error_rate_pct:.2f}** | < 2.0% | {err_status} |
| **Eskalasyon Oranı** | **%{report.escalation_rate_pct:.2f}** | < 20.0% | {esc_status} |

---

### 2. Kriptografik Doğrulama Bilgileri
- **SHA-256 Özeti:** `{report.sha256_digest}`
- **Ed25519 Dijital İmzası:** `{report.ed25519_signature}`
- **Doğrulama Anahtarı:** `{self.signer.public_key_hex}`
"""
