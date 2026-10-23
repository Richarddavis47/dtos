# My DTOS ranking and personal valuation contract

## Ownership and complete universe

Custom Rankings belong to an authenticated account, league and controlled franchise. A read does not initialize durable intent. Explicit creation takes the complete eligible, priced, identified player/pick order from one prepared canonical Market model, including its deterministic tie order. QB/RB/WR/TE and exact owned league picks share that global comparison universe. Unpriced, unresolved and retired assets are not assigned prices. Search/position filters never create another order.

Market pick IDs `pick:2028:1:4` and Trade IDs `2028-R1-4` refer to the same original-franchise asset within the scoped league. Current owner is separate and revalidated. Player identity uses canonical Sleeper IDs, never names. New eligible assets appear for review without a Custom price until Restart. If a saved member loses compatible evidence, numerical Custom evaluation is withheld; the order remains saved.

## Current Market slot curve

Method `personal-current-market-slot-curve-v1` takes all current compatible neutral prices for the saved cohort and sorts those prices descending. Saved overall position 1 receives price slot 1, position 2 receives slot 2, and so on. The distribution, extrema and total are conserved; there is no interpolation, inflation, extrapolation, inferred future price or personal provider quote. Moving upward cannot lower an asset's personal value; ties can leave its value unchanged. This is an explicitly declared manager valuation convention, not a mathematical claim that ordinal opinion proves willingness to pay.

At creation or Restart, the saved order is exactly the current Market order, so every personal value equals its compatible neutral value. Market refreshes can change the price curve but do not reorder saved opinions. For example, neutral A/B/C prices 900/500/100 and saved C/A/B yield personal C/A/B prices 900/500/100. Those remain the manager's opinions; neutral C is still 100 and neutral severe-overpay safeguards still apply. Tier breaks are organizational labels and never change numerical prices. A new asset cannot silently shift the saved cohort's price slots.

Neutral mode uses existing evaluation mathematics. Custom mode keeps neutral Market balance, canonical production and counterparty evidence separately visible, and reuses prepared legal-lineup evidence for personal cost/strategy assessment. A favorite cannot fabricate a material lineup benefit or convert severe neutral Market loss into an endorsed recommendation. An unsupported personal price is unavailable, never zero. Canonical genuine zero remains a supported zero.

## Lifecycle and storage

View Neutral preserves custom order and preferences. Editing increments the document revision. Confirmed Restart replaces baseline/order/tiers with the current compatible universe; separate Target/Avoid/Protect intent survives unless explicitly reset. Strategy changes do not rewrite opinions. No automatic season rollover or ownership-to-player conversion occurs.

One additive table in the existing account SQLite database stores IDs, baseline identity, complete order, optional tier boundaries, sparse flags, revision and timestamps. No prices, projections, roster copies, recommendation history or historical grades are persisted. The representation permits 10,000 distinct ranked IDs and 512 KiB of serialized intent; exceeding either rejects the entire write without truncation. Measured identity/order payloads: 1,000 IDs 25,909 bytes; 5,000 IDs 137,909 bytes; 10,000 IDs 277,911 bytes. A 10,000-asset document with two flags per asset exceeds the byte budget and is rejected atomically. Reads do not create rows or update preference timestamps.

Writes require current scope, live session, CSRF and optimistic revision. Commit-time session/membership checks share the account transaction. A fixed 32-stripe synchronization set coordinates short preference commits with personalized response handoff; it is not a user cache. Per-runtime source publication protection remains separate. No heavyweight acquisition, serialization, discovery or solver work belongs inside these short publication boundaries.

Saved Protect constrains generated outgoing suggestions, while explicit manual packages remain unchanged and show conflicts. Target/Avoid are personal preferences, not opponent intent. Temporary Trade targets and locks remain separate. New personalized responses carry mode, preference revision and compatible source/baseline identity; stale results are rejected rather than reinterpreted. No new personalized evaluation cache or expansion of the Home opportunity cache is introduced.

## Resource and acceptance boundary

Editor reads and edits use prepared directory rows and account intent only. They do not start provider calls, discovery, FOIS, history reconstruction, lineup solving or AI work. Browser pagination bounds rendered controls independently of the full saved order. Existing 2 GiB resource admission, 500 ms liveness and historical integrity requirements remain unchanged. Retained FOIS grades remain RETAINED / NOT REVALIDATED.

Author-run fixtures and responsive Chromium are not independent Scout acceptance, physical iPhone/Safari testing or unfamiliar-human comprehension studies. Release evidence must state these limits and preserve unsuccessful validation runs.
