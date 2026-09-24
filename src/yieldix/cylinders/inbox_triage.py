"""
Cylinder 6 (C6): Inbox Smart Triage, Sentiment Scoring & SLA Ticket Router.
Classifies inbound messages into 6 discrete intents with emergency escalation.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

logger = logging.getLogger("Yieldix.C6.InboxTriage")


class InboxIntent(str, Enum):
    PURCHASE_INTENT = "PURCHASE_INTENT"      # High priority -> trigger C2 speed call
    PRICE_INQUIRY = "PRICE_INQUIRY"          # Standard sales demo
    TECHNICAL_SUPPORT = "TECHNICAL_SUPPORT"  # Routing to support desk
    COMPLAINT = "COMPLAINT"                  # Immediate executive escalation
    CANCELLATION = "CANCELLATION"            # Churn risk alert
    SPAM_OR_IRRELEVANT = "SPAM_OR_IRRELEVANT"# Auto-archive


class InboxTriageRouter:
    """
    Evaluates incoming emails/messages and dispatches them according to priority and sentiment.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def classify_and_route(self, subject: str, body: str, sender_email: str) -> dict[str, Any]:
        text = f"{subject} {body}".lower()
        t0 = time.time()

        # Heuristic intent classification
        if any(k in text for k in ["fiyat teklifi", "satın almak", "başlamak istiyoruz", "demo"]):
            intent = InboxIntent.PURCHASE_INTENT
            priority = "URGENT"
            action = "TRIGGER_C2_CALL_OR_SCHEDULE"
        elif any(k in text for k in ["fiyatı nedir", "ücret ne kadar", "maliyet"]):
            intent = InboxIntent.PRICE_INQUIRY
            priority = "HIGH"
            action = "REPLY_WITH_BROCHURE_AND_CALENDAR"
        elif any(k in text for k in ["hata", "çalışmıyor", "bozuldu", "teknik"]):
            intent = InboxIntent.TECHNICAL_SUPPORT
            priority = "MEDIUM"
            action = "OPEN_SUPPORT_TICKET"
        elif any(k in text for k in ["şikayet", "rezalet", "dava", "avukat"]):
            intent = InboxIntent.COMPLAINT
            priority = "CRITICAL"
            action = "ESCALATE_TO_FOUNDER"
        elif any(k in text for k in ["iptal", "bırakmak istiyorum", "fesih"]):
            intent = InboxIntent.CANCELLATION
            priority = "HIGH"
            action = "FLAG_CHURN_RISK"
        else:
            intent = InboxIntent.SPAM_OR_IRRELEVANT
            priority = "LOW"
            action = "ARCHIVE"

        routing_result = {
            "tenant_id": self.tenant_id,
            "sender_email": sender_email,
            "intent": intent.value,
            "priority": priority,
            "recommended_action": action,
            "processing_time_ms": (time.time() - t0) * 1000,
        }
        logger.info("Message from %s classified as %s (Priority: %s)", sender_email, intent.value, priority)
        return routing_result
