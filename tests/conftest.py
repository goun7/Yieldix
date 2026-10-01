"""
Pytest configuration and shared fixtures for Yieldix test suite.
"""

import os
import sys

# LEAD fix: src/ layout — paket sys.path'te degildi (ModuleNotFoundError)
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "..", "src")
for _p in (os.path.abspath(_SRC),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from yieldix.core.engine import YieldixEngine
from yieldix.core.types import InboundLeadPayload, LeadSource, PipelineConfig


@pytest.fixture
def sample_config() -> PipelineConfig:
    return PipelineConfig(
        tenant_id="test_client_01",
        speed_to_lead_sla_seconds=60,
        max_escalation_rate_pct=20.0,
        circuit_breaker_window_days=7,
    )


@pytest.fixture
def engine(sample_config: PipelineConfig) -> YieldixEngine:
    return YieldixEngine(config=sample_config)


@pytest.fixture
def sample_lead() -> InboundLeadPayload:
    return InboundLeadPayload(
        tenant_id="test_client_01",
        lead_id="lead_test_001",
        contact_name="Mehmet Yılmaz",
        contact_phone="+905321112233",
        contact_email="mehmet@example.com",
        source=LeadSource.WEB_FORM,
        intent_summary="Kurumsal filo kiralama hakkında acil bilgi istiyor",
    )
