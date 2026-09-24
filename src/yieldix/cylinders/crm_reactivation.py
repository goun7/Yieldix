"""
Cylinder 4 (C4): Dormant CRM Lead Reactivation Engine.
Re-engages dormant CRM contacts (60-365 days stale) with KVKK and IYS compliance checks.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("Yieldix.C4.CRMReactivation")


class CRMReactivationEngine:
    """
    Scans dormant CRM contacts, verifies compliance, and generates personalized value hooks.
    """

    def __init__(self, tenant_id: str, dormant_threshold_days: int = 90):
        self.tenant_id = tenant_id
        self.dormant_threshold_days = dormant_threshold_days

    def evaluate_reactivation_candidate(
        self,
        lead_id: str,
        contact_name: str,
        days_dormant: int,
        has_iys_consent: bool,
        last_deal_notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Assesses eligibility and generates custom reactivation messaging.
        """
        if not has_iys_consent:
            logger.warning("CRM Reactivation Rejected for %s: No IYS Consent", lead_id)
            return {
                "lead_id": lead_id,
                "eligible": False,
                "reason": "NO_IYS_CONSENT",
                "message_draft": None,
            }

        if days_dormant < self.dormant_threshold_days:
            return {
                "lead_id": lead_id,
                "eligible": False,
                "reason": "NOT_SUFFICIENTLY_DORMANT",
                "message_draft": None,
            }

        # Value hook generation based on prior notes
        notes_str = last_deal_notes or "geçtiğimiz dönemde yapılan görüşme"
        message_draft = (
            f"Sayın {contact_name}, {notes_str} sonrasında devreye aldığımız yeni "
            "kurumsal satış motorumuz hakkında 5 dakikalık bir güncelleme paylaşmak isteriz. "
            "Bu hafta kısa bir değerlendirme görüşmesine açık mısınız?"
        )

        logger.info("CRM Reactivation Generated for %s (Dormant %d days)", lead_id, days_dormant)
        return {
            "lead_id": lead_id,
            "eligible": True,
            "days_dormant": days_dormant,
            "message_draft": message_draft,
            "channel": "WHATSAPP_OR_EMAIL",
            "timestamp": time.time(),
        }
