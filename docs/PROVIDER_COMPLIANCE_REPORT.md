# Provider Compliance Report — DTOS v1.7.2

| Provider | Official source | Access | Classification | Production | Redistribution | Limitation |
|---|---|---|---|---|---|---|
| FantasyCalc | [terms](https://fantasycalc.com/terms-of-usage) | Public JSON endpoint; daily caching encouraged | `approved_enabled` | Enabled for this non-commercial deployment | Attributed derived display | Commercial use requires written permission; no substantial substitute |
| DynastyProcess | [official repository](https://github.com/dynastyprocess/data) | Weekly open CSV under GPL-3.0 | `approved_enabled` | Enabled | Open data with source attribution | Values derive from FantasyPros; same evidence family |
| FantasyPros | [official API](https://api.fantasypros.com/v2/docs) | Authenticated `x-api-key` API | `approved_credentials_required` | Disabled without approved key/rights | License-dependent | Free access is development-only; redistribution requires a commercial agreement |
| KeepTradeCut | keeptradecut.com | No approved machine interface | `unsupported_no_public_interface` | Disabled | Not approved | No scraping, private endpoints, prompt bypass, or ranking reproduction |
| Sleeper League Trade Market | [official API](https://docs.sleeper.com/) | Free read-only API; under 1,000 calls/minute | `approved_enabled` | Enabled | Aggregate only | Active-league evidence is contextual, not fair-value truth |
| DTOS League-Local Market | Cached active-league actions | Internal derivation | `approved_enabled` | Enabled | Private aggregate only | Never contaminates global baseline |
| nflverse | [official releases](https://github.com/nflverse/nflverse-data) | CC-BY-4.0 release datasets | `approved_enabled` | Enabled through Historical Memory | Open data with dataset attribution | Performance/identity evidence, not market consensus |
| DTOS Historical Model | DTOS repository | Internal deterministic model | `approved_enabled` | Enabled | Derived | Independent intrinsic evidence, never market consensus |
| MFL / Fleaflicker trade adapters | Official platform sources | Future adapters | `development_only` | Disabled | Undetermined | Requires access, terms, identity, and privacy review |

The registry records authentication, supported formats, refresh expectations, rate limits, historical and pick coverage, usage rights, asset coverage, identity method, lineage, reliability prior, runtime health, last attempt/success, records, coverage, errors, and reasons. No credentials or private provider payloads are included in this report or public APIs. The audit was verified against official provider documentation on 2026-08-03; permissions must be reviewed again before changing a compliance classification.
