# Trade-time Market evidence audit — no release

Production remains v1.22.24 / build 2239, commit b982e49ded18455e2fcc4fab58610569cc784343, tree 0ca79a715f697147c8081d4d69f1afd7efca9bb4. The application checkout is unchanged. No PR, tag, release or deployment was created.

Start with [REPORT.md](REPORT.md), [coverage.json](coverage.json), [contracts.json](contracts.json) and [SCOUT_HANDOFF.md](SCOUT_HANDOFF.md).

The existing trade detail already has an At the time Market evidence disclosure. This bounded replay includes 25 distinct completed trades and 104 asset appearances but no paired Market observation population. Real quote/trade overlap is UNKNOWN, not a measured 0/25 production coverage rate. Authenticated private inspection was unavailable in this session. No provider acquisition, forced hydration, sync, search, FOIS rebuild or user-data write was attempted.

53 existing unit/HTTP tests and one actual four-size history/navigation browser test passed. Eight disposable price cases characterize existing complete, partial, later, ambiguous, incompatible, old and foreign evidence behavior; their synthetic values do not establish real coverage. Existing old-estimate package admission and latest-incompatible masking are not acceptance of the stricter proposed feature. The phone/browser artifacts are fixtures, not live or physical Safari observations. Full mandatory/canonical/hosted release validation was not rerun because no application change is justified.

Every original console is directly readable and small enough to inspect without splitting. Failed author-method variants remain distinct. Trade-time-market-audit-originals.zip preserves original report, logs, methods and screenshots; its manifest is external to avoid self-reference. manifest.json and SHA256SUMS cover every delivered file. These are author-produced checks, not independent Scout review.
