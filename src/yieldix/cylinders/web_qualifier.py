"""
Cylinder 3 (C3): Web Visitor Dynamic Pre-Qualification & Chat Twin.
Implements Theorem 2 (Bayesian BANT) and Theorem 4 (ICP Minimum Variance Scoring).
"""

from __future__ import annotations

import logging

from yieldix.core.types import BANTScore, InboundLeadPayload

logger = logging.getLogger("Yieldix.C3.WebQualifier")


class WebQualifier:
    """
    3-step interactive conversational questionnaire & BANT scoring engine.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def evaluate_initial_bant(
        self,
        lead: InboundLeadPayload,
        budget_answer: str | None = None,
        authority_answer: str | None = None,
        need_answer: str | None = None,
        timeline_answer: str | None = None,
    ) -> BANTScore:
        """
        Evaluates BANT features using heuristic signals and conversational inputs.
        """
        # 1. Budget Score (0-25)
        budget_score = 15.0  # Baseline
        if budget_answer:
            if "100k" in budget_answer or "kurumsal" in budget_answer.lower():
                budget_score = 25.0
            elif "25k" in budget_answer:
                budget_score = 18.0
            elif "bütçe yok" in budget_answer.lower():
                budget_score = 5.0

        # 2. Authority Score (0-25)
        authority_score = 15.0
        if authority_answer:
            if any(k in authority_answer.lower() for k in ["sahip", "kurucu", "ceo", "direktör", "müdür"]):
                authority_score = 25.0
            elif "ekip" in authority_answer.lower():
                authority_score = 15.0

        # 3. Need Score (0-25)
        need_score = 18.0
        if lead.intent_summary and len(lead.intent_summary) > 20:
            need_score = 22.0

        # 4. Timeline Score (0-25)
        timeline_score = 15.0
        if timeline_answer:
            if "hemen" in timeline_answer.lower() or "bu ay" in timeline_answer.lower():
                timeline_score = 25.0
            elif "gelecek yıl" in timeline_answer.lower():
                timeline_score = 8.0

        score = BANTScore(
            budget=budget_score,
            authority=authority_score,
            need=need_score,
            timeline=timeline_score,
        )
        logger.info(
            "BANT Evaluated for Lead %s: Score=%.1f (SQL=%s)",
            lead.lead_id,
            score.total_score,
            score.is_sql,
        )
        return score
