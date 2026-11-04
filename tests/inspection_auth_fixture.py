"""Disposable existing inspection credential for semantic-router contract tests."""
from unittest.mock import Mock, patch

from src.platform.account_context import AccountContextMiddleware


def authorize_inspection(test, app, league_id):
    token = 'disposable-semantic-inspection-only'
    environment = patch.dict('os.environ', {
        'DTOS_INSPECTION_AUTH_TOKEN': token,
        'DTOS_INSPECTION_LEAGUE_ID': league_id,
        'DTOS_INSPECTION_ROSTER_ID': '1',
    })
    environment.start()
    test.addCleanup(environment.stop)
    app.add_middleware(AccountContextMiddleware, service=Mock(), required=True)
    return {'X-DTOS-Inspection-Auth': token}
