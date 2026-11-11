# Draft capital after a prepared exchange — build 2247

## Boundary

The existing Trade evaluator already admits exact canonical pick assets and capital-policy evidence. This extension adds ownership-only presentation, not a new capital assessment or recommendation rule. `services/trade_capital_inventory.py` reconciles retained canonical ledger tuples `(season, round, original roster)` with native Sleeper transfers and each franchise's owned-pick view. A complete inventory must cover every configured round/original franchise for every season actually in that ledger. No absent season is created. Native historical transfers outside the retained future ledger are not converted into new picks.

A bounded recorded snapshot contains the active franchise's exact inventory, exchange movements, configured rounds, observed seasons, franchise labels, and a deterministic ownership digest. Missing inventory/configuration withholds counts while otherwise verified proposal movements remain available. Duplicate, conflicting, foreign-league or incorrectly owned evidence withholds ambiguous movements as well. Complete empty inventory supports zero; missing evidence never does.

## Recorded comparisons

Both Evaluate and generated offers use the same snapshot producer after existing bilateral evaluation. The two-offer comparison reads each assessment's captured snapshot. It does not consult today's inventory, optimize another lineup or issue HTTP requests. A shared keep-roster inventory is displayed only when both recorded ownership generations agree; incompatible individual inventories remain separate. Projection/Market compatibility continues to govern lineup/value comparisons independently of ownership.

The existing 12k/512-node analytical disclosure bound remains unchanged. Ownership has its own bounded envelope (10k serialized characters, at most eight 1400-character chunks) within the unchanged 64k context/100k offer/200k selected-offer limits. Missing/truncated snapshots produce unknown inventory, never reconstructed counts. No permanent price/source store or account preference is added.

## Verification plan and limits

`tests/test_trade_capital_inventory.py` covers exact same-round original franchises, native ownership, own/acquired firsts, player-only exchanges, complete zero, partial/legacy evidence, invalid identities, isolated leagues and recorded ownership changes. An authenticated prepared Evaluate route proves supported inventory survives missing projections.

`tests/test_trade_capital_browser.py` uses real authenticated disposable one-QB/K/DEF and Superflex evaluations, two alternatives, exact disclosure identities, four viewports, keyboard disclosure, reload, changed ownership and league switching. Existing comparison journeys additionally cover touch, replacement/removal and contextual return. The hosted Product workflow includes the new controls; canonical discovery includes them in full regression. Source-pinned original logs and screenshots, not this plan, establish final outcomes.

Fixtures do not establish live owner acceptance. No production Trade search, synchronization, preference update or real exchange is performed by validation. Historical attempt logs are retained separately, including development fixture/rendering failures. Physical iPhone/Safari acceptance is not claimed.
