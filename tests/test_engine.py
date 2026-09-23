import asyncio

from yieldix.core.engine import YieldixEngine
from yieldix.core.types import InboundLeadPayload, LeadSource, PipelineConfig


def test_engine_ingest_inbound_lead(engine: YieldixEngine, sample_lead: InboundLeadPayload):
    async def _run():
        result = await engine.ingest_inbound_lead(sample_lead)
        assert result["lead_id"] == sample_lead.lead_id
        assert "call_dispatched" in result
        assert result["call_dispatched"]["success"] is True
        assert result["call_dispatched"]["sla_met"] is True
        assert "bant_score" in result
        assert result["bant_score"]["total_score"] > 0
        assert "cycle_time_seconds" in result

    asyncio.run(_run())


def test_engine_full_lifecycle_and_shedding(engine: YieldixEngine):
    async def _run():
        # 1. Process 10 leads
        for i in range(10):
            lead = InboundLeadPayload(
                tenant_id="test_client_01",
                lead_id=f"lead_multi_{i}",
                contact_name=f"Müşteri {i}",
                contact_phone=f"+9053211100{i:02d}",
                source=LeadSource.WEB_FORM,
                intent_summary="Kurumsal filo yönetimi",
            )
            res = await engine.ingest_inbound_lead(lead)
            assert res["lead_id"] == f"lead_multi_{i}"

        # 2. Simulate 7 cycles of high escalation on C2 to trigger Teorem 3 dynamic shedding
        for _ in range(7):
            for _ in range(10):
                engine.circuit_breaker.record_interaction("c2_speed_to_lead", has_error=False, was_escalated=True)
            engine.circuit_breaker.evaluate_cycle("c2_speed_to_lead")

        assert engine.circuit_breaker.is_component_active("c2_speed_to_lead") is False
        assert "c2_speed_to_lead" in engine.circuit_breaker.get_shed_components()

        # 3. Ingest another lead -> C2 should be shed/disabled
        lead_after = InboundLeadPayload(
            tenant_id="test_client_01",
            lead_id="lead_after_shed",
            contact_name="Son Müşteri",
            contact_phone="+905329998877",
            source=LeadSource.WEB_FORM,
        )
        res_after = await engine.ingest_inbound_lead(lead_after)
        assert res_after["call_dispatched"]["status"] == "SHED_OR_DISABLED"

        # 4. Generate signed report
        from yieldix.telemetry.reporter import MonthlyReportGenerator
        rep_gen = MonthlyReportGenerator()
        report = rep_gen.generate_signed_report(
            tenant_id="test_client_01",
            period_start="2026-10-01",
            period_end="2026-10-31",
            kpi_collector=engine.kpi_collector,
            active_components=[c for c in engine.config.enabled_components if engine.circuit_breaker.is_component_active(c)],
            circuit_breaker_triggered=True,
        )
        assert report.circuit_breaker_triggered is True
        assert "c2_speed_to_lead" not in report.active_components

        # Verify signature
        from yieldix.crypto.signer import Ed25519ReportSigner
        assert Ed25519ReportSigner.verify_signature(
            payload=MonthlyReportGenerator.to_signable_dict(report),
            signature_hex=report.ed25519_signature,
            public_key_hex=rep_gen.signer.public_key_hex,
        ) is True

    asyncio.run(_run())


def test_engine_run_daily_cycle_shedding():
    async def _run():
        # AT-179: config'siz-YieldixEngine()-artık-fail-closed ( default-tenant-
        # sessiz-cross-tenant-açık). Dürüst-yol: açık-tenant-id-ile-config.
        engine = YieldixEngine(PipelineConfig(tenant_id="test-tenant-at179"))
        for _ in range(6):
            for _ in range(10):
                engine.circuit_breaker.record_interaction("c1_receptionist", has_error=False, was_escalated=True)
            engine.circuit_breaker.evaluate_cycle("c1_receptionist")

        # 7th breach will occur inside run_daily_cycle
        for _ in range(10):
            engine.circuit_breaker.record_interaction("c1_receptionist", has_error=False, was_escalated=True)

        res = await engine.run_daily_cycle()
        assert "c1_receptionist" in res["newly_shed"]
        assert res["circuit_breaker_tripped"] is True

    asyncio.run(_run())

