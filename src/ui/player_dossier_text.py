"""Read-only wording for accepted player facts; no valuation or evidence admission."""

_LONG_TERM = "Long-term scalar unavailable; demonstrated quality, opportunity and longevity remain separate."
_NO_STRENGTH = "No evidence-backed strength exceeds the v1 baseline."
_NO_WEAKNESS = "No current evidence-backed weakness exceeds the v1 threshold."


def outlook_text(text: str) -> str:
    if text == _LONG_TERM:
        return ("A reliable multi-season outlook is not available. Age, NFL status and a weekly projection "
                "do not tell us how long this player will keep producing. Compare current production and Market price separately.")
    if text == 'Weekly evidence is disclosed at its actual horizon, not converted into a season-value score.':
        return ("A full-season forecast is not available. Use the weekly Sleeper projection for that week's lineup; "
                "it does not establish season-long production or value.")
    return text


def recommendation_text(recommendation) -> str:
    if recommendation.summary == 'No supported aggregate justifies a Buy/Sell posture.':
        return ("DTOS does not have enough supported evidence to recommend buying or selling this player. "
                "Review his current projection, recorded production and Market price before deciding.")
    if recommendation.summary == f'{recommendation.action} is the contextual v1 posture for this Front Office; the GM makes the final decision.':
        return (f"{recommendation.action} reflects this player's assessed fit for your selected team. "
                "Check the supporting evidence and price before acting; this is not a prediction of future production.")
    return recommendation.summary


def strengths_text(report) -> tuple[str, ...]:
    rows = tuple(item for item in report.strengths if item != _NO_STRENGTH)
    if rows:
        return rows
    return ("No clear player strength is established. "
            "This is not a negative grade; review his weekly projection and Market price separately.",)


def weaknesses_text(report) -> tuple[str, ...]:
    rows = tuple(dict.fromkeys(evidence_text(item) for item in report.weaknesses if item != _NO_WEAKNESS))
    if rows:
        return rows
    unverified_age = any(item.factor == 'Age-decline risk' and not item.available for item in report.risk.evidence)
    if unverified_age:
        reason = ("Age is missing; age risk is unknown. " if report.profile.age is None else
                  "Age risk is unverified. ")
        return (reason + "Other checks establish no specific weakness; role changes and injury history need review.",)
    return ("No specific weakness is established by age or reported status. "
            "Role changes, injury history and availability remain uncertain.",)


def evidence_text(text: str) -> str:
    return {
        "Age is at or above the position-specific v1 risk threshold.":
            "Age warrants caution for this position; it does not predict retirement or future points.",
        "Age is below the position-specific v1 risk threshold.":
            "Below this position's age caution range; future production remains unknown.",
    }.get(text, outlook_text(text))


def availability_text(field: str, text: str | None) -> str | None:
    """Translate legacy presentation hints without changing or supplementing facts."""
    if field == 'bye_week' and text and text.startswith('Consult canonical_evidence.schedule'):
        return ("His bye week is not confirmed. Check the schedule before relying "
                "on him for bye cover.")
    if field == 'production' and text and text.startswith('Consult canonical_evidence for season-scoped production'):
        return ("No season result summary is prepared here. Review the scored observations "
                "in Career History below; missing production is not zero points.")
    return text
