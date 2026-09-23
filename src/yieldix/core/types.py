"""
Yieldix Core Type Definitions & Pydantic Data Models.
"""

from __future__ import annotations

import time
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class LeadSource(str, Enum):
    WEB_FORM = "WEB_FORM"
    FACEBOOK_LEAD = "FACEBOOK_LEAD"
    VOICE_INBOUND = "VOICE_INBOUND"
    CRM_REACTIVATION = "CRM_REACTIVATION"
    MANUAL_IMPORT = "MANUAL_IMPORT"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PackageTier(str, Enum):
    ENTRY = "ENTRY"
    GROWTH = "GROWTH"
    ENTERPRISE = "ENTERPRISE"


class BANTScore(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    budget: float = Field(default=0.0, ge=0.0, le=25.0)
    authority: float = Field(default=0.0, ge=0.0, le=25.0)
    need: float = Field(default=0.0, ge=0.0, le=25.0)
    timeline: float = Field(default=0.0, ge=0.0, le=25.0)

    @property
    def total_score(self) -> float:
        return self.budget + self.authority + self.need + self.timeline

    @property
    def is_sql(self) -> bool:
        return self.total_score >= 60.0


class InboundLeadPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    lead_id: str
    contact_name: str
    contact_phone: str
    contact_email: str | None = None
    source: LeadSource
    intent_summary: str = ""
    company_name: str | None = None
    timestamp_utc: float = Field(default_factory=time.time)


class PipelineConfig(BaseModel):
    tenant_id: str
    package_tier: PackageTier = PackageTier.ENTERPRISE
    speed_to_lead_sla_seconds: int = Field(default=60, ge=10, le=300)
    max_escalation_rate_pct: float = Field(default=20.0, ge=5.0, le=50.0)
    circuit_breaker_window_days: int = Field(default=7, ge=1, le=30)
    enabled_components: list[str] = Field(
        default_factory=lambda: [
            "c1_receptionist",
            "c2_speed_to_lead",
            "c3_web_qualifier",
            "c4_crm_reactivation",
            "c5_cold_email_l2",
            "c6_inbox_triage",
        ]
    )
    monthly_retainer_try: Decimal = Field(default=Decimal("45000.00"))
    setup_fee_try: Decimal = Field(default=Decimal("150000.00"))


class MonthlyReportPayload(BaseModel):
    report_id: str
    tenant_id: str
    period_start: str
    period_end: str
    total_leads: int
    qualified_sql: int
    p95_speed_to_lead_seconds: float
    cost_per_lead_try: Decimal = Field(default=Decimal("0.00"))
    error_rate_pct: float
    escalation_rate_pct: float
    circuit_breaker_triggered: bool
    active_components: list[str]
    engine_version: str = "16.0.0"
    sha256_digest: str | None = None
    ed25519_signature: str | None = None

