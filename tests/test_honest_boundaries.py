"""
Dürüst-sınır genişletme testleri — YIELDIX ( 53 → 73+ hedefi).

Mevcut-suitenin-açık-bıraktığı kenarları-hedefler:
  * devre-kesici: recovery-breach-counter-sıfırlama, sınır-tam-üzerinde,
    eşik-altı-kurtarma, shed-sonrası-kayıt
  * tenant-izolasyon: env-geçersiz-kılma, çapraz-tenant-KPI, config-doğrulama
  * KPI-hesaplama: tek-olay, tüm-hata, tüm-eskalasyon, Decimal-maliyet
  * hasher/signer: kanonik-sıralama-duyarlılığı, bozuk-imza-şekli
"""

import asyncio
import os
from decimal import Decimal

import pytest

from yieldix.core.circuit_breaker import CircuitBreaker, ComponentMetrics
from yieldix.core.engine import YieldixEngine
from yieldix.core.types import (
    BANTScore, InboundLeadPayload, LeadSource, PipelineConfig, PackageTier,
)
from yieldix.crypto.hasher import canonical_json_bytes, sha256_digest_hex
from yieldix.crypto.signer import Ed25519ReportSigner
from yieldix.telemetry.kpi_collector import KPICollector


# --------------------------------------------------------------------------
# Devre-kesici kenar-durumları
# --------------------------------------------------------------------------
def test_breach_counter_resets_when_rate_below_threshold():
    """
    Ardışık-ihlal-sayacı yalnızca escalation-oranı eşiğin-altına-düşünce
    sıfırlanır ( biriken oranların-seyrelmesi-gerekir). Tek-bir-sağlıklı
    etkileşim-tek-başına-sayacı-sıfırlamaz — bu gerçek-davranıştır.
    """
    cb = CircuitBreaker(max_escalation_pct=20.0, max_consecutive_breaches=5)
    # 10 etkileşim: 3 yükseltme = %30 > %20 → 2 ihlal-biriktir
    for _ in range(3):
        cb.record_interaction("c", was_escalated=True)   # %30
    for _ in range(7):
        cb.record_interaction("c", was_escalated=False)
    cb.evaluate_cycle("c")
    assert cb._metrics["c"].escalation_rate_pct == 30.0
    assert cb._metrics["c"].consecutive_breaches == 1
    # Daha-fazla-sağlıklı-etkileşim: oranı %10'a-düşür
    for _ in range(21):
        cb.record_interaction("c", was_escalated=False)  # 3/31 ≈ %9.7
    cb.evaluate_cycle("c")
    assert cb._metrics["c"].consecutive_breaches == 0


def test_threshold_boundary_does_not_trip():
    """
    Tam-%20 eşiği AŞMAZ ( > karşılaştırması): 20% > 20% yanlış → ihlal-yok.
    Sınır-tam-üstünde DEĞİL, tam-üstünde-olması-gereken-kenar-budur.
    """
    cb = CircuitBreaker(max_escalation_pct=20.0, max_consecutive_breaches=1)
    for _ in range(20):
        cb.record_interaction("c", was_escalated=True)   # tam %20
    for _ in range(80):
        cb.record_interaction("c", was_escalated=False)
    assert cb._metrics["c"].escalation_rate_pct == pytest.approx(20.0)
    assert cb.evaluate_cycle("c") is False


def test_single_breach_above_threshold_trip():
    cb = CircuitBreaker(max_escalation_pct=10.0, max_consecutive_breaches=1)
    cb.record_interaction("c", was_escalated=True)       # %100 > %10
    assert cb.evaluate_cycle("c") is True
    assert "c" in cb.get_shed_components()


def test_shed_component_stays_shed_across_cycles():
    """Shed-edilen-bileşen sonraki-döngülerde-shed-kalmalı."""
    cb = CircuitBreaker(max_escalation_pct=10.0, max_consecutive_breaches=1)
    cb.record_interaction("c", was_escalated=True)
    cb.evaluate_cycle("c")
    assert cb.evaluate_cycle("c") is False   # zaten-shed → False
    assert cb.is_component_active("c") is False


def test_error_only_does_not_trip_on_escalation_gate():
    """Hata sayılır-ama yalnız-escalation-oranı ihlali-tetikler."""
    cb = CircuitBreaker(max_escalation_pct=20.0, max_consecutive_breaches=1)
    for _ in range(10):
        cb.record_interaction("c", has_error=True)       # %0 eskalasyon
    assert cb.evaluate_cycle("c") is False


def test_reset_component_after_trip_reinstates():
    cb = CircuitBreaker(max_escalation_pct=10.0, max_consecutive_breaches=1)
    cb.record_interaction("c", was_escalated=True)
    cb.evaluate_cycle("c")
    assert not cb.is_component_active("c")
    cb.reset_component("c")
    assert cb.is_component_active("c")
    assert cb._metrics["c"].consecutive_breaches == 0


