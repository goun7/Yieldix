"""
Tests for Circuit Breaker & Component Shedding (Theorem 3).
"""

from yieldix.core.circuit_breaker import CircuitBreaker


def test_circuit_breaker_healthy_metrics():
    cb = CircuitBreaker(max_escalation_pct=20.0, max_consecutive_breaches=5)
    
    # 10 calls, 1 escalation -> 10% (below 20%)
    for _ in range(9):
        cb.record_interaction("c1_receptionist", has_error=False, was_escalated=False)
    cb.record_interaction("c1_receptionist", has_error=False, was_escalated=True)

    tripped = cb.evaluate_cycle("c1_receptionist")
    assert tripped is False
    assert cb.is_component_active("c1_receptionist") is True


def test_circuit_breaker_dynamic_shedding_trip():
    cb = CircuitBreaker(max_escalation_pct=20.0, max_consecutive_breaches=3)
    
    # Trigger 3 consecutive breach cycles
    for cycle in range(3):
        # 10 calls, 5 escalations -> 50% (> 20%)
        for _ in range(5):
            cb.record_interaction("c5_cold_email_l2", has_error=False, was_escalated=False)
        for _ in range(5):
            cb.record_interaction("c5_cold_email_l2", has_error=False, was_escalated=True)
            
        tripped = cb.evaluate_cycle("c5_cold_email_l2")
        if cycle < 2:
            assert tripped is False
            assert cb.is_component_active("c5_cold_email_l2") is True
        else:
            # 3rd breach -> tripped
            assert tripped is True
            assert cb.is_component_active("c5_cold_email_l2") is False

    assert "c5_cold_email_l2" in cb.get_shed_components()

    # Manual reset test
    cb.reset_component("c5_cold_email_l2")
    assert cb.is_component_active("c5_cold_email_l2") is True
    # Reset non-existent
    cb.reset_component("non_existent_component")


def test_circuit_breaker_zero_calls_and_properties():
    from yieldix.core.circuit_breaker import ComponentMetrics
    m = ComponentMetrics()
    assert m.error_rate_pct == 0.0
    assert m.escalation_rate_pct == 0.0
    
    cb = CircuitBreaker()
    # Evaluate component with no calls
    assert cb.evaluate_cycle("empty_comp") is False
    # Evaluate already shed component
    cb._shed_components.add("already_shed")
    assert cb.evaluate_cycle("already_shed") is False

    # Metrics with calls
    m.total_calls = 10
    m.error_count = 2
    assert m.error_rate_pct == 20.0

