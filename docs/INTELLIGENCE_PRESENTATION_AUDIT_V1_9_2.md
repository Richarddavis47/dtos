# v1.9.2 Intelligence Presentation Audit

| Surface | Before | Canonical source | Correction | Result |
|---|---|---|---|---|
| Asset Market | IDs and hashes were primary | Market identity and recommendation | Meaning first; provenance collapsed | Human-first comparison |
| Player Dossier | Identity status mixed with player context | Player report and Historical Memory | Current outlook and career evidence separated | Connected dossier |
| Pick Dossier | Canonical ID as title | Historical pick dossier | Draft-year/round title and readable events | Understandable lineage |
| Historical Trade | Raw asset/event identifiers | Historical trade dossier | Readable labels and trade-time limitation | No current value backdating |
| FOIS | API link used as profile | Persisted FOIS 2.0 score | Human profile, explicit rank and evidence | Browsable intelligence |
| Search | Resolution internals shown | Historical graph and FOIS | Human type and availability | Clean result cards |
| Matchups | Preseason zeroes shown as tied | Cached matchup state | Not Started preseason state | Honest status |

## Data DTOS Had But Was Not Using

- Persisted FOIS category scores, ordering, confidence, strengths, and weaknesses now power an Executive Profile.
- Historical season summaries and ownership intervals are presented as a career timeline.
- Pick conversion and ownership events are presented as lineage.
- Brain snapshots, model generations, dataset identities, and canonical IDs remain available without dominating pages.

No new intelligence engine or provider integration was introduced.
