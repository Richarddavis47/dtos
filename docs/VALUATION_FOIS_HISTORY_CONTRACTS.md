# Valuation, FOIS, and Season Archive Contracts

## Canonical valuation layers

Market, intrinsic, contender, and rebuilder values are independent fields. The
intrinsic layer uses DTOS evidence and does not require an external provider
quote. Contender value emphasizes near-term production, lineup utility, risk,
and championship usefulness. Rebuilder value emphasizes dynasty value, the
position-specific age curve, liquidity, and long-term retention. A missing layer
is never replaced by another layer; its contract includes an explicit reason and
limitations list.

## FOIS score and confidence

FOIS evidence signals use 50 as a neutral process midpoint. Model 3.0 maps that
midpoint to 70 on the documented executive scale and preserves relative evidence
differences. Confidence answers how certain DTOS is; completeness describes how
much registered evidence is present. Neither is multiplied into the executive
score. Unavailable metrics are excluded and lower completeness rather than
becoming zero.

Letter-grade thresholds remain the versioned FOIS configuration contract:
A+ 97, A 93, A- 90, B+ 87, B 83, B- 80, C+ 77, C 73, C- 70,
D+ 67, D 63, D- 60, and F below 60.

## Historical season archives

`/history/{year}` and `/api/history/seasons/{year}` read immutable Historical
Memory only. Subresources expose standings, playoffs, weeks, transactions,
drafts, and leaders. Responses include human franchise and player identities,
segment availability, counts, and a completeness state. Current seasons are
reported as current and never assigned unfinished final outcomes. These routes
make zero provider requests and do not mutate records, checkpoints, or jobs.
