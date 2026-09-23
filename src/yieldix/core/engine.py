"""
Yieldix Master Orchestration Engine.
Coordinates the 6 cylinders under strict SLA, telemetry, and circuit breaker constraints.
"""

from __future__ import annotations

import logging
import os
import time
from decimal import Decimal
from typing import Any

from yieldix.core.circuit_breaker import CircuitBreaker
from yieldix.core.types import (
    InboundLeadPayload,
    PipelineConfig,
)
from yieldix.cylinders.cold_email_l2 import ColdEmailL2Manager
from yieldix.cylinders.crm_reactivation import CRMReactivationEngine
from yieldix.cylinders.inbox_triage import InboxTriageRouter
from yieldix.cylinders.receptionist import VoiceReceptionist
from yieldix.cylinders.speed_to_lead import SpeedToLeadDispatcher
from yieldix.cylinders.web_qualifier import WebQualifier
from yieldix.telemetry.kpi_collector import KPICollector

logger = logging.getLogger("Yieldix.Engine")


class YieldixEngine:
    """
    Unified Autonomous Revenue Engine (6 Cylinders).
    """

    def __init__(self, config: PipelineConfig | None = None):
        # AT-179-BULGU-4-düzeltmesi: config-YOKSA-sessizce-'default_tenant'-
        # yaratılıyordu — çok-kiracılı-sistemde-cross-tenant-açık ( AT-178'in-
        # tenant-izolasyonu-config'siz-bozar). Bilinen-değer-artık-uyarı-ile-
        # bildirilir; YIELDIX_ALLOW_DEFAULT_TENANT=1-açıkça-beyan-etmeyen-
        # sürümlerde-reddedilir ( fail-closed).
        if config is None:
            _t = os.environ.get("YIELDIX_TENANT_ID", "default_tenant")
            if _t == "default_tenant" and not os.environ.get(
                    "YIELDIX_ALLOW_DEFAULT_TENANT"):
                raise ValueError(
                    "tenant-required: YieldixEngine-config-YOK — 'default_tenant' "
                    "sessiz-cross-tenant-açık. PipelineConfig-geçin ( tenant_id-"
                    "zorunlu) veya YIELDIX_TENANT_ID-env-key — AT-179")
            logging.getLogger(__name__).warning(
                "default-tenant-uyarisi: config-YOK — tenant_id=%r-kullanılıyor "
                "( üretimde-PipelineConfig-geçin) — AT-179", _t)
            config = PipelineConfig(tenant_id=_t)
        self.config = config
        self.circuit_breaker = CircuitBreaker(
            max_escalation_pct=self.config.max_escalation_rate_pct,
            max_consecutive_breaches=self.config.circuit_breaker_window_days,
        )
        self.kpi_collector = KPICollector(tenant_id=self.config.tenant_id)

        # 6 Cylinders Initialization
        self.receptionist = VoiceReceptionist(tenant_id=self.config.tenant_id)
        self.speed_to_lead = SpeedToLeadDispatcher(
            max_sla_seconds=self.config.speed_to_lead_sla_seconds
        )
        self.web_qualifier = WebQualifier(tenant_id=self.config.tenant_id)
        self.crm_reactivation = CRMReactivationEngine(tenant_id=self.config.tenant_id)
        self.cold_email_l2 = ColdEmailL2Manager(tenant_id=self.config.tenant_id)
        self.inbox_triage = InboxTriageRouter(tenant_id=self.config.tenant_id)

    async def ingest_inbound_lead(self, lead: InboundLeadPayload) -> dict[str, Any]:
        """
        Ingests a new lead, records telemetry, and triggers C2 (Speed to Lead) or C3 (Web qualifier).
        """
        logger.info("Ingesting inbound lead: %s (Tenant: %s, Source: %s)", lead.lead_id, lead.tenant_id, lead.source)
        t_start = time.time()

        # Check circuit breaker for speed-to-lead
        c2_active = self.circuit_breaker.is_component_active("c2_speed_to_lead")
        call_result = None

        if c2_active and "c2_speed_to_lead" in self.config.enabled_components:
            call_result = await self.speed_to_lead.dispatch_call(lead)
            self.circuit_breaker.record_interaction(
                "c2_speed_to_lead",
                has_error=not call_result["success"],
                was_escalated=call_result.get("escalated", False),
            )
            cycle_time = call_result.get("latency_seconds", time.time() - t_start)
        else:
            cycle_time = time.time() - t_start
            call_result = {
                "status": "SHED_OR_DISABLED",
                "success": False,
                "latency_seconds": cycle_time,
                "sla_met": False,
            }

        # Initial BANT scoring via WebQualifier heuristic
        bant = self.web_qualifier.evaluate_initial_bant(lead)
        is_sql = bant.is_sql

        # Record telemetry
        self.kpi_collector.record_lead_processed(
            lead_id=lead.lead_id,
            cycle_time_sec=cycle_time,
            is_sql=is_sql,
            cost_try=Decimal("15.00") if call_result.get("success") else Decimal("1.00"),
            has_error=not call_result.get("success", True),
            escalated=call_result.get("escalated", False),
        )

        return {
            "lead_id": lead.lead_id,
            "call_dispatched": call_result,
            "bant_score": {
                **bant.model_dump(),
                "total_score": bant.total_score,
                "is_sql": bant.is_sql,
            },
            "is_sql": is_sql,
            "cycle_time_seconds": cycle_time,
        }

    async def run_daily_cycle(self) -> dict[str, Any]:
        """
        Runs the daily cycle: evaluates circuit breaker across all cylinders,
        processes pending queues, and returns health status.
        """
        shed_events = []
        for comp in self.config.enabled_components:
            tripped = self.circuit_breaker.evaluate_cycle(comp)
            if tripped:
                shed_events.append(comp)

        active_components = [
            c for c in self.config.enabled_components if self.circuit_breaker.is_component_active(c)
        ]

        return {
            "tenant_id": self.config.tenant_id,
            "active_components": active_components,
            "shed_components": self.circuit_breaker.get_shed_components(),
            "newly_shed": shed_events,
            "circuit_breaker_tripped": len(self.circuit_breaker.get_shed_components()) > 0,
        }
