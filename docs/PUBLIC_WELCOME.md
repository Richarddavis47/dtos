# Public welcome and read only demonstration

This v1.21.99/build 2199 release reconciles original candidate `419fb840816c13489c13ec01a11089b704ee3426` with secured build 2198 and implements the approved public landing page at `/welcome`. Anonymous GET/HEAD `/` redirects to it when the application opts into the public entry. The account middleware's default remains backward-compatible for other embedded applications. Authenticated Home, onboarding, private routes, existing deep-link behavior, account creation, recovery and session/CSRF policy remain unchanged.

The public router constructs one immutable HTML document from the reviewed fictional JSON export. It consumes no request/account/league data and performs no runtime lookup, provider, Market preparation, Trade search, solver, FOIS, history or persistent write. Exact `/welcome` and `/welcome/` paths bypass league hydration. The canonical slash redirect and unsupported methods do not turn query parameters into source acquisition. Public HTML is no-store and has a no-script/no-network content security policy. No new cache, process, warehouse or paid service is introduced.

The three read-only examples share one fictional football league and exact assets. The generator under `tools/validation/public_demo_fixture.py` runs existing canonical services offline and freezes only presentation fields into `src/ui/public_demo_data.json`. It is not imported by the public renderer. The generator's tests verify the complete export against its inputs and authoritative results. No demo value is a live provider quote, actual NFL forecast, guaranteed result or predicted manager acceptance.

Native anchor navigation and disclosures need no JavaScript. All displayed assets, fictional labels, values, lineup changes, reserve changes and picks come from the export. Account creation remains publicly reachable under the existing policy; controlled-beta product status does not create an invitation gate or authorize expanded participation. The page preserves that distinction and keeps Create Account subordinate to the demo and Sign In.

## Secured integration and separate operator observation

The previous release hold was resolved separately by builds 2196–2198, independently accepted within their tested scopes. Their inspection authorization, public status allowlists, handled runtime error messages and cached synchronization warning boundaries remain intact. Only the exact anonymous root GET/HEAD redirect and two exact welcome-path source-independent classifications were added to the secured middleware; older middleware implementations were not restored.

A disposable preflight reproduces the separate existing `orchestration.last_error` detail in `/api/platform/health` for the valid inspection credential only. Anonymous requests remain 401 and ordinary members 403, including trailing-slash/encoded paths and optional-auth fixtures. The welcome page neither reads nor embeds that field. This is separately scoped operator-diagnostic hardening, not a public/member exposure or authorization for a broad diagnostic redesign in this release.

Account creation remains publicly reachable under existing rules; controlled-beta status is not an invitation gate and this release does not authorize beta expansion or public promotion. No registration, billing, session or CSRF policy changed.

Run fixture regeneration/equivalence, public/authorized routing and all accepted security regressions; four-viewport controlled Chromium, complete mandatory regression, all ten canonical gates, hosted checks and enforced-2-GiB lifecycle controls are required before release. Physical iPhone/Safari and unfamiliar-human acceptance are separate from author Chromium evidence.