def test_get_shed_components_sorted():
    cb = CircuitBreaker(max_escalation_pct=10.0, max_consecutive_breaches=1)
    for name in ("zeta", "alpha", "mid"):
        cb.record_interaction(name, was_escalated=True)
        cb.evaluate_cycle(name)
    assert cb.get_shed_components() == ["alpha", "mid", "zeta"]


def test_component_metrics_error_rate_zero_calls():
    m = ComponentMetrics()
    assert m.error_rate_pct == 0.0
    assert m.escalation_rate_pct == 0.0


# --------------------------------------------------------------------------
# Tenant-izolasyon kenar-durumları ( AT-179)
# --------------------------------------------------------------------------
def test_engine_rejects_default_tenant_by_default(monkeypatch):
    """Config'siz-motor default_tenant'i reddetmeli ( fail-closed)."""
    monkeypatch.delenv("YIELDIX_TENANT_ID", raising=False)
    monkeypatch.delenv("YIELDIX_ALLOW_DEFAULT_TENANT", raising=False)
    with pytest.raises(ValueError, match="tenant-required"):
        YieldixEngine()


def test_engine_allows_default_tenant_with_explicit_flag(monkeypatch):
    monkeypatch.setenv("YIELDIX_TENANT_ID", "default_tenant")
    monkeypatch.setenv("YIELDIX_ALLOW_DEFAULT_TENANT", "1")
    engine = YieldixEngine()
    assert engine.config.tenant_id == "default_tenant"


def test_engine_accepts_env_tenant_id(monkeypatch):
    monkeypatch.setenv("YIELDIX_TENANT_ID", "env-tenant-42")
    monkeypatch.delenv("YIELDIX_ALLOW_DEFAULT_TENANT", raising=False)
    engine = YieldixEngine()
    assert engine.config.tenant_id == "env-tenant-42"


def test_two_engines_have_isolated_kpi_collectors():
    """Farklı-tenant-motorları KPI-durumunu-paylaşmaz."""
    a = YieldixEngine(PipelineConfig(tenant_id="iso-A"))
    b = YieldixEngine(PipelineConfig(tenant_id="iso-B"))
    a.kpi_collector.record_lead_processed("la", 10.0, is_sql=True, cost_try=Decimal("15"))
    assert a.kpi_collector.compute_summary_metrics()["total_leads"] == 1
    assert b.kpi_collector.compute_summary_metrics()["total_leads"] == 0


def test_pipeline_config_tenant_id_defaults_and_types():
    """tenant_id bir-zorunlu-alan; geçerli-değer-üretir."""
    cfg = PipelineConfig(tenant_id="acme-corp")
    assert cfg.tenant_id == "acme-corp"
    assert isinstance(cfg.monthly_retainer_try, Decimal)
    assert isinstance(cfg.setup_fee_try, Decimal)


def test_pipeline_config_sla_bounds():
    with pytest.raises(Exception):
        PipelineConfig(tenant_id="t", speed_to_lead_sla_seconds=5)
    with pytest.raises(Exception):
        PipelineConfig(tenant_id="t", speed_to_lead_sla_seconds=500)


def test_disabled_component_skipped_in_cycle():
    """enabled_components-dışındaki-bileşen döngüde-değerlendirilmez."""
    import asyncio
    cfg = PipelineConfig(tenant_id="t", enabled_components=["c1_receptionist"])
    engine = YieldixEngine(cfg)
    result = asyncio.run(engine.run_daily_cycle())
    assert "c1_receptionist" in result["active_components"]
    assert "c6_inbox_triage" not in result["active_components"]


def test_pipeline_config_escalation_bounds():
    with pytest.raises(Exception):
        PipelineConfig(tenant_id="t", max_escalation_rate_pct=1.0)
    with pytest.raises(Exception):
        PipelineConfig(tenant_id="t", max_escalation_rate_pct=80.0)


def test_pipeline_config_window_bounds():
    with pytest.raises(Exception):
        PipelineConfig(tenant_id="t", circuit_breaker_window_days=0)
    with pytest.raises(Exception):
        PipelineConfig(tenant_id="t", circuit_breaker_window_days=60)


def test_disabled_component_skipped_in_cycle():
    """enabled_components-dışındaki-bileşen döngüde-değerlendirilmez."""
    cfg = PipelineConfig(tenant_id="t", enabled_components=["c1_receptionist"])
    engine = YieldixEngine(cfg)
    result = asyncio.run(engine.run_daily_cycle())
    assert "c1_receptionist" in result["active_components"]
    assert "c6_inbox_triage" not in result["active_components"]


# --------------------------------------------------------------------------
# KPI-hesaplama kenar-durumları
# --------------------------------------------------------------------------
def test_kpi_single_event_pct_is_zero():
    kpi = KPICollector(tenant_id="t")
    kpi.record_lead_processed("l1", 30.0, is_sql=True, cost_try=Decimal("20"))
    m = kpi.compute_summary_metrics()
    assert m["error_rate_pct"] == 0.0
    assert m["escalation_rate_pct"] == 0.0
    assert m["p95_cycle_time_seconds"] == 30.0
    assert m["avg_cycle_time_seconds"] == 30.0


