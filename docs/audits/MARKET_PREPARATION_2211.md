# Market preparation and recovery — build 2211

Baseline: v1.21.110 / build 2210, commit 320a93ca748d2d598ea6c886eccdaca8c2cdd5f1.

## Confirmed behavior and correction

The exact Market directory warming guard already sends a bounded 503 response before scheduling the existing single-flight reconciliation. Secondary-league warming is handled by the Market router. Existing prepared publications remain owned by AssetMarketCache; replacement publication, source admission, memory backoff and last-valid retention are unchanged.

The browser warming template included the shared dark background but never assigned body text color. Ordinary paragraphs and secondary links therefore inherited browser black. It offered only retry links and no completion observation. The existing `/api/market/health` endpoint reconciles a Market and is unsuitable for readiness polling.

Add an explicitly allowlisted, resident-only `AssetMarketCache.preparation_status` accessor and account-bound `/api/account/market-preparation`. This endpoint is intentionally source-independent under the existing league middleware: it never acquires, hydrates, pins or touches a runtime, reads Market storage, reconciles/prepares a generation, or launches providers/analytics. Account authorization is still evaluated on every request. The opaque scope is the existing session/account/league/franchise navigation binding; query parameters cannot select another manager's runtime. Responses are private/no-store. Raw exception strings and operator metrics are never serialized.

## Observable states

| State | Evidence | Browser behavior |
| --- | --- | --- |
| Waiting | No matching resident publication; preparation may be waiting on existing machinery | Honest indeterminate wording, useful retry and Home/My Team actions |
| Preparing | Cache reports an active build | Only existing phases: preparing evidence, building values, loading prepared evidence, publishing |
| Ready | Exact current input marker, store identity and requested generation match a nonempty publication | Recheck account scope, then replace the waiting history entry with the same Market query |
| Last successful Market | Same compatible publication remains usable and last league synchronization failed | Keep values; display its preparation timestamp, separately from Custom limitations |
| Failed | Existing preparation reports failed phase/state | Stop automatic checks; explicit retry uses normal Market entry |
| League update failed | Existing synchronization failure, without a matching usable Market | Explain the source update requirement, preserve saved rankings and offer Home/Market recovery; no raw errors |
| Incompatible | A retained model does not match current input/store/generation requirements | Do not expose retained incompatible prices; explain need for a compatible publication |
| Empty | Compatible publication has zero assets | Do not describe it as a complete Market; offer recovery |

No percentages, coverage counts, ETA, fabricated prices or simulated progress are introduced. The preparation timestamp is not represented as a provider quote timestamp. Stage names do not expose internal exception details.

## Bounded transition and recovery

The visible warming page performs at most twelve sequential GET checks, five seconds apart, within one minute. Each check has an eight-second request timeout. Hidden pages stop checks; page departure and context invalidation abort pending checks. Three consecutive connection failures pause observation. Failed, incompatible, empty, nonresident/unavailable and changed-scope states stop observation immediately. Browser re-entry renders current authoritative state. No local preference or ranking writes occur.

Ready replacement uses the build 2210 navigation API after its scope revalidation, preserving the meaningful prior page and the exact search/filter query. An old readiness result cannot authorize old account/league state; the final Market GET still performs existing source/publication admission. Pending observer responses are fenced by request serial and page visibility/activity. No new background job or cross-tab work coordinator is necessary: readiness checks never prepare anything; explicit Market entry retains existing cache single-flight.

Automatic completion is deliberately bounded, not guaranteed indefinitely. If preparation is not underway, a runtime has been evicted, a source publication is absent/incompatible, resource admission has deferred work, or preparation outlasts the observation window, the page provides a manual retry instead of creating a polling/preparation loop. A ready generation can change again before navigation; the existing Market guard remains authoritative.

## Presentation and preservation

Set preparing-page primary text to #f2f6f8 on #141617 and secondary text to #b6c2cb; primary action is #80df42 with dark text. Retain 44px actions, visible focus, semantic status announcements, native disclosure, responsive wrapping and contextual Back. Ready Market search/filter layout is preserved. The last-successful notice is added outside shared render caches, so account chrome and current failure state cannot be cached in shared Market body artifacts.

No changes to pricing, normalized units, source generations, historical observations, failed-refresh population, subset prices, rank slots, saved Custom order/tiers/flags/revision, Trade verdicts, projections or legal lineup mathematics. Welcome, account admission, exact picks and historical grades remain unchanged. No new permanent storage, cache, worker or dependency.

## Validation and limitations

New disposable controls cover resident producer through account HTTP and controlled Chromium, bounded/hidden/offline checks, scope changes, revoked access, failed worker cleanup and explicit retry, single-flight across repeated views, incompatible/empty publications, actual preparing-page contrast/focus and automatic transition at 320×432, 375×667, 390×844 and desktop. A complete Custom Trade workspace → preparing Market → ready Market → contextual Back control preserves the exact proposal and mode. Existing Market HTTP tests cover last-valid wording/unchanged prices and safe failed-replacement HTML. Guarded source, FOIS, historical, discovery and four solver call sites remain zero during repeated readiness reads.

Original failed and incomplete local/hosted attempts must be preserved separately from final passing artifacts. Local shared-container memory admission is not bypassed; mandatory full validation uses the established isolated hosted 2 GiB workflow. That enforced limit and liveness controls are not proof of broad production capacity. Controlled Chromium is not physical iPhone/Safari. The owner's connected Work-browser control is not exposed in this session; bounded owner-authorized HTTPS observations, when available, are distinct from an authenticated visual walkthrough. No production preferences or league data may be changed for acceptance.

Release requires the complete canonical ten-gate validator, full application regression, hosted Product/security/navigation and lifecycle controls on the exact final candidate. Final results, unsuccessful attempts, source/tree checksums, screenshots and public/read-only production smoke belong in the sanitized Scout evidence handoff; this source audit does not predeclare their outcome.
