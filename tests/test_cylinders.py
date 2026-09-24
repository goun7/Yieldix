"""
Unit tests for the 6 individual Yieldix Cylinders (C1–C6).
"""

import pytest

from yieldix.core.types import InboundLeadPayload, LeadSource
from yieldix.cylinders.cold_email_l2 import ColdEmailL2Manager
from yieldix.cylinders.crm_reactivation import CRMReactivationEngine
from yieldix.cylinders.inbox_triage import InboxIntent, InboxTriageRouter
from yieldix.cylinders.receptionist import VoiceReceptionist
from yieldix.cylinders.speed_to_lead import SpeedToLeadDispatcher
from yieldix.cylinders.web_qualifier import WebQualifier


def test_c1_receptionist_greeting_and_latency():
    rec = VoiceReceptionist(tenant_id="test_01", max_latency_ms=450)
    greeting = rec.generate_greeting("Acme Lojistik", "Ahmet")
    assert "Defne" in greeting
    assert "kaydedilmektedir" in greeting

    res = rec.process_utterance("Fiyatlarınız hakkında bilgi alabilir miyim?", latency_ms=390)
    assert res["latency_budget_met"] is True
    assert res["escalated"] is False

    # Emergency escalation test
    res_esc = rec.process_utterance("Avukatımla görüşeceksiniz, bu bir skandal!", latency_ms=410)
    assert res_esc["escalated"] is True
    assert res_esc["intent"] == "ESCALATION_REQUESTED"


def test_c2_speed_to_lead(sample_lead: InboundLeadPayload):
    async def _run():
        dispatcher = SpeedToLeadDispatcher(max_sla_seconds=60)
        res = await dispatcher.dispatch_call(sample_lead, force_latency_sec=42.0)
        assert res["success"] is True
        assert res["sla_met"] is True
        assert res["latency_seconds"] == 42.0

    import asyncio
    asyncio.run(_run())


def test_c3_web_qualifier(sample_lead: InboundLeadPayload):
    qualifier = WebQualifier(tenant_id="test_01")
    bant = qualifier.evaluate_initial_bant(
        lead=sample_lead,
        budget_answer="100k+ TL",
        authority_answer="Kurucu ve Genel Müdür",
        timeline_answer="Bu ay içinde",
    )
    assert bant.total_score >= 80.0
    assert bant.is_sql is True


def test_c4_crm_reactivation():
    crm = CRMReactivationEngine(tenant_id="test_01", dormant_threshold_days=90)
    
    # Missing consent
    res_no_iys = crm.evaluate_reactivation_candidate(
        lead_id="crm_01", contact_name="Can", days_dormant=120, has_iys_consent=False
    )
    assert res_no_iys["eligible"] is False
    assert res_no_iys["reason"] == "NO_IYS_CONSENT"

    # Eligible
    res_ok = crm.evaluate_reactivation_candidate(
        lead_id="crm_02", contact_name="Ayşe", days_dormant=150, has_iys_consent=True
    )
    assert res_ok["eligible"] is True
    assert "Ayşe" in res_ok["message_draft"]


def test_c5_cold_email_l2_queue():
    manager = ColdEmailL2Manager(tenant_id="test_01", daily_quota=2)
    task_id = manager.enqueue_outbound_draft(
        lead_id="lead_99",
        recipient_email="ceo@targetcorp.com",
        subject="Yanıt süreleri hakkında",
        body_text="Merhaba, 60 saniyede yanıt almanızı sağlıyoruz.",
        company_domain="google.com",
    )
    assert task_id.startswith("l2_")
    assert len(manager.get_pending_tasks()) == 1

    # Review task
    approved = manager.review_draft(task_id, approve=True, reviewer="operator_gokun")
    assert approved is True
    assert len(manager.get_pending_tasks()) == 0


def test_c6_inbox_triage():
    router = InboxTriageRouter(tenant_id="test_01")
    
    # Purchase intent
    res_buy = router.classify_and_route(
        subject="Teklif ve Demo Talebi",
        body="Yeni filomuz için kurumsal demo planlamak istiyoruz.",
        sender_email="buyer@firm.com",
    )
    assert res_buy["intent"] == InboxIntent.PURCHASE_INTENT.value
    assert res_buy["priority"] == "URGENT"

    # Complaint intent
    res_complaint = router.classify_and_route(
        subject="Rezalet Şikayet",
        body="Avukat ile görüştüm dava açacağız bu ne rezalet",
        sender_email="angry@firm.com",
    )
    assert res_complaint["intent"] == InboxIntent.COMPLAINT.value
    assert res_complaint["priority"] == "CRITICAL"

    # Spam or irrelevant
    res_spam = router.classify_and_route(
        subject="Rastgele Mesaj",
        body="Merhaba rastgele bir selam metni.",
        sender_email="random@spam.com",
    )
    assert res_spam["intent"] == InboxIntent.SPAM_OR_IRRELEVANT.value
    assert res_spam["priority"] == "LOW"


def test_c1_receptionist_various_intents():
    rec = VoiceReceptionist(tenant_id="test_01", max_latency_ms=450)
    # Generic greeting without caller name
    generic_greeting = rec.generate_greeting("Acme Lojistik")
    assert "Defne" in generic_greeting
    assert "Ahmet" not in generic_greeting

    # High latency breach test
    res = rec.process_utterance("Paketleriniz hakkında konuşalım.", latency_ms=520)
    assert res["latency_budget_met"] is False


