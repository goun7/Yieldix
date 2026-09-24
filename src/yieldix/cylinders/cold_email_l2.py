"""
Cylinder 5 (C5): L2 Human-in-the-Loop Cold Email Pipeline.
Strict anti-spam, RFC 7489 DMARC / SPF compliance, and human approval queue.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from yieldix.core.types import TaskStatus

logger = logging.getLogger("Yieldix.C5.ColdEmailL2")


class ColdEmailL2Manager:
    """
    Manages cold email drafting, domain health verification, and the mandatory L2 human approval gate.
    """

    def __init__(self, tenant_id: str, daily_quota: int = 35):
        self.tenant_id = tenant_id
        self.daily_quota = daily_quota
        self._queue: dict[str, dict[str, Any]] = {}
        self._sent_today_count: int = 0

    def verify_domain_deliverability(self, domain: str) -> dict[str, bool]:
        """
        Checks a domain's outbound email authentication records over live DNS.

        This is NOT a blacklist-string check. It performs real DNS queries:
          * spf_valid — the apex TXT record set contains a "v=spf1" record.
          * dmarc_reject_policy — _dmarc.<domain> publishes a DMARC policy
            ( "v=DMARC1" ) whose p= is reject or quarantine.
          * dkim_valid — DKIM cannot be validated at the domain level, since
            the selector only appears in the signed email header; it is
            reported as False rather than falsely claimed as True.

        Any DNS failure ( NXDOMAIN, SERVFAIL, timeout, no resolver ) fails
        closed: every flag is False, so an unverifiable domain is never
        reported as deliverable.
        """
        try:
            import dns.resolver
            import dns.exception

            def _txts(name: str) -> list[str]:
                # dns.resolver TXT'leri tırnaklı verir ( '"v=spf1 …"' ) — soy
                out = []
                for r in dns.resolver.resolve(name, "TXT", lifetime=3.0):
                    s = str(r).strip()
                    if s.startswith('"') and s.endswith('"'):
                        s = s[1:-1]
                    out.append(s)
                return out

            apex_txts = _txts(domain)
            spf_valid = any(
                t.strip().lower().startswith("v=spf1") for t in apex_txts
            )

            dmarc_txts = _txts(f"_dmarc.{domain}")
            dmarc_reject_policy = any(
                t.strip().lower().startswith("v=dmarc1")
                and any(
                    part.strip().lower().startswith("p=")
                    and part.strip().lower().split("=", 1)[1]
                    in ("reject", "quarantine")
                    for part in t.strip().split(";")
                )
                for t in dmarc_txts
            )
        except Exception as exc:
            # fail-closed: NXDOMAIN, SERVFAIL, timeout veya resolver-yok
            logger.debug("domain-tespiti-basarisiz %s: %s", domain, exc)
            spf_valid = False
            dmarc_reject_policy = False

        return {
            "spf_valid": spf_valid,
            "dkim_valid": False,
            "dmarc_reject_policy": dmarc_reject_policy,
            "deliverability_healthy": spf_valid and dmarc_reject_policy,
        }

    def enqueue_outbound_draft(
        self,
        lead_id: str,
        recipient_email: str,
        subject: str,
        body_text: str,
        company_domain: str = "outbound.yieldix.internal",
    ) -> str:
        """Submits a draft to the mandatory L2 Human Approval queue"""
        task_id = f"l2_{int(time.time() * 1000)}_{lead_id}"
        
        deliverability = self.verify_domain_deliverability(company_domain)
        if not deliverability["deliverability_healthy"]:
            logger.error("Domain %s failed deliverability check! Cannot enqueue draft.", company_domain)
            raise ValueError(f"Domain {company_domain} is not deliverability compliant")

        self._queue[task_id] = {
            "task_id": task_id,
            "tenant_id": self.tenant_id,
            "lead_id": lead_id,
            "recipient_email": recipient_email,
            "subject": subject,
            "body_text": body_text,
            "status": TaskStatus.PENDING,
            "created_at": time.time(),
            "reviewed_at": None,
            "reviewed_by": None,
        }
        logger.info("Draft enqueued in L2 queue: Task %s for %s", task_id, recipient_email)
        return task_id

    def review_draft(
        self, task_id: str, approve: bool, reviewer: str, modified_body: str | None = None
    ) -> bool:
        """Processes human operator approval or rejection"""
        if task_id not in self._queue:
            return False

        task = self._queue[task_id]
        if task["status"] != TaskStatus.PENDING:
            return False

        if approve:
            if self._sent_today_count >= self.daily_quota:
                logger.warning("Daily quota (%d) reached for tenant %s. Cannot dispatch.", self.daily_quota, self.tenant_id)
                return False

            task["status"] = TaskStatus.APPROVED
            if modified_body:
                task["body_text"] = modified_body
            self._sent_today_count += 1
            logger.info("Task %s APPROVED by %s and marked ready for dispatch.", task_id, reviewer)
        else:
            task["status"] = TaskStatus.REJECTED
            logger.info("Task %s REJECTED by %s.", task_id, reviewer)

        task["reviewed_by"] = reviewer
        task["reviewed_at"] = time.time()
        return True

    def get_pending_tasks(self) -> list[dict[str, Any]]:
        return [t for t in self._queue.values() if t["status"] == TaskStatus.PENDING]
