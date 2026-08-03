# Team Identity and Headquarters Contract

DTOS resolves every franchise label through one canonical identity boundary. The preferred order is league team name, owner/display name, franchise name, then the neutral `Unassigned Franchise` fallback. Roster identifiers remain valid in URLs, API fields, diagnostics, and inspection metadata, but are not presentation labels.

Team Headquarters presents one canonical Competitive Window Contract and one unified Front Office recommendation. The page order is header, recommendation, core intelligence, roster, assets, activity, and detailed evidence. Detailed evidence is collapsed by default so deterministic calculations remain inspectable without duplicating the executive summary.

During preseason, projected wins, power rank, playoff odds, and championship odds replace empty record and scoring results. Once played-game data exists, current-season performance is shown. Unknown bye weeks are omitted rather than rendered as unavailable.

The canonical HTTP smoke validator renders every Team Headquarters and Front Office context and rejects generic numbered labels such as `Team 4`, `Roster 4`, or `Team Detail`. This gate prevents identity regressions from reaching a release.
