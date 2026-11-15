"""Recover only source-supported gaps during preparation, never on page reads."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.history_context.coverage import periods
from src.core.intelligence_memory.sleeper_source import SleeperHistoricalSource


def facts(lid='A', season=2025):
    return dict(league={'league_id':lid, 'season':str(season), 'status':'complete'},
        users=[], rosters=[], matchups={}, drafts=[], draft_picks=[], traded_picks=[],
        winners_bracket=[], losers_bracket=[], transactions={str(w):[] for w in range(1,19)})


class HistoryPeriodRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.cache = SleeperSeasonCache(Path(self.directory))
        self.original = facts()
        self.original['transactions']['2'] = [{'transaction_id':'retained', 'type':'trade', 'status':'complete'}]
        self.cache.write(self.cache.normalize('A',2025,self.original))
        self.full = AsyncMock(side_effect=AssertionError('No whole-season fetch for a retained cache'))

    async def recover(self, response, *, cache=None, lid='A', season=2025):
        calls = []
        def handler(request):
            calls.append(request.url.path)
            return response(request) if callable(response) else httpx.Response(response[0], json=response[1])
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        source = SleeperHistoricalSource(base_url='https://fixture.invalid')
        with patch('src.core.intelligence_memory.sleeper_source.httpx.AsyncClient',return_value=client):
            result = await (cache or self.cache).get_or_rebuild(lid,season,self.full,
                recover_transactions=source.recover_transaction_periods)
        return result,calls

    async def test_legacy_missing_week_zero_recovers_only_zero_and_preserves_unknown_old_clocks(self):
        result,calls = await self.recover((200,[]))
        self.assertEqual(calls,['/league/A/transactions/0'])
        self.assertEqual(result.facts['transactions']['0'],[])
        self.assertEqual(result.facts['transactions']['2'],self.original['transactions']['2'])
        metadata = result.facts['transaction_acquisition']['periods']
        self.assertEqual(metadata['0']['state'],'observed_empty')
        self.assertIsNotNone(metadata['0']['retrieved_at'])
        self.assertNotIn('1',metadata)
        self.assertTrue(periods(result.facts,'transactions')['complete_acquisition'])
        again,calls = await self.recover((500,None))
        self.assertFalse(calls)
        self.assertEqual(again.checksum,result.checksum)
        self.full.assert_not_awaited()

    async def test_failed_unavailable_and_malformed_are_not_empty_or_data_loss_and_cool_down(self):
        for response, expected in (((500,{}),'failed'),((404,None),'unavailable'),((200,{}),'malformed')):
            self.cache.write(self.cache.normalize('A',2025,self.original))
            result,calls = await self.recover(response)
            self.assertEqual(len(calls),1)
            self.assertEqual(result.facts['transactions'],self.original['transactions'])
            row = result.facts['transaction_acquisition']['periods']['0']
            self.assertEqual(row['state'],expected)
            self.assertIsNone(row['retrieved_at'])
            self.assertFalse(periods(result.facts,'transactions')['complete_acquisition'])
            _,calls = await self.recover((200,[]))
            self.assertEqual(calls,[])

    async def test_only_missing_buckets_are_requested_and_valid_zero_empty_is_not_missing(self):
        original=deepcopy(self.original)
        original['transactions'].update({'0':[], '3':None, '7':'bad'})
        del original['transactions']['8']
        self.cache.write(self.cache.normalize('A',2025,original))
        result,calls=await self.recover((200,[]))
        self.assertEqual(set(calls),{f'/league/A/transactions/{w}' for w in (3,7,8)})
        self.assertEqual(result.facts['transactions']['2'],original['transactions']['2'])
        self.assertTrue(periods(result.facts,'transactions')['complete_acquisition'])

    async def test_foreign_source_identity_is_never_authority_to_recover(self):
        original=deepcopy(self.original)
        original['league']['league_id']='B'
        self.cache.write(self.cache.normalize('A',2025,original))
        result,calls=await self.recover((200,[]))
        self.assertEqual(calls,[])
        self.assertNotIn('0',result.facts['transactions'])

    async def test_source_bounds_and_refresh_failure_preserve_original_archive(self):
        source=SleeperHistoricalSource()
        for periods_to_get in ((-1,), (19,), (True,), (0,0), tuple(range(20))):
            with self.assertRaises(ValueError):
                await source._transaction_periods(None,'A',2025,periods_to_get)
        before=self.cache.read('A',2025)
        failing=AsyncMock(side_effect=RuntimeError('fixture transport failed'))
        result=await self.cache.get_or_rebuild('A',2025,self.full,recover_transactions=failing)
        self.assertEqual(result.facts['transactions'],before.facts['transactions'])
        self.assertIsNone(result.facts['transaction_acquisition']['periods']['0']['retrieved_at'])

    async def test_concurrent_new_publication_wins_over_old_recovery(self):
        newer=deepcopy(self.original)
        newer['transactions']['0']=[{'transaction_id':'concurrent'}]
        async def recover(*args):
            self.cache.write(self.cache.normalize('A',2025,newer))
            return {},{}
        result=await self.cache.get_or_rebuild('A',2025,self.full,recover_transactions=recover)
        self.assertEqual(result.facts['transactions']['0'],newer['transactions']['0'])

    async def test_ordinary_cache_reads_and_warm_metadata_do_not_call_source_or_decode_again(self):
        result,_=await self.recover((200,[]))
        self.cache.clear_resident()
        fields=('league','transactions','transaction_acquisition')
        first=self.cache.sections('A',2025,fields)
        with patch.object(self.cache,'read',side_effect=AssertionError('No repeat decode on warm read')):
            second=self.cache.sections('A',2025,fields)
        self.assertEqual(second,first)
        self.assertEqual(second['transaction_acquisition'],result.facts['transaction_acquisition'])
        self.full.assert_not_awaited()

    async def test_rendered_history_updates_coverage_and_keeps_supporting_events(self):
        from tests import test_current_season_franchise_history as fixtures
        f=fixtures.CurrentSeasonRuntimeHistoryTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        await f.restore()
        lid=f.runtime.league_id
        year=int(f.data['league']['season'])-1
        original=facts(lid,year)
        f.cache.write(f.cache.normalize(lid,year,original))
        path=f'/history/team/{lid}:franchise:1?season={year}'
        before=f.client.get(path)
        self.assertEqual(before.status_code,200)
        self.assertIn('18 of 19 supported source weeks retrieved',before.text)
        self.assertIn('Not retrieved: weeks 0',before.text)
        _,calls=await self.recover((200,[]),cache=f.cache,lid=lid,season=year)
        self.assertEqual(calls,[f'/league/{lid}/transactions/0'])
        after=f.client.get(path)
        self.assertEqual(after.status_code,200)
        self.assertIn('19 of 19 supported source weeks retrieved',after.text)
        self.assertNotIn('Not retrieved: weeks 0',after.text)
        f.sync.assert_not_called()