def test_c2_speed_to_lead_edge_cases():
    import asyncio
    dispatcher = SpeedToLeadDispatcher(max_sla_seconds=60)

    # Invalid phone
    lead_bad = InboundLeadPayload(
        tenant_id="test_01",
        lead_id="bad_01",
        contact_name="Bozuk Numara",
        contact_phone="123",
        source=LeadSource.WEB_FORM,
    )
    res_bad = asyncio.run(dispatcher.dispatch_call(lead_bad))
    assert res_bad["success"] is False
    assert res_bad["status"] == "INVALID_PHONE"

    # Intent indicating error / human escalation
    lead_esc = InboundLeadPayload(
        tenant_id="test_01",
        lead_id="esc_01",
        contact_name="Sorunlu",
        contact_phone="+905321112233",
        source=LeadSource.WEB_FORM,
        intent_summary="Hatalı işlem yapıldı hemen insan bağlayın",
    )
    res_esc = asyncio.run(dispatcher.dispatch_call(lead_esc))
    assert res_esc["escalated"] is True


def test_c3_web_qualifier_edge_cases(sample_lead: InboundLeadPayload):
    qualifier = WebQualifier(tenant_id="test_01")
    
    # Low budget & distant timeline
    bant_low = qualifier.evaluate_initial_bant(
        lead=sample_lead,
        budget_answer="bütçe yok",
        timeline_answer="gelecek yıl",
    )
    assert bant_low.budget == 5.0
    assert bant_low.timeline == 8.0
    assert bant_low.is_sql is False


def test_c4_crm_reactivation_edge_cases():
    crm = CRMReactivationEngine(tenant_id="test_01", dormant_threshold_days=90)
    
    # Exactly on boundary (89 days -> not dormant)
    res_89 = crm.evaluate_reactivation_candidate(
        lead_id="crm_89", contact_name="Efe", days_dormant=89, has_iys_consent=True
    )
    assert res_89["eligible"] is False
    assert res_89["reason"] == "NOT_SUFFICIENTLY_DORMANT"

    # 90 days -> eligible
    res_90 = crm.evaluate_reactivation_candidate(
        lead_id="crm_90", contact_name="Efe", days_dormant=90, has_iys_consent=True
    )
    assert res_90["eligible"] is True


def test_c5_cold_email_l2_quota_limit():
    manager = ColdEmailL2Manager(tenant_id="test_01", daily_quota=1)
    t1 = manager.enqueue_outbound_draft("l1", "a@corp.com", "Subj 1", "Body 1", company_domain="google.com")
    t2 = manager.enqueue_outbound_draft("l2", "b@corp.com", "Subj 2", "Body 2", company_domain="google.com")

    # First approval succeeds
    assert manager.review_draft(t1, approve=True, reviewer="admin") is True

    # Second approval fails due to quota limit
    assert manager.review_draft(t2, approve=True, reviewer="admin") is False

    # Reviewing invalid task
    assert manager.review_draft("invalid_task_id", approve=True, reviewer="admin") is False


def test_c6_inbox_triage_all_classes():
    router = InboxTriageRouter(tenant_id="test_01")
    
    # Price inquiry
    res_price = router.classify_and_route("Ücretler", "Fiyatı nedir bu servisin?", "user@test.com")
    assert res_price["intent"] == InboxIntent.PRICE_INQUIRY.value

    # Support
    res_supp = router.classify_and_route("Destek", "Sistem çalışmıyor, teknik arıza var", "user@test.com")
    assert res_supp["intent"] == InboxIntent.TECHNICAL_SUPPORT.value

    # Cancellation
    res_cancel = router.classify_and_route("İptal", "Sözleşmeyi fesih etmek istiyorum", "user@test.com")
    assert res_cancel["intent"] == InboxIntent.CANCELLATION.value

def test_c5_cold_email_rejection_and_bad_domain():
    manager = ColdEmailL2Manager(tenant_id="test_01")
    # AT-160-düzeltmesi: verify_domain_deliverability-artık-gerçek-DNS-sorgular.
    # Varsayılan-dahili-domain-DNS'siz-geçemez — gerçek-SPF+DMARC-yayınlamış
    # bir-domain-ile-enqueue-yapıyoruz ( sandbox-DNS-çalışıyor-kanıtı).
    t1 = manager.enqueue_outbound_draft("lead_rej", "x@corp.com", "Konu", "Metin",
                                        company_domain="google.com")
    
    # Rejection flow
    assert manager.review_draft(t1, approve=False, reviewer="admin_gokun") is True
    assert manager._queue[t1]["status"].value == "REJECTED"

    # Bad domain test (deterministic deliverability rejection)
    with pytest.raises(ValueError, match="is not deliverability compliant"):
        manager.enqueue_outbound_draft("lead_bad_dom", "x@corp.com", "Konu", "Metin", company_domain="broken.domain")


def test_c3_web_qualifier_authority_and_budget_branches(sample_lead: InboundLeadPayload):
    qualifier = WebQualifier(tenant_id="test_01")
    bant = qualifier.evaluate_initial_bant(
        lead=sample_lead,
        budget_answer="25k TL bütçe",
        authority_answer="ekip ile görüşüyoruz",
    )
    assert bant.budget == 18.0
    assert bant.authority == 15.0


