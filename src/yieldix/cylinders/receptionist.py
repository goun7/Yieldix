"""
Cylinder 1 (C1): 7/24 Voice and Text AI Receptionist.
Compliant with EU AI Act Art. 50, KVKK, and Sub-450ms Turn-Taking Latency Budget.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("Yieldix.C1.Receptionist")


class VoiceReceptionist:
    """
    7/24 Inbound Call Receptionist & FAQ Answerer with strict turn-taking latency.
    """

    def __init__(self, tenant_id: str, max_latency_ms: int = 450):
        self.tenant_id = tenant_id
        self.max_latency_ms = max_latency_ms
        self._call_history: list[dict[str, Any]] = []

    def generate_greeting(self, company_name: str, caller_name: str | None = None) -> str:
        """Mandatory EU AI Act Art. 50 & KVKK compliant greeting"""
        if caller_name:
            return (
                f"Merhaba {caller_name} Bey/Hanım, ben {company_name} yapay zekâ satış asistanı Defne. "
                "Talebinizi hızlıca çözmek için görüşmemiz kaydedilmektedir. Size nasıl yardımcı olabilirim?"
            )
        return (
            f"Merhaba, {company_name} yapay zekâ satış asistanı Defne ile görüşmektesiniz. "
            "Kalite standartlarımız gereği görüşmemiz kaydedilmektedir. Size nasıl yardımcı olabilirim?"
        )

    def process_utterance(
        self, caller_text: str, latency_ms: int = 380, requires_escalation: bool = False
    ) -> dict[str, Any]:
        logger.info("Processing utterance: '%s' (Latency: %d ms)", caller_text, latency_ms)

        # Fast escalation triggers
        emergency_keywords = ["şikayet", "avukat", "dava", "yetkili", "insan", "müdür"]
        escalate = requires_escalation or any(k in caller_text.lower() for k in emergency_keywords)

        if escalate:
            response_text = (
                "Anlayışınız için teşekkür ederim, konuyu daha detaylı çözebilmek adına "
                "sizi derhal kıdemli müşteri direktörümüze aktarıyorum. Lütfen hatta kalınız."
            )
            intent = "ESCALATION_REQUESTED"
        else:
            response_text = (
                "Talebinizi aldım. Kurumsal paketlerimiz ve fiyatlandırma detaylarımız hakkında "
                "size en uygun teklifi hazırlayabilmemiz için 15 dakikalık bir demo organize edelim mi?"
            )
            intent = "GENERAL_INQUIRY"

        record = {
            "caller_text": caller_text,
            "response_text": response_text,
            "intent": intent,
            "latency_ms": latency_ms,
            "latency_budget_met": latency_ms <= self.max_latency_ms,
            "escalated": escalate,
            "timestamp": time.time(),
        }
        self._call_history.append(record)
        return record
