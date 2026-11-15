# Recent carries and targets

Player dossiers reuse shared retained nflverse auxiliary statistics. They do not
use those statistics for fantasy scores or projections: Sleeper remains their
exclusive authority. No Trade, valuation or ranking input changes.

The comparison uses the latest six eligible regular-season game observations in
the selected league season, ordered by actual source game date and split into
preceding three versus latest three. The existing admitted NFL completed-week
boundary excludes current and future weeks. A missing boundary withholds the
comparison; this version does not infer historical or postseason completion from
today's calendar. Future game dates and facts not known at the observation
boundary are excluded. Game identity, week, type and historical team are required.
These are observed-game samples, not full-season coverage or participation proof.

Zero counts are retained. Each metric requires all six counts. Missing counts do
not shift the sample, and carries may remain supported when targets are missing.
Missing weeks within or after the sample withhold comparison, except a bye proven
by the existing complete-schedule contract. Do not infer a bye/DNP from absence.
A team change is disclosed without claiming its causal effect.

The shared store resolves temporal revisions. Opt-in tied-revision detection
prevents a fingerprint tie-break from supplying a workload result. Duplicate
source keys for one game count once; contradictory counts withhold that metric.
Unknown identities/order withhold the comparison. Newly acquired observations are
not backdated as evidence available at earlier trades.

A bounded local read builds the view on each dossier/API request; it owns no
runtime, creates no database, stores no duplicate payload and makes no provider
calls. Newly published source facts change the semantic generation and are
visible on reload across leagues. Failed source checks preserve the valid sample
with a retained-data notice. Observation dates and latest source-check status are
separate; an old complete check does not establish current season completeness.
The existing admitted background refresh schedule and all resource policies are
unchanged. This is not a real-time feed.

Normal presentation leads with the supported change, averages, difference and
sample dates. Game identities, exact knowledge timestamps, totals and methodology
are available under “Game samples and sources.” No snaps, routes, injuries,
forecasts, player-specific upgrades or buy/sell claims are inferred.

Validation uses disposable deterministic retained facts and actual rendered
routes, with responsive Chromium at 320, 375, 390 and desktop widths. Such evidence
is distinct from authenticated live or physical iPhone/Safari acceptance. Exact
candidate identities, originals, limitations and measurements accompany release
evidence; this document alone is not proof of validation or publication.
