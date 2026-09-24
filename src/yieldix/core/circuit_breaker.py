"""
Yieldix Circuit Breaker & Component Shedding Engine.
Implements Theorem 3: Bounded Error Propagation and Dynamic Component Isolation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("Yieldix.CircuitBreaker")


@dataclass
class ComponentMetrics:
    total_calls: int = 0
    error_count: int = 0
    escalation_count: int = 0
    consecutive_breaches: int = 0

    @property
    def error_rate_pct(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return (self.error_count / self.total_calls) * 100.0

    @property
    def escalation_rate_pct(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return (self.escalation_count / self.total_calls) * 100.0


class CircuitBreaker:
    """
    Evaluates streaming or interval-based component telemetry.
    If a component exceeds max_escalation_pct (default 20%) for max_consecutive_breaches (default 7 cycles),
    it trips and dynamically sheds the faulty component from active execution.
    """

    def __init__(
        self,
        max_escalation_pct: float = 20.0,
        max_consecutive_breaches: int = 7,
    ):
        self.max_escalation_pct = max_escalation_pct
        self.max_consecutive_breaches = max_consecutive_breaches
        self._metrics: dict[str, ComponentMetrics] = {}
        self._shed_components: set[str] = set()

    def record_interaction(
        self, component_name: str, has_error: bool = False, was_escalated: bool = False
    ) -> None:
        if component_name not in self._metrics:
            self._metrics[component_name] = ComponentMetrics()

        m = self._metrics[component_name]
        m.total_calls += 1
        if has_error:
            m.error_count += 1
        if was_escalated:
            m.escalation_count += 1

    def evaluate_cycle(self, component_name: str) -> bool:
        """
        Evaluates current metrics for a component.
        Returns True if the component is shed in this cycle, False otherwise.
        """
        if component_name in self._shed_components:
            return False

        metrics = self._metrics.get(component_name)
        if not metrics or metrics.total_calls == 0:
            return False

        if metrics.escalation_rate_pct > self.max_escalation_pct:
            metrics.consecutive_breaches += 1
            logger.warning(
                "Circuit Breaker Warning: Component '%s' escalation rate at %.2f%% (Breach %d/%d)",
                component_name,
                metrics.escalation_rate_pct,
                metrics.consecutive_breaches,
                self.max_consecutive_breaches,
            )
            if metrics.consecutive_breaches >= self.max_consecutive_breaches:
                self._shed_components.add(component_name)
                logger.error(
                    "CIRCUIT BREAKER TRIPPED: Component '%s' has been shed from active pipeline! "
                    "Teorem 3 Koruması: Ana motor güvenliği sağlandı.",
                    component_name,
                )
                return True
        else:
            metrics.consecutive_breaches = 0

        return False

    def is_component_active(self, component_name: str) -> bool:
        return component_name not in self._shed_components

    def get_shed_components(self) -> list[str]:
        return sorted(self._shed_components)

    def reset_component(self, component_name: str) -> None:
        self._shed_components.discard(component_name)
        if component_name in self._metrics:
            self._metrics[component_name] = ComponentMetrics()
        logger.info("Circuit Breaker: Component '%s' has been manually reinstated.", component_name)
