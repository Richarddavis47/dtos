import unittest
from copy import deepcopy
from unittest.mock import patch
from types import SimpleNamespace
from tests.lineup_review_fixture import authenticated_prepared
from src.core.intelligence.team_strength import prepare_for_data

case=unittest.TestCase()
try:
    fixture, data, service, now = authenticated_prepared(case, empty=False, uncertain="bq")
    client=fixture.f.f.client
    previous=deepcopy(data["season_matchups"])
    schedule=data["team_strength"]["lineup_review_schedule"]
    roster=data["teams"][0]["players"]
    print("Prepared starters before:",previous["weeks"]["8"]["rows"][0]["starters"])
    paths=("/teams/1","/matchups/1?week=8")
    for path in paths:
        first=client.get(path)
        stale=client.get(path)
        assert first.status_code==stale.status_code==200
        assert 'If Example BQ 1 is ruled out' not in first.text+stale.text
        assert data["season_matchups"]["observed_at"]==previous["observed_at"]
        print(path,"ordinary reads kept the prepared roster and did not add a fallback")
    # Simulate a new compatible Sleeper roster and matchup publication, retaining the same projection snapshot.
    publication=deepcopy(previous)
    for p in roster:
        if p["id"]=="1-bq":
            p.update(roster_slot="Starter",starter_index=0)
        if p["id"]=="1-q":
            p.update(roster_slot="Bench",starter_index=None)
    publication["weeks"]["8"]["rows"][0]["starters"][0]="1-bq"
    publication["observed_at"]=publication["weeks"]["8"]["observed_at"]=now.isoformat()
    data["season_matchups"]=publication
    fact=dict(provider='nflverse',family='schedule',season=2026,week=8,fingerprint='fixture-game-8',
              values=dict(game_type='REG',home_team='BUF',away_team='NYJ',kickoff=schedule['games']['8:BUF']['kickoff']))
    with patch("services.global_evidence.retained_global_evidence", return_value=SimpleNamespace(read=lambda *a,**k:[fact])):
        prepare_for_data(service,data)
    print("Prepared starters after:",publication["weeks"]["8"]["rows"][0]["starters"])
    for path in paths:
        page=client.get(path)
        assert page.status_code==200 and 'If Example BQ 1 is ruled out, Example Q 1 can cover QB.' in page.text
        print(path,"now shows the same fallback from the newer prepared roster")
finally:
    case.doCleanups()
