# Roster Intelligence Engine v1

## Purpose

Roster Intelligence answers: **How likely is this room to help win championships over the next several seasons?** It treats depth as one dimension, never as a substitute for elite quality.

## Architecture

The Intelligence Orchestrator invokes Roster Intelligence after Decision, Asset, Front Office, Trade, and Market Intelligence. The engine consumes their immutable results and publishes presentation-neutral `RosterReport`, `PositionRoomReport`, and `PlayerCard` contracts. Application services continue to depend only on the orchestrator.

## Evaluation model

Each position independently evaluates Elite Talent, Depth, Weekly Advantage, Longevity, Market Value, and Championship Impact. Position-specific published weights emphasize top-end leverage while retaining injury protection and depth. Grades use a deterministic A+ through F scale.

Player cards preserve independent dynasty, contender, rebuilder, and market values. Tiers describe the resulting asset profile; they do not replace the underlying evidence.

Roster identity uses separate current and future Decision Engine horizons, starter age when available, and elite-asset concentration. No identity is inferred from manager personality.

## Explainability and limitations

Every room includes dimension scores, calculation details, observable data, and concise reasoning. Missing market, production, or projection data is disclosed. When live feeds are unavailable, DTOS uses traceable Asset Intelligence opportunity and risk proxies rather than fabricating precision.

## Extension points

Future providers can add historical production, projections, injury probabilities, age curves, and league supply through the orchestrator without changing Team Headquarters or duplicating roster formulas.
