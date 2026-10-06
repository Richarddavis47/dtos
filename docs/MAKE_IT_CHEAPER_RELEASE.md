# DTOS v1.21.8 / build 2108 — Make It Cheaper Repair Completeness

## Current-code finding and reproduction

v1.21.7 retained exact locks, current/adopted packages and preview-only repair.
The cheaper repair path still constructed packages using the discovery generator's
nearest-price shortlist (one/four packages per shape) and ten replacements nearest
to the incoming target's price. Cheaper picks could disappear before the price
predicate or canonical evaluator saw them. The 160-evaluation budget was a ceiling
on already shortlisted constructions, not evidence of meaningful repair coverage.

An unchanged-code deterministic fixture with canonical cost 763 and a directly
evaluated, credible 751-cost pick substitution emitted 25 repair packages and
assessed only the anchor-only reduction. The known pick substitution was absent.
The raw cheap-pair funnel counted 3,236 inspected combinations. This fixture
reproduces the omitted route; it is not an exact replay of live projection evidence
or a claim that the live 33-construction count has been reconstructed.

## Correction and contract

Make It Cheaper uses a separate, objective-specific bounded construction path:

1. Try current-offer removals and replacements priced against the asset being
   replaced, including cheaper exact picks.
2. If fewer than three useful alternatives qualify, expand through diversified
   owned-asset pools capped at 18/24 assets and packages up to three outgoing assets.
3. Assess each surviving construction through the unchanged canonical evaluator,
   stopping at three distinct useful alternatives, exhausted constructions or the
   unchanged 160-evaluation request budget.

Strict full-precision canonical outgoing cost must fall. Equal costs and missing
prices never become cheaper claims. Shop's selected outgoing anchor, the original
incoming objective/Trade For target, exact protected/excluded IDs, ownership,
pick identity, legality, capacity and request strategy remain mandatory. Equivalent
same-economic-role pick variants cannot fill every result slot. Strategy changes
interpretation, never canonical prices. No pick projection or horizon aggregation
changes are included.

The response retains original proposal and preview semantics. Cost evidence shows
current outgoing cost, alternative outgoing cost and reduction. Current state only
changes when the user explicitly adopts an alternative. Existing protections,
preview/Keep Original/adoption and targeted reload contracts are unchanged.

## Diagnostics and honest empty results

Technical details record raw constructions, priced-cheaper candidates, named
pre-evaluation prune reasons, evaluated legality/missing-evidence/counterparty/
strategy outcomes, credible cheaper results, displayed results and unassessed
constructions. The generated count conserves pruned + evaluated + unassessed.
Stop reasons distinguish sufficient alternatives, construction exhaustion and
160-evaluation exhaustion. Required missing current prices return unavailable
before comparison. Missing candidate prices are named; other priced routes may
still qualify. Empty results explain actual locks, legality, evidence, bilateral
costs or additional adjustment requirements, without calling unassessed packages
bad or relaxing constraints automatically. Near misses remain evaluated packages.

## Proof and performance scope

The corrected canonical fixture assesses and returns the previously skipped
751-cost route as Worth Pursuing, preserving the selected anchor and both exact
protections. It inspects 54 constructions and assesses two, with every other
construction's prune reason recorded. The first reduction also qualifies under
this deterministic projection fixture; that differs from the live no-result case.

Eighteen focused backend tests cover the 763→751 route, first-failure continuation,
multiple options, exact player/pick locks, another same-round pick, anchors/targets,
equal costs, fractional precision, missing prices, named rejection classes,
progressive expansion, diversity, conservation and full 160-evaluation exhaustion.
Two authenticated local browser tests exercise the actual repair API, cost display,
preview/Keep Original/adoption/reload and no-cheaper diagnostics at 375/390px.
Browser CI includes them. This is responsive Chromium, not physical iPhone/Safari.

Seven interleaved same-evidence warm runs measured median repair time of 44.8ms on
v1.21.7 and 35.5ms after correction. This small deterministic fixture demonstrates no
pathological regression; it is not a production latency promise. The reported
93-second live search was not reproduced and remains a separate performance
investigation. The player-dossier/Trade Center Market discrepancy is also outside
this repair correction and must not be conflated with it.

## Scout live handoff

- Retry the adopted selected-QB + third → target-TE proposal under Win Now with
  the protected player and exact acquired fourth retained. Make It Cheaper should
  assess the credible cheaper alternative-pick route rather than skip it because
  the anchor-only construction was first. Current live evidence still governs.
- Inspect generated/evaluated counts and named prunes. Protect that exact acquired
  fourth while allowing a different fourth. No locks may relax automatically.
- Preview the cheaper package, Keep Original, preview again and deliberately adopt.
  Original/current and complete packages must survive reload/navigation.
- Try a genuinely no-cheaper case. Read its actual blocker or bounded-search
  explanation; it must not claim every possible trade was exhaustively evaluated.
- Try Trade For cheaper repair when a suitable owned package exists; target and
  owner remain fixed. Recheck Recommended/Next Five and Shop usefulness.
- Check 375/390px cost text, long pick identities, technical details, preview
  controls and sticky actions. Record physical iPhone/Safari separately.
- Continue noting the unrelated dossier Market discrepancy and long live search
  latency for their separate workstreams. Never submit a real trade, change a
  lineup or mutate Sleeper for acceptance.
