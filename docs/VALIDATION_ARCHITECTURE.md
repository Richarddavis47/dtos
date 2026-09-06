# Product validation after automated visual retirement

v1.13.6 retires Current Visual/Live Visual, DINS and External Visual Mirror.
This is an explicit product and validation architecture decision, not a passing
reclassification of the old red capture job. Historical published assets remain
immutable; no new screenshot archive, public DOM bundle or mirror is generated.

## Retained safety gates

- Canonical release validator, full regression, compilation, lint, dependencies,
  whitespace, startup, routes/OpenAPI and HTTP smoke.
- Ordinary, archive-warmed and combined-read Linux application lifecycle.
  Application memory admission, responsiveness, single-flight construction,
  semantic compatibility and restart reuse contracts are unchanged.
- Account/league/franchise isolation, large-membership tests, provider-free
  requests, history retirement and historical intelligence remain covered.
- Pure matchup projection reconciliation and accessibility checks were extracted
  from capture tooling. They do not require a capture worker or published PNG.

## Lightweight browser checks

Install `requirements-validation.txt` only in validation environments. Production
uses `requirements.txt` and does not install Playwright, Pillow or Chromium.

`tests.test_product_browser_journey` runs actual product routers and authentication
middleware on a temporary loopback server. Synthetic local state supplies two
accounts and three leagues. Desktop/mobile journeys submit real A→B→A activation
forms, verify franchise chrome and absence of cross-league content, navigate Home,
League, Team HQ, FOIS, Market and Trade workflows, check named controls and reject
unauthorized activation. External synthetic image requests use fixture-only bytes.
Existing Trade browser tests retain package/filter/disclosure interaction coverage;
matchup tests retain numeric/DOM reconciliation. No production state is used.

Successful runs retain test results only. No successful screenshots, cookies, tokens,
DOM archives or public browser artifacts are retained. A failing run may preserve
only bounded sanitized private diagnostics. Browsers and test servers stop on exit.

## Deployment and production

Run full smoke plus real authenticated primary/secondary league browser journeys.
Confirm current franchise/settings/history/FOIS/Market/Trade isolation and account
authorization. Establish stable canonical semantic inputs before controlled restart;
then require compatible artifact reuse, no fresh construction, unchanged generation
and post-restart smoke. A real source transition is classified, never forced compatible.

Semantic `/api/inspect` remains read-only under existing authentication. Its health
reports semantic availability, not screenshot/publication completion. Retired visual
paths return 404. No capture relay or temporary SSH access is needed for acceptance.

Remove obsolete production browser build steps and capture-only settings only after
checking ownership. Retain shared inspection authentication and all canonical storage.
Do not delete prior release assets, user files, source evidence or private account data.
