# Public welcome candidate

This unreleased v1.21.96/build 2196 candidate implements the approved public landing page at `/welcome`. Anonymous GET/HEAD `/` redirects to it when the application opts into the public entry. The account middleware's default remains backward-compatible for other embedded applications. Authenticated Home, onboarding, private routes, existing deep-link behavior, account creation, recovery and session/CSRF policy remain unchanged.

The public router constructs one immutable HTML document from the reviewed fictional JSON export. It consumes no request/account/league data and performs no runtime lookup, provider, Market preparation, Trade search, solver, FOIS, history or persistent write. Exact `/welcome` and `/welcome/` paths bypass league hydration. The canonical slash redirect and unsupported methods do not turn query parameters into source acquisition. Public HTML is no-store and has a no-script/no-network content security policy. No new cache, process, warehouse or paid service is introduced.

The three read-only examples share one fictional football league and exact assets. The generator under `tools/validation/public_demo_fixture.py` runs existing canonical services offline and freezes only presentation fields into `src/ui/public_demo_data.json`. It is not imported by the public renderer. The generator's tests verify the complete export against its inputs and authoritative results. No demo value is a live provider quote, actual NFL forecast, guaranteed result or predicted manager acceptance.

Native anchor navigation and disclosures need no JavaScript. All displayed assets, fictional labels, values, lineup changes, reserve changes and picks come from the export. Account creation remains publicly reachable under the existing policy; controlled-beta product status does not create an invitation gate or authorize expanded participation. The page preserves that distinction and keeps Create Account subordinate to the demo and Sign In.

## Release hold

The user's required security review confirmed a pre-existing material defect on exact baseline `0724079b22244b83f431a091c3e147b5090aa8f0`: anonymous legacy inspection can serialize the same cached manager, roster and exact-pick facts protected by ordinary team routes. The operations-only token boundary remains effective. Raw cached operational errors can also be published. Evidence uses synthetic sentinels, not production private payloads.

Per the explicit release condition, do not merge, publish a version tag or deploy this candidate while that blocker remains. Remediation requires a separately authorized policy for the intended diagnostic audience and public field minimization; do not broaden authentication changes inside this presentation batch. Preserve public liveness/readiness and existing operator semantics.

Focused tests and screenshots are author evidence only. Full mandatory regressions, all ten canonical gates, hosted/resource validation and independent Scout acceptance remain necessary before release, after the security decision. Physical iPhone/Safari and unfamiliar-human acceptance are not established by controlled Chromium.
