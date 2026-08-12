# Projection & Intelligence Audit Export

DTOS exposes the current canonical projection and intelligence state through:

- `GET /api/audit/projections/current` — structured JSON.
- `GET /api/audit/projections/current.csv` — compact starter-level CSV.

The export exists for calibration, model validation, debugging, and human
review. It is an observer only: it does not synchronize providers, build the
Asset Market, regenerate the Brain, create recommendations, calculate FOIS, or
write historical data. It requires already-retained Projection Intelligence and
Asset Market generations and reads existing FOIS records.

Every starter remains in the export when evidence is missing; unavailable values
are represented by `null` or an explicit unavailable object. Team totals are
sums of the full-precision starter fields in the same response. Difference
buckets are audit-only: Very Close is at most 2 points, Small is at most 5,
Moderate is at most 10, and Large is greater than 10.

The screenshot comparison section is static regression metadata and is not
represented as current-week truth. Snapshot identity fields allow consumers to
reject an export that mixes Projection, Brain, or Asset Market generations.
