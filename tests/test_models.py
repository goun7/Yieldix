"""
Tests for Core Data Models, Pydantic Schema Validation, and Edge Constraints.
"""

import pytest
from pydantic import ValidationError

from yieldix.core.types import (
    BANTScore,
    InboundLeadPayload,
    LeadSource,
    PackageTier,
    PipelineConfig,
)


def test_bant_score_bounds():
    # Valid
    b = BANTScore(budget=25.0, authority=25.0, need=25.0, timeline=25.0)
    assert b.total_score == 100.0
    assert b.is_sql is True

    # Invalid > 25
    with pytest.raises(ValidationError):
        BANTScore(budget=30.0)

    # Invalid < 0
    with pytest.raises(ValidationError):
        BANTScore(need=-5.0)


def test_inbound_lead_immutability():
    lead = InboundLeadPayload(
        tenant_id="t1",
        lead_id="l1",
        contact_name="Ahmet",
        contact_phone="+905001234567",
        source=LeadSource.WEB_FORM,
    )
    assert lead.lead_id == "l1"
    # Frozen check
    with pytest.raises(ValidationError):
        lead.contact_name = "Mehmet"


def test_pipeline_config_constraints():
    # Valid
    cfg = PipelineConfig(
        tenant_id="t_custom",
        speed_to_lead_sla_seconds=45,
        max_escalation_rate_pct=15.0,
    )
    assert cfg.speed_to_lead_sla_seconds == 45
    assert cfg.package_tier == PackageTier.ENTERPRISE

    # Invalid SLA (< 10 sec)
    with pytest.raises(ValidationError):
        PipelineConfig(tenant_id="t_err", speed_to_lead_sla_seconds=5)

    # Invalid escalation rate (> 50%)
    with pytest.raises(ValidationError):
        PipelineConfig(tenant_id="t_err", max_escalation_rate_pct=60.0)


def test_lead_source_enums():
    assert LeadSource.WEB_FORM.value == "WEB_FORM"
    assert LeadSource.CRM_REACTIVATION.value == "CRM_REACTIVATION"
    assert LeadSource.VOICE_INBOUND.value == "VOICE_INBOUND"
