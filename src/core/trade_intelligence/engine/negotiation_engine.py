"""Deterministic negotiation guardrails, never automated negotiation."""
from __future__ import annotations

from src.core.trade_intelligence.models import NegotiationPlan, PartnerReport, TradeProposal


def _labels(assets) -> str:
    return " + ".join(asset.label for asset in assets)


def build_negotiation_plan(proposal: TradeProposal, alternatives: tuple[str, ...], partner: PartnerReport) -> NegotiationPlan:
    sent, received = _labels(proposal.assets_sent), _labels(proposal.assets_received)
    fallback = proposal.assets_sent[:-1] if len(proposal.assets_sent) > 1 else proposal.assets_sent
    return NegotiationPlan(
        f"Offer {sent} for {received}.",
        f"Minimum opening framework: {_labels(fallback)} for {received}.",
        "Maximum: do not add value that pushes the received/offered blend outside the 1.25 boundary.",
        partner.expected_counter,
        "Walk away if the added requested dynasty value moves package balance beyond the documented 25% generation boundary.",
        f"Fallback: { _labels(fallback) } for the primary target, subject to the same balance boundary.",
        alternatives,
        ("Confirm current NFL news before negotiating.", *partner.forecast_notes, "The GM approves every message and roster move."),
    )
