# Recent player workload — released

Managers can now see whether an existing player's carries or targets rose, fell or stayed unchanged across two observed-game samples. The dossier compares the latest three eligible completed regular-season records with the preceding three, independently per statistic, and shows averages, differences, actual dates and sample sizes. Game records, clocks and methodology stay expandable. This is descriptive usage, not a forecast or recommendation.

**Released and production-ready: v1.22.43/build2258** · [PR347](https://github.com/Richarddavis47/dtos/pull/347) · [Immutable release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.43).

- Deployed commit: `01da0c00f8b657222ed6af719933c3c3da8db3be`
- Exact validated tree: `4d455c93174f246f242f724e23de5fed44ecb4fb`
- Original candidate: `ca685099dd6f7d95090fcee732f0ad3287a50ca6`
- Baseline: `66a54635df075b2a120606ae3e6e3e5a96bd7b21` / tree`129b9423d529d3a5fea70603474f22088a662389`
- Frozen publisher: `310d7c9217e27613ca39f201baab2429079e81e2`
- [Actual application source](https://github.com/Richarddavis47/dtos/tree/01da0c00f8b657222ed6af719933c3c3da8db3be); the evidence branch root is not the released application checkout.

## Supported source-to-screen change

The existing retained NFLverse auxiliary counts previously lacked a recent3-versus3dossier comparison. The extension reuses that shared store and exact player/season evidence without another provider, persistent payload, worker or provider call on render. Retained updates/corrections appear on the next read with their evidence generation. Failed refreshes preserve valid observations and qualify their status.

The matched fictional fixture shows **targets2→5(+3)** and **carries12→6(−6)** per observed game, three records per window. Dates are Sep6–20versusSep27–Oct11,2026UTC. This is a deterministic illustration, not a live NFL player's result. Supported carries survive missing targets; missing records/fields and contradictions never become zero. A team change is qualified without a causal claim. Sleeper alone still supplies fantasy projections and actual scores.

See [source-to-screen findings](SOURCE_TO_SCREEN.md), [full patch](candidate.patch), [source preservation](source-preservation.json), [before](paired-dossier-before/dossier-390.png), [after](paired-dossier-after/dossier-390.png), and [expanded keyboard disclosure](paired-dossier-after/dossier-390-details.png). New controls cover zeros, increases/decreases/unchanged counts, missing periods/stat fields, revisions/conflicts, insufficient samples, season/game-type/knowledge boundaries, transfers and shared updates across isolated leagues.

## Verified validation

| Scope | Result |
|---|---|
| Full local |4555passed/all10canonical gates; Python3.14.3,2GiB/no swap,2CPU,networknone,128MiBtest-driver old-space|
| Full hosted |4555passed/all10canonical gates under2GiB; all13required jobs passed on the exact source|
| Product |1025actual executions (811+35+179), independently reconciled original console|
| Focused |54passed;24new workload IDs verified once in both canonical originals|
| Standing preservation |10normal,123Trade,4harness plus enforced2GiBnative/resource and rendered controls passed|
| Publisher |181local controls/lint; [prepare43777476796](https://github.com/Richarddavis47/dtos/actions/runs/43777476796) and [publish43778121253](https://github.com/Richarddavis47/dtos/actions/runs/43778121253) passed on the same frozen controller|
| Publication |Immutable tag targets the exact merged tree;23attachments/manifests/digests reconciled, Actions upload/readback verified|
| Production |Authorized Render deploy live, exact public ready identity, seven standard public smokes plus one auth boundary, served-JavaScript parity|

Counts overlap; they are not a unique-test total. [Original consoles and event streams](ORIGINAL_LOGS.md) are byte-preserving readable parts, not reconstructed logs. Final console parts are≤120KB; supportingJSON/JSONL/wrapper parts are≤350KB. Earlier60KBparts remain in the original recovery checkpoint; concatenate each current index’s ordered parts and verify its original hash. Earlier setup/focused failures and the original full-local four-error result stay separate in Prior-attempts.zip and the [recovery checkpoint](https://github.com/Richarddavis47/dtos/tree/d440f95ee0b8167410765717120729e47abed235/.task-evidence/recent-workload-2258/checkpoint-local-recovery). The original errors followed actual Trade capacity deferrals. A single matched driver-budget experiment measured113.4MiBless driverPSS, then the complete rerun passed with a tighter test-driver heap. This is not a production optimization or proof that a later pass fully reconstructs the original cause. All application reserves, assertions, timing limits and2GiBprotection stayed unchanged.

## Memory and visual limits

The twelve-cycle/four-concurrent-read fixture sampled **+6.48MiBpeakRSS**, with **+6.45MiBRSSaftercollection**. The299008byte sourceDB stayed identical; FD4→4andthreads1→1. RSS,cgroup and Python allocation peaks have different accounting scopes. Short allocations between samples may be missed. These finite cycles establish neither long-term leak freedom nor private league restoration demand. [Measurement](workload-measurement/memory.json) and [summary](evidence-reconciliation/workload-memory-summary.json) retain exact counters.

New24screenshots cover complete/partial/missing states at320/375/390anddesktop in Chromium, with keyboard/touch controls. The standing76capture comparison reused69identical accepted pixels and inspected7changed source images. Existing Trade/cost/fit, saved state, history navigation, valuation and source contracts were preserved. Physical iPhone/Safari and real-user-study acceptance were not performed.

**Owner-authenticated live workload parity remains unverified:** this session exposed no supported owner browser or RenderShell. Public readiness/Render metadata do not establish dossier-data coverage. Opera was not used. No forced production preparation, sync, Trade search, restart, source acquisition or saved-user mutation occurred. Independent acceptance must use an existing safely usable warm context and stop on deferral.

Comparisons require six compatible REG observations and a confirmed completed-week boundary. Unsupported historical/postseason completion, gaps and conflicting fields remain unknown; useful retained totals/records remain separately available. The public CSV aggregate receipt is upstream research before identity/calendar/retention checks, not an authenticated production denominator.

## Independent handoff and integrity

- [Complete sanitized Scout prompt](SCOUT_DEPLOYED_HANDOFF.md)
- [Readable original-log index](ORIGINAL_LOGS.md)
- [SHA256SUMS](SHA256SUMS) and [original/part manifest](manifest.json)
- [Production verification](production-verified.json), [Render metadata](render-deployment-live-original.json), [tag proof](published-tag-verified.json)
- [Publication certificate](publish-certificate-verified.json), [source/tree merge proof](merge-verified.json), [clean workspace and owned-container cleanup](workspace-completion.json)

The immutable release contains Customer-Experience.zip (the established generic recovery filename;new workload evidence is insideworkload/), Prior-attempts.zip and15original hosted archives. Their published manifest andSHA256SUMSverify those archive bytes. This Git directory's checksum file verifies its readable originals/screenshots and manifest. Ancillary evidence-format/sparse-staging issues are preserved as such; no assertion or application gate was weakened. All other preserved worktrees remain untouched.

Report generated 2026-11-16T00:11:54.545356+00:00.
