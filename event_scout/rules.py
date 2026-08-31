from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import EligibilityDecision, MedicalEvent


def evaluate_event(event: MedicalEvent, now: datetime, lookahead_days: int = 370) -> EligibilityDecision:
    reasons: list[str] = []
    if not event.medical_relevance:
        reasons.append("not-medical")
    if not event.event_relevance:
        reasons.append("not-an-event")
    if event.free_status != "confirmed":
        reasons.append("not-confirmed-free")
    if event.mode not in {"online", "onsite_thailand", "hybrid_thailand"}:
        reasons.append("not-online-or-thailand")
    if event.start_at is None:
        reasons.append("missing-date")
    else:
        start_utc = event.start_at.astimezone(timezone.utc)
        now_utc = now.astimezone(timezone.utc)
        if start_utc <= now_utc:
            reasons.append("event-past")
        if start_utc > now_utc + timedelta(days=lookahead_days):
            reasons.append("event-too-far")
    if event.registration_closed:
        reasons.append("registration-closed")
    if not event.registration_url:
        reasons.append("missing-registration-link")

    score = event.confidence
    if event.certificate_status in {"confirmed", "cme_cpd"}:
        score += 3
    if event.mode == "onsite_thailand":
        score += 2
    if event.mode == "hybrid_thailand":
        score += 3
    return EligibilityDecision(accepted=not reasons, reasons=tuple(reasons), score=score)
