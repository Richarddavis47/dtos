"""Read-only wording for accepted player facts; no valuation or evidence admission."""

_LONG_TERM = "Long-term scalar unavailable; demonstrated quality, opportunity and longevity remain separate."
_NO_STRENGTH = "No evidence-backed strength exceeds the v1 baseline."
_NO_WEAKNESS = "No current evidence-backed weakness exceeds the v1 threshold."


def outlook_text(text: str) -> str:
    if text == _LONG_TERM:
        return ("A reliable multi-season outlook is not available. Age, NFL status and a weekly projection "
                "do not tell us how long this player will keep producing. Compare current production and Market price separately.")
    return text


def strengths_text(report) -> tuple[str, ...]:
    rows = tuple(item for item in report.strengths if item != _NO_STRENGTH)
    if rows:
        return rows
    return ("This dossier has not established a clear player advantage from supported production or role evidence. "
            "That is an evidence limit, not a negative grade. Review his weekly projection and Market price separately.",)


def weaknesses_text(report) -> tuple[str, ...]:
    rows = tuple(evidence_text(item) for item in report.weaknesses if item != _NO_WEAKNESS)
    if rows:
        return rows
    unverified_age = any(item.factor == 'Age-decline risk' and not item.available for item in report.risk.evidence)
    if unverified_age:
        reason = ("Age-related assessment is incomplete because age is missing. " if report.profile.age is None else
                  "Age-related assessment could not be verified from the available evidence. ")
        return (reason + "No specific weakness is established by the remaining checks; role changes and injury history still need review.",)
    return ("No specific weakness is established by the available age and reported-status checks. "
            "Role changes and injury history are not fully assessed; this is not a guarantee of availability.",)


def evidence_text(text: str) -> str:
    return {
        "Age is at or above the position-specific v1 risk threshold.":
            "His age reaches the model's positional caution range. This is an age-related warning, not a prediction of retirement or future production.",
        "Age is below the position-specific v1 risk threshold.":
            "His age is below the model's positional caution range. That does not establish future seasons of production.",
    }.get(text, outlook_text(text))


def availability_text(field: str, text: str | None) -> str | None:
    """Translate legacy presentation hints without changing or supplementing facts."""
    if field == 'bye_week' and text and text.startswith('Consult canonical_evidence.schedule'):
        return ("His bye week is not confirmed in this player record. Check the NFL schedule before relying "
                "on him to cover another player's bye; missing schedule information does not mean he has no bye.")
    if field == 'production' and text and text.startswith('Consult canonical_evidence for season-scoped production'):
        return ("This player context does not include a season production summary. Review the scored observations "
                "in Career History below; missing production is not zero points.")
    return text
