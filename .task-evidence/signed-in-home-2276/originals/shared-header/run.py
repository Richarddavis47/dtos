import os
from pathlib import Path

from tools.validation import generate_sanitized_market_fixture as seed
from tools.validation.run_http_validation import main

fixture = Path('/fixture')
for key, name in {
    'CACHE': 'cache.json', 'PROJECTION_DB': 'projections.sqlite3', 'METADATA_DB': 'metadata.sqlite3',
    'INTELLIGENCE_CHECKPOINT': 'intelligence.sqlite3', 'FOIS_DB': 'fois.sqlite3',
    'HISTORY_DB': 'retired.sqlite3', 'ACCOUNT_DB': 'accounts.sqlite3',
}.items():
    os.environ['DTOS_' + key + '_FILE'] = str(fixture / name)
os.environ.update(
    DTOS_DURABLE_HISTORY_REQUIRED='0', SLEEPER_BASE_URL='http://127.0.0.1:9/v1',
    SLEEPER_LEAGUE_ID='1804000000000000000', DTOS_FIXTURE_ROOT=str(fixture),
    DTOS_SLEEPER_SEASON_CACHE_ROOT=str(fixture / 'sleeper-season-cache'),
    DTOS_HISTORY_STORAGE_ROOT=str(fixture), DTOS_VALIDATION_RETAIN_DIAGNOSTICS='1',
)
seed.ASSET_COUNT = 250
data = seed._cache(fixture / 'cache.json')
seed.seed_fixture_projection(data, fixture / 'projections.sqlite3')
seed._canonical_history_fixture(fixture)
raise SystemExit(main())
