"""Presentation-only explanation contract over accepted, scoped intelligence.

No scoring, thresholds, forecasts, provider calls or persistence belong here.
Adapters supply existing conclusions and exact display values, with references
to the evidence that produced them. Different evidence families may have
different generations, but each family must match the caller's pinned context.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


CONTRACT_VERSION = 'explanation-view-v1'


class EvidenceKind(str, Enum):
    SOURCE = 'Source fact'
    DERIVED = 'DTOS-derived evidence'
    INTERPRETATION = 'DTOS interpretation'


class Availability(str, Enum):
    AVAILABLE = 'available'
    PARTIAL = 'partial'
    UNAVAILABLE = 'unavailable'
    NOT_APPLICABLE = 'not_applicable'
    NO_COMPARABLE_EVIDENCE = 'no_comparable_evidence'


@dataclass(frozen=True)
class EvidenceContext:
    family: str
    scope: str
    generation: str
    methodology: str
    league_id: str | None  # None means explicitly global evidence, not unknown.

    def __post_init__(self):
        if not all((self.family, self.scope, self.generation, self.methodology)):
            raise ValueError('Explanation evidence requires explicit semantic identity')


@dataclass(frozen=True)
class EvidenceItem:
    key: str
    label: str
    kind: EvidenceKind
    context: EvidenceContext
    reference: str
    unit: str
    availability: Availability
    display: str | None

    def __post_init__(self):
        if not all((self.key, self.label, self.reference, self.unit)):
            raise ValueError('Evidence requires identity, reference and explicit unit')
        if not isinstance(self.kind, EvidenceKind) or not isinstance(self.availability, Availability):
            raise ValueError('Evidence kind and availability must be explicit')
        if self.availability in (Availability.AVAILABLE, Availability.PARTIAL):
            if not isinstance(self.display, str) or not self.display:
                raise ValueError('Supported evidence requires an accepted display value')
        elif self.display is not None:
            raise ValueError('Unavailable evidence cannot carry a substitute value')


@dataclass(frozen=True)
class Statement:
    """An accepted reason/conclusion, not a newly inferred explanation."""
    code: str
    text: str
    evidence_keys: tuple[str, ...]

    def __post_init__(self):
        if not self.code or not self.text or not self.evidence_keys:
            raise ValueError('Statements require a structured code and evidence references')
        if not isinstance(self.evidence_keys, tuple):
            raise ValueError('Statement references must be immutable')


@dataclass(frozen=True)
class Explanation:
    subject: str
    league_id: str | None
    contexts: tuple[EvidenceContext, ...]
    evidence: tuple[EvidenceItem, ...]
    conclusion: Statement
    why: tuple[Statement, ...] = ()
    tradeoffs: tuple[Statement, ...] = ()
    confidence: tuple[Statement, ...] = ()
    limitations: tuple[Statement, ...] = ()
    advanced: tuple[Statement, ...] = ()
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self):
        if any(not isinstance(rows, tuple) for rows in (
                self.contexts, self.evidence, self.why, self.tradeoffs,
                self.confidence, self.limitations, self.advanced)):
            raise ValueError('Explanation collections must be immutable')
        if not self.subject or not self.contexts:
            raise ValueError('Explanation requires a subject and pinned evidence contexts')
        identities = [(c.family, c.scope) for c in self.contexts]
        if len(set(identities)) != len(identities):
            raise ValueError('Competing generations/methodologies for one evidence scope')
        if any(c.league_id not in (None, self.league_id) for c in self.contexts):
            raise ValueError('Cross-league explanation evidence')
        keys = [e.key for e in self.evidence]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate explanation evidence identity')
        if any(e.context not in self.contexts for e in self.evidence):
            raise ValueError('Unpinned or incompatible evidence generation')
        for statement in (self.conclusion, *self.why, *self.tradeoffs,
                          *self.confidence, *self.limitations, *self.advanced):
            if not set(statement.evidence_keys).issubset(keys):
                raise ValueError('Statement references missing explanation evidence')
