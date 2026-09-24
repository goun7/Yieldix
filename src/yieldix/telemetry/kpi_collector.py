"""
Yieldix 4-KPI Telemetry Collector & Snapshot Manager.
Compliant with Swarmax-69 Metric Schema.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


@dataclass
class LeadEvent:
    lead_id: str
    timestamp: float
    cycle_time_sec: float
    is_sql: bool
    cost_try: Decimal
    has_error: bool
    escalated: bool


class KPICollector:
    """
    Collects transaction-level events and computes 4-KPI statistics:
    1. cost_per_lead (CPL)
    2. cycle_time_seconds (Average & P95)
    3. error_rate_pct
    4. escalation_rate_pct
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._events: list[LeadEvent] = []

    def record_lead_processed(
        self,
        lead_id: str,
        cycle_time_sec: float,
        is_sql: bool = False,
        cost_try: Decimal | float = Decimal("15.00"),
        has_error: bool = False,
        escalated: bool = False,
    ) -> None:
        cost_dec = cost_try if isinstance(cost_try, Decimal) else Decimal(str(cost_try))
        event = LeadEvent(
            lead_id=lead_id,
            timestamp=time.time(),
            cycle_time_sec=cycle_time_sec,
            is_sql=is_sql,
            cost_try=cost_dec,
            has_error=has_error,
            escalated=escalated,
        )
        self._events.append(event)

    def compute_summary_metrics(self) -> dict[str, Any]:
        if not self._events:
            return {
                "total_leads": 0.0,
                "qualified_sql": 0.0,
                "cost_per_lead_try": Decimal("0.00"),
                "avg_cycle_time_seconds": 0.0,
                "p95_cycle_time_seconds": 0.0,
                "error_rate_pct": 0.0,
                "escalation_rate_pct": 0.0,
            }

        n = len(self._events)
        sql_count = sum(1 for e in self._events if e.is_sql)
        total_cost = sum((e.cost_try for e in self._events), start=Decimal("0.00"))
        error_count = sum(1 for e in self._events if e.has_error)
        escalated_count = sum(1 for e in self._events if e.escalated)

        cycle_times = sorted([e.cycle_time_sec for e in self._events])
        avg_cycle = sum(cycle_times) / n
        p95_idx = min(n - 1, math.ceil(n * 0.95) - 1)
        p95_cycle = cycle_times[p95_idx]

        cpl = total_cost / Decimal(max(1, sql_count)) if sql_count > 0 else (total_cost / Decimal(n))

        return {
            "total_leads": float(n),
            "qualified_sql": float(sql_count),
            "cost_per_lead_try": cpl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "avg_cycle_time_seconds": round(avg_cycle, 2),
            "p95_cycle_time_seconds": round(p95_cycle, 2),
            "error_rate_pct": round((error_count / n) * 100.0, 2),
            "escalation_rate_pct": round((escalated_count / n) * 100.0, 2),
        }