def test_kpi_all_errors_and_escalations():
    kpi = KPICollector(tenant_id="t")
    for i in range(4):
        kpi.record_lead_processed(f"l{i}", 10.0, has_error=True, escalated=True)
    m = kpi.compute_summary_metrics()
    assert m["error_rate_pct"] == 100.0
    assert m["escalation_rate_pct"] == 100.0


def test_kpi_cpl_uses_sql_denominator():
    """CPL = toplam-maliyet / SQL-sayısı ( SQL>0 iken)."""
    kpi = KPICollector(tenant_id="t")
    kpi.record_lead_processed("l1", 10.0, is_sql=True, cost_try=Decimal("30"))
    kpi.record_lead_processed("l2", 10.0, is_sql=False, cost_try=Decimal("10"))
    m = kpi.compute_summary_metrics()
    assert m["cost_per_lead_try"] == Decimal("40.00")   # 40/1 SQL


def test_kpi_cpl_falls_back_to_total_when_no_sql():
    kpi = KPICollector(tenant_id="t")
    kpi.record_lead_processed("l1", 10.0, is_sql=False, cost_try=Decimal("10"))
    kpi.record_lead_processed("l2", 10.0, is_sql=False, cost_try=Decimal("30"))
    m = kpi.compute_summary_metrics()
    assert m["cost_per_lead_try"] == Decimal("20.00")   # 40/2 lead


def test_kpi_accepts_float_cost():
    kpi = KPICollector(tenant_id="t")
    kpi.record_lead_processed("l1", 5.0, is_sql=True, cost_try=12.5)   # float
    m = kpi.compute_summary_metrics()
    assert m["cost_per_lead_try"] == Decimal("12.50")


def test_kpi_p95_index_ceiling():
    """Az-olayda P95-index taşmamalı ( n-1 ile-sınırlandırılmış)."""
    kpi = KPICollector(tenant_id="t")
    for i in range(3):
        kpi.record_lead_processed(f"l{i}", float(i + 1) * 10)
    m = kpi.compute_summary_metrics()
    assert 10.0 <= m["p95_cycle_time_seconds"] <= 30.0


# --------------------------------------------------------------------------
# Kriptografi kenar-durumları
# --------------------------------------------------------------------------
def test_canonical_json_is_order_independent():
    a = canonical_json_bytes({"x": 1, "y": 2, "z": Decimal("3")})
    b = canonical_json_bytes({"z": Decimal("3"), "y": 2, "x": 1})
    assert a == b


def test_sha256_changes_on_payload_change():
    h1 = sha256_digest_hex({"k": 1})
    h2 = sha256_digest_hex({"k": 2})
    assert h1 != h2
    assert len(h1) == 64


def test_signer_roundtrip_and_reject():
    signer = Ed25519ReportSigner()
    payload = {"a": 1, "b": "x"}
    digest, sig = signer.sign_dict(payload)
    assert Ed25519ReportSigner.verify_signature(payload, sig, signer.public_key_hex)
    assert not Ed25519ReportSigner.verify_signature(
        {"a": 2, "b": "x"}, sig, signer.public_key_hex)


def test_verify_rejects_bad_hex():
    signer = Ed25519ReportSigner()
    _, sig = signer.sign_dict({"a": 1})
    assert not Ed25519ReportSigner.verify_signature(
        {"a": 1}, "not-hex!!", signer.public_key_hex)
    assert not Ed25519ReportSigner.verify_signature(
        {"a": 1}, sig, "deadbeef")


def test_verify_rejects_wrong_key():
    signer = Ed25519ReportSigner()
    other = Ed25519ReportSigner()
    _, sig = signer.sign_dict({"a": 1})
    assert not Ed25519ReportSigner.verify_signature(
        {"a": 1}, sig, other.public_key_hex)


# --------------------------------------------------------------------------
# BANT-modeli kenar-durumları
# --------------------------------------------------------------------------
def test_bant_score_sums_and_sql_threshold():
    assert BANTScore(budget=25, authority=25, need=25, timeline=25).total_score == 100
    assert BANTScore(budget=25, authority=25, need=25, timeline=25).is_sql
    assert not BANTScore(budget=0, authority=0, need=0, timeline=0).is_sql
    # tam-60 → SQL-eşiği ( >=)
    assert BANTScore(budget=20, authority=20, need=20, timeline=0).is_sql


def test_bant_score_rejects_out_of_range():
    with pytest.raises(Exception):
        BANTScore(budget=30)   # > 25


def test_lead_source_enum_values():
    assert LeadSource.WEB_FORM.value == "WEB_FORM"
    assert PackageTier.ENTERPRISE.value == "ENTERPRISE"


def test_inbound_lead_accepts_all_sources():
    for src in LeadSource:
        lead = InboundLeadPayload(
            tenant_id="t", lead_id=f"l-{src.value}", contact_name="N",
            contact_phone="+15550001111", source=src)
        assert lead.source is src
