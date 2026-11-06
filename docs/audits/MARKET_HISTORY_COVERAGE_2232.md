# Market history evidence coverage — build 2232

## Baseline and existing capability

Public production readiness, clean `main` and `origin/main` agreed on v1.22.16 / build 2231, commit `bb71de7faa4ff112500d01f2e3547dbc4652715e`, tree `4e0351fa02f2a3890f1ea15b97e73274d5f56808`. There was no related unfinished PR. The next unused release was v1.22.17 / build 2232. The existing v1.21.70 investigation in `docs/HISTORICAL_MARKET_TREND_INTEGRATION.md` is reused, not rewritten.

The supported path already works: selected canonical price and `market_observation_evidence` -> `CheckpointPipeline._market_observations` -> compact immutable observations plus event references -> `market_trend_evidence` -> `current_comparison` and the existing v2 `MarketTrendService` -> Market directory/trending/detail APIs and selected HTML. Player dossiers link to the same canonical comparison while independently labeling FantasyCalc's raw-provider 30-day change. Neutral history does not use saved Custom values.

No new upstream source-loss defect was established. The original 69 focused producer, store, compatibility, integration and cache controls passed. Compatible fixture observations of 100 and 120 plus the supported current endpoint 200 already yield +100, with the actual retained dates and unknown source freshness preserved. History remains sparse and event driven, not a daily series.

## Confirmed source-to-screen defects

The rendered Market cache key omitted retained observation/reference revisions and the existing UTC-day aging dependency. A disposable actual producer/store/router reproduction warms selected HTML, then admits an earlier compatible 80-valued checkpoint. With the same current publication, APIs correctly return three checkpoints and +120, but the old HTML is byte-identical and still reports two checkpoints and +100. Adding an incompatible format similarly leaves an obsolete numerical comparison visible. These are rendering defects, not evidence that the provider lacks data.

A new public event reference can add a supported milestone without creating another price observation. An observation-only cache token would miss that update. The corrected read-only revision includes high-water marks of the existing observation, reference and checkpoint tables in one indexed scalar query. No payload scan, schema change, capture, provider request or persisted revision is introduced. A separate internal render token also uses the same UTC day as the existing evaluator. It is not a canonical price generation, a freshness claim, a reservation or authorization. Both rendered cache layers use it; their entry/byte bounds and single-flight behavior remain unchanged.

The selected page previously omitted individual prepared checkpoint rows. Its existing disclosure now shows a bounded preview: all supplied rows up to twelve, otherwise the first and latest eleven with an explicit omission notice. The complete canonical comparison remains unchanged and uses all admitted evidence. The current published endpoint is separately labeled and never counted as an additional retained checkpoint. Unknown/incompatible comparison units do not acquire canonical numerical treatment. Dates are observation times, not invented publication/retrieval clocks. No daily points or connecting forecasts are manufactured.

A genuine +0 comparison can be supported before the existing policy has enough observations to classify a trend as stable. The page and trending unavailability reason now distinguish those facts; classification and grouping thresholds are unchanged. Counts describe checkpoints available to this comparison, rather than claiming there are no retained records when some were excluded. Exclusion counts are shown only when the existing diagnostic supplies them.

The explanation adapter also called the entire provider catalogue "Participating provider" even when the admitted current evidence selected only FantasyCalc. It now identifies selected current price providers from that existing structured evidence and labels catalogue entries separately. Historical provider counts remain the actual prepared counts. No unselected provider is promoted into the price or its confidence.

## Preserved numerical and source contracts

The v2 direction, confidence, materiality, volatility, current-endpoint eligibility and comparison calculations are unchanged. `TREND_METHOD_VERSION`, source normalization, consensus selection, units and historical record identities are unchanged. There is no interpolation, blanket import, historical price reconstruction, preference migration or duplicate provider store. Existing missing, future, stale, methodology, provider/context and native-unit boundaries remain fail closed.

The controls distinguish multiple/one/no checkpoints, genuine zero, dated retained evidence, excluded future records, new references without new prices, aging, native units and format changes. Exact picks with the same season/round but different original franchises cannot substitute each other's history. Price movement does not establish a buy recommendation, future return, a historical decision grade or championship causality. FOIS remains RETAINED / NOT REVALIDATED.

The 2 GiB cap, independent FOIS/Trade reserves, lifecycle coordination, cancellation and worker cleanup remain unchanged. Warm-read controls prove no repeated Market preparation, sync, checkpoint ingestion or durable-record change. The only new ordinary-read work is the bounded metadata revision lookup; expanding the disclosure performs no acquisition or calculation.

## Reproduction, validation and limitations

Original logs are preserved separately. The first new test run included two fixture errors: patching a FastAPI annotation's datetime class before lazy route construction, and assuming a nonexistent cache build method. Corrected fixture setup gives six assertion-only baseline failures. Additional provider/zero controls run against the prior validated commit with the same baseline tree. No earlier failure is relabeled a pass.

A pick control initially supplied an expired current quote and was correctly withheld. Its disposable retrieval clock was corrected; no quote-age safeguard was relaxed. Provider catalogue naming was made consistent for both string and metadata entries. All final results must refer to the exact committed candidate, not these intermediate runs.

Rendered tests cover 320x432, 375x667, 390x844 and desktop in two league contexts, before/after compatible publication and an incompatible boundary. They verify actual APIs versus rendered values/dates/counts, keyboard focus, table scrolling, disclosures, no document overflow and no extra disclosure requests. These fixtures use the existing admitted global Market reference; their sample league IDs do not establish current live settings or live historical coverage. Physical iPhone/Safari and comprehensive screen-reader acceptance are not claimed.

This session can read public readiness and authorized Render deployment metadata but has no associated owner-browser control or Render Shell/SSH execution. The external inspection binding's prior 401 is not retried; no secret is exposed or rotated. Current private production checkpoint counts and authenticated historical coverage are unverified. No forced sync, FOIS rebuild, Trade search, cache clear, manual restart or saved-user-data mutation is part of this task.

Local scratch recovery preserves the unchanged 8 GiB validation prerequisite. Only a checksum-verified redundant public download, clean completed duplicate evidence/publisher checkouts, and ignored regenerable bytecode were removed. Frozen Git references, original logs, immutable attachments and source objects remain. Repository compaction retained unreachable objects without pruning and preserved every ref. No production infrastructure or permissions were changed.

Release requires the final exact-source focused tests, complete canonical regression and ten gates, all required hosted Product/security/navigation/tooling/lifecycle jobs, constrained 2 GiB controls, source/manifest checksums and the established two-phase Actions publisher. Passing fixture/replay evidence does not establish private live Market history coverage or recover missing upstream periods.
