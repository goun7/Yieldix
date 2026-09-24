"""
Yieldix: Autonomous B2B Revenue Engine & Speed-to-Lead Orchestrator.
Version: 16.0.0
"""

__version__ = "16.0.0"
__author__ = "Yieldix Contributors"

from yieldix.core.circuit_breaker import CircuitBreaker
from yieldix.core.engine import YieldixEngine
from yieldix.core.types import (
    BANTScore,
    InboundLeadPayload,
    LeadSource,
    MonthlyReportPayload,
    PipelineConfig,
    TaskStatus,
)

__all__ = [
    "BANTScore",
    "CircuitBreaker",
    "InboundLeadPayload",
    "LeadSource",
    "MonthlyReportPayload",
    "PipelineConfig",
    "TaskStatus",
    "YieldixEngine",
    "__version__",
]
