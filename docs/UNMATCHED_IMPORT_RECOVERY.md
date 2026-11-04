# Unmatched-franchise import recovery — v1.21.62

Baseline: v1.21.61/build 2161, `e694a41b0bc3b02d5754e11706e14cd3f42570f4`, matching main and production before changes.

Both authenticated manual and discovered imports correctly withheld ownership when Sleeper could not identify one supported franchise, but their response offered no navigation. Actual form submissions reproduced the missing recovery links before the correction.

Both handlers now reuse one presentation helper. **Your leagues** opens `/account/leagues`; **Review Sleeper identity** opens `/account/sleeper`. These are existing authenticated destinations, not automatic imports or identity changes. The response explains that saved connections and selection are unchanged and that retry requires corrected source/identity evidence. The existing HTTP status and private/no-store admission remain unchanged.

The correction does not change account writers, import transactions, authorization, CSRF, source preparation, ownership resolution, successful imports, algorithms or caches. No new persistent fields, files, schema or history are required.

`tests.test_unmatched_import_recovery` exercises actual account stores, canonical Sleeper adapters with controlled provider responses, account middleware, both submitted forms, native authenticated browser navigation, keyboard/pointer controls, phone geometry, discovery outage, session expiration, CSRF rejection and a later supported retry. Logical account snapshots and durable file hashes must remain unchanged on rejection and navigation. Existing atomic-import, onboarding and cold-source tests remain in force. The module is included in hosted beginner-navigation CI and full discovery.

Browser evidence is author-operated responsive Chromium, not independent Scout acceptance, physical iPhone/Safari acceptance or proof that an unfamiliar human understands the workflow. Those acceptance requirements remain open.
