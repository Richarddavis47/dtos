# DTOS Product Design System 1.0

## Purpose

Design System 1.0 makes DTOS read as one Front Office Operating System. It is a
server-rendered presentation contract: domain engines remain authoritative for
facts and recommendations, while shared UI helpers provide consistent hierarchy,
language, actions, evidence, freshness, empty states, and responsive behavior.

## Page header contract

Every public decision page includes a specific dynamic title, one-sentence
purpose, league or Front Office context, latest cached synchronization time, and
one clear primary action with an optional secondary action. Internal identifiers
remain in machine contracts but are not displayed as user-facing labels.

## Recommendation contract

Every primary recommendation presents the recommendation, confidence, primary
reason, collapsed supporting evidence, expected impact, direct action, and known
limitations. The shared renderer consumes existing intelligence outputs and never
evaluates an asset or fabricates missing evidence.

## Grade contract

League-relative grades show grade, score, league rank, percentile, confidence,
plain-language meaning, and collapsed reasoning. A grade is a decision aid, not an
unexplained label.

## Visual and accessibility primitives

The system centralizes panel hierarchy, actions, freshness, empty states, focus
visibility, minimum mobile target size, and horizontal table containment.
Responsive rules preserve reading order while collapsing multi-column layouts.

## Empty and offseason states

Empty states explain what is missing and when it can become available. Preseason
surfaces use projections, odds, and planning language rather than treating 0-0
records as meaningful standings.

## Ownership

`src/ui/design_system.py` owns presentation helpers and CSS. `dtos_app.py` applies
shared page chrome. Routes and components supply domain content; intelligence and
service layers remain the only owners of calculations.
