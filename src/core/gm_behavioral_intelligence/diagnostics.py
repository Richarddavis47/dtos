"""Disposable league/franchise observations; no grades, prices or personality model.

Uses the existing verified Sleeper season cache and prepared current buckets.
Historical manager attribution follows the canonical season-owner contract;
current ownership is never backdated into historical decisions.
"""
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations, islice
import json
from threading import Lock, RLock
from time import perf_counter

from src.core.fois.attribution import belongs_to_manager
from src.core.fois.configuration import DEFAULT_FOIS_CONFIGURATION
from src.core.history_context.assets import future_pick_id
from src.core.history_context.coverage import periods
from src.core.history_context.timestamps import canonical_utc_timestamp
from src.core.team_identity import canonical_team_name

METHOD = 'league-gm-observations-3'
MAX_ROWS = 10_000
MAX_SEASONS = 20
MAX_ENTRIES = 4
MAX_BYTES = 2_097_152
MINIMUM_TENDENCY = DEFAULT_FOIS_CONFIGURATION.minimum_sample_sizes['tendencies']
FIELDS = ('type', 'status', 'transaction_id', 'league_id', 'roster_ids', 'adds',
          'drops', 'draft_picks', 'waiver_budget', 'created', 'status_updated', 'settings')


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def _rid(value):
    return str(int(value)) if not isinstance(value, bool) and str(value).isdigit() and int(value) > 0 else None


def _transaction(row):
    result = {key: row[key] for key in FIELDS if key in row} if isinstance(row, dict) else {}
    participants = result.get('roster_ids')
    if isinstance(participants, list):
        normalized = [_rid(rid) for rid in participants]
        if None not in normalized and len(set(normalized)) == len(normalized):
            # Enumeration is unordered; directed consideration remains untouched.
            result['roster_ids'] = sorted(normalized, key=int)
    return result


def _current_rows(data):
    buckets = data.get('season_transactions') or {}
    if isinstance(buckets, dict):
        for key in sorted((k for k in buckets if str(k).isdigit() and 0 <= int(k) <= 18), key=int):
            if isinstance(buckets[key], list):
                yield from buckets[key]
    active = data.get('transactions') or []
    if isinstance(active, list):
        yield from active


def _clock(raw, now):
    stamp = canonical_utc_timestamp(raw.get('status_updated'))
    created = canonical_utc_timestamp(raw.get('created'))
    if stamp and datetime.fromisoformat(stamp) <= now and (not created or stamp >= created):
        return stamp
    return None  # Creation alone never establishes when a trade completed.


def _movement_evidence(raw):
    """Original directed consideration; repeated legs collapse, conflicts qualify."""
    raw_participants = raw.get('roster_ids')
    if not isinstance(raw_participants, list):
        return (), (), False, {}
    participants = [_rid(r) for r in raw_participants]
    if len(participants) < 2 or None in participants or len(set(participants)) != len(participants):
        return (), (), False, {}
    participants = tuple(sorted(participants, key=int))
    categories = dict.fromkeys(('player', 'pick', 'faab'), True)
    adds, drops = raw.get('adds'), raw.get('drops')
    if adds is not None and not isinstance(adds, dict):
        categories['player'] = False
        adds = {}
    if drops is not None and not isinstance(drops, dict):
        categories['player'] = False
        drops = {}
    adds, drops = adds or {}, drops or {}
    candidates = []
    for pid in sorted(set(adds) | set(drops), key=str):
        identity = str(pid) if pid is not None and not isinstance(pid, bool) else ''
        candidates.append(('player', identity, _rid(drops.get(pid)), _rid(adds.get(pid)), None))
    picks, budgets = raw.get('draft_picks'), raw.get('waiver_budget')
    if picks is not None and not isinstance(picks, list):
        categories['pick'] = False
        picks = []
    if budgets is not None and not isinstance(budgets, list):
        categories['faab'] = False
        budgets = []
    picks, budgets = picks or [], budgets or []
    for pick in picks:
        if not isinstance(pick, dict):
            categories['pick'] = False
            continue
        identity = future_pick_id(pick, 0)
        candidates.append(('pick', identity, _rid(pick.get('previous_owner_id')), _rid(pick.get('owner_id')), None))
    for budget in budgets:
        if not isinstance(budget, dict):
            categories['faab'] = False
            continue
        amount = budget.get('amount')
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not 0 <= amount < float('inf'):
            categories['faab'] = False
            continue
        sender, receiver = _rid(budget.get('sender')), _rid(budget.get('receiver'))
        candidates.append(('faab', f'FAAB:{sender}:{receiver}:{amount}', sender, receiver, amount))
    by_id, conflicts = {}, set()
    for item in candidates:
        kind, identity, sender, receiver, amount = item
        if not identity or sender not in participants or receiver not in participants or sender == receiver:
            categories[kind] = False
            continue
        key = (kind, identity)
        if key in by_id and by_id[key] != item:
            conflicts.add(key)
            categories[kind] = False
        by_id[key] = item
    movements = tuple(v for k, v in by_id.items() if k not in conflicts)
    if not movements:
        # Missing/empty consideration is not evidence of a no-asset trade.
        categories = dict.fromkeys(categories, False)
    return participants, movements, bool(movements) and all(categories.values()), categories


def _movements(raw):
    """Compatibility view over the single directed-consideration admission path."""
    return _movement_evidence(raw)[:3]


def _counts():
    return {'trades': 0, 'incoming': Counter(), 'outgoing': Counter(),
            'incomplete_composition': 0,
            'composition_supported_trades': 0, 'composition_partial_trades': 0,
            'composition_unavailable_trades': 0, 'category_supported_trades': Counter(),
            'acquired_positions': Counter(), 'moved_positions': Counter(),
            'acquired_kinds': Counter(), 'moved_kinds': Counter(),
            'package_style': Counter(), 'counterparties': Counter(), 'references': []}


def _add_side(counts, rid, participants, movements, positions, reference, complete, categories):
    counts['trades'] += 1
    counts['incomplete_composition'] += int(not complete)
    state = 'supported' if complete else 'partial' if movements else 'unavailable'
    counts[f'composition_{state}_trades'] += 1
    counts['category_supported_trades'].update(kind for kind, supported in categories.items() if supported)
    counts['counterparties'].update(other for other in participants if other != rid)
    received, sent = [], []
    acquired, moved = set(), set()
    for kind, identity, sender, receiver, _amount in movements:
        if receiver == rid:
            counts['incoming'][kind] += 1
            if kind != 'faab':
                received.append(kind)
            if kind == 'player' and positions.get(identity):
                acquired.add(positions[identity])
        if sender == rid:
            counts['outgoing'][kind] += 1
            if kind != 'faab':
                sent.append(kind)
            if kind == 'player' and positions.get(identity):
                moved.add(positions[identity])
    counts['acquired_positions'].update(acquired)
    counts['moved_positions'].update(moved)
    counts['acquired_kinds'].update(set(received))
    counts['moved_kinds'].update(set(sent))
    if complete and sent and received:
        style = 'consolidation' if len(sent) > len(received) else 'depth expansion' if len(received) > len(sent) else 'balanced asset count'
        counts['package_style'][style] += 1
    if len(counts['references']) < 12:
        counts['references'].append(reference)


def _plain(counts):
    return {key: dict(sorted(value.items())) if isinstance(value, Counter) else value for key, value in counts.items()}


class LeagueGMObservations:
    """Bounded shared extension of GM Behavioral Intelligence, never persisted."""
    def __init__(self, season_cache=None):
        self.season_cache = season_cache
        self._lock, self._build_lock = RLock(), Lock()
        self._entries = OrderedDict()
        self.builds = self.hits = 0
        self.last_duration_ms = 0.0

    def _cache(self):
        if self.season_cache is not None:
            return self.season_cache
        from src.core.history_context.store import sleeper_season_cache
        return sleeper_season_cache

    def source_identity(self, data):
        league = str((data.get('league') or {}).get('league_id') or '')
        cache = self._cache()
        files = []
        for season in cache.available_seasons(league)[-MAX_SEASONS:]:
            try:
                stat = cache.path(league, season).stat()
            except FileNotFoundError:
                continue  # Atomic archive turnover; the post-build check rejects revision mixtures.
            checksum = cache.prepared_checksum(league, season)
            files.append((season, checksum) if checksum is not None else
                         (season, 'unverified', stat.st_ino, stat.st_size, stat.st_mtime_ns))
        return _digest((METHOD, str(cache.root.resolve()), league, files,
                        (data.get('league') or {}).get('season'),
                        [(t.get('roster_id'), t.get('owner_id'), canonical_team_name(t)) for t in data.get('teams') or []],
                        [_transaction(r) for r in islice(_current_rows(data), MAX_ROWS + 1)],
                        periods({'league': data.get('league') or {}, 'transactions': data.get('season_transactions')}, 'transactions'),
                        [(str(pid), row.get('position')) for pid, row in sorted((data.get('players') or {}).items()) if isinstance(row, dict)]))

    def report(self, data, *, prepared_only=False):
        key = self.source_identity(data)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                self.hits += 1
                return deepcopy(cached)
        if prepared_only:
            return None
        with self._build_lock:
            with self._lock:
                if key in self._entries:
                    return deepcopy(self._entries[key])
            started = perf_counter()
            result = self._build(data)
            if self.source_identity(data) != key:
                # Never publish mixed history/identity revisions as one report.
                return {'league_id': str((data.get('league') or {}).get('league_id') or ''),
                        'semantic_identity': key, 'teams': {}, 'trade_count': None,
                        'coverage': {'state': 'unavailable', 'explanation': 'Source changed during analysis; retry the league report.'},
                        'limitations': ['Source publication changed; no coherent report was admitted.']}
            with self._lock:
                self._entries[key] = result
                while len(self._entries) > MAX_ENTRIES or sum(len(json.dumps(x, default=str)) for x in self._entries.values()) > MAX_BYTES:
                    self._entries.popitem(last=False)
                self.builds += 1
                self.last_duration_ms = round((perf_counter() - started) * 1000, 3)
            return deepcopy(result)

    def _build(self, data):
        league = str((data.get('league') or {}).get('league_id') or '')
        current_season = (data.get('league') or {}).get('season') or data.get('season')
        now = datetime.now(timezone.utc)
        cache = self._cache()
        coverage, identities, raw_rows, limitations = [], {}, [], []
        raw_rows.extend((str(current_season) if current_season is not None else None, league, _transaction(row))
                        for row in islice(_current_rows(data), MAX_ROWS + 1))
        seasons = cache.available_seasons(league)
        if len(seasons) > MAX_SEASONS:
            limitations.append('Only the latest 20 retained seasons are represented.')
        for season in reversed(seasons[-MAX_SEASONS:]):
            if len(raw_rows) > MAX_ROWS:
                break  # Prefer current/recent evidence within the explicit source bound.
            try:
                facts = cache.sections(league, season, ('league', 'rosters', 'transactions'))
            except (OSError, ValueError, TypeError):
                limitations.append(f'{season}: retained source unavailable; not an observed zero.')
                coverage.append({'season': season, 'source_league_id': None,
                    'source_state': 'unavailable',
                    **periods({'league': {'season': str(season), 'status': 'complete'}, 'transactions': None}, 'transactions')})
                continue
            if not facts:
                continue
            source_league = str((facts.get('league') or {}).get('league_id') or '')
            periods_row = periods(facts, 'transactions')
            coverage.append({'season': season, 'source_league_id': source_league, **periods_row})
            owners = {}
            for roster in facts.get('rosters') or []:
                if isinstance(roster, dict) and _rid(roster.get('roster_id')):
                    rid = _rid(roster['roster_id'])
                    owners.setdefault(rid, set()).add(str(roster.get('owner_id') or ''))
            for rid, values in owners.items():
                identities[(str(season), rid)] = next(iter(values)) if len(values) == 1 and '' not in values else None
            for bucket in (facts.get('transactions') or {}).values() if isinstance(facts.get('transactions'), dict) else []:
                if isinstance(bucket, list):
                    raw_rows.extend((str(season), source_league, _transaction(row)) for row in islice(bucket, max(0, MAX_ROWS + 1 - len(raw_rows))))
            del facts
        current_buckets = data.get('season_transactions')
        if current_season is not None:
            current_coverage = periods({'league': data.get('league') or {}, 'transactions': current_buckets}, 'transactions')
            if not any(str(x['season']) == str(current_season) and x.get('source_state') != 'unavailable' for x in coverage):
                coverage.append({'season': current_season, 'source_league_id': league, **current_coverage})
        if len(raw_rows) > MAX_ROWS:
            limitations.append('Transaction observation limit reached; counts describe a bounded subset.')
        unique, conflicts = {}, set()
        for season, source_league, raw in raw_rows[:MAX_ROWS]:
            if raw.get('type') != 'trade' or not source_league or str(raw.get('league_id') or source_league) != source_league:
                continue
            tid = str(raw.get('transaction_id') or '')
            if not tid or len(tid) > 100:
                continue
            key = (source_league, tid)
            raw.pop('league_id', None)  # Already validated; absent versus explicit scope is not a conflicting copy.
            row = (season, source_league, raw)
            if key in unique and unique[key] != row:
                conflicts.add(key)
            unique[key] = row
        if conflicts:
            limitations.append(f'{len(conflicts)} conflicting transaction identities withheld.')
        team_map = {str(t.get('roster_id')): t for t in data.get('teams') or []}
        teams = {rid: {'roster_id': rid, 'name': canonical_team_name(team),
                       'current_owner_id': str(team.get('owner_id') or ''),
                       'franchise': _counts(), 'manager': _counts()}
                 for rid, team in team_map.items()}
        positions = {str(pid): str(row.get('position') or '') for pid, row in (data.get('players') or {}).items() if isinstance(row, dict)}
        events, season_counts, edges, timed = [], Counter(), Counter(), []
        composition, unknown_clocks, pick_deals, faab_deals, faab_legs, asset_total = 0, 0, 0, 0, 0, 0
        composition_partial = composition_unavailable = 0
        category_supported = Counter()
        for key, (season, source_league, raw) in sorted(unique.items()):
            if key in conflicts or str(raw.get('status') or '').casefold() not in {'complete', 'completed'}:
                continue
            participants, movements, complete, categories = _movement_evidence(raw)
            if not participants:
                limitations.append('A completed row has unsupported participants; it is withheld.')
                continue
            reference = {'transaction_id': key[1], 'source_league_id': source_league, 'season': season,
                         'url': f'/trades/history/TRADE-{source_league}-{key[1]}'}
            clock = _clock(raw, now)
            if clock:
                timed.append(clock)
            else:
                unknown_clocks += 1
            events.append((key, season, participants, movements, complete, clock, categories))
            season_counts[str(season) if season is not None else 'unknown'] += 1
            edges.update(combinations(participants, 2))
            composition += int(complete)
            composition_partial += int(bool(movements) and not complete)
            composition_unavailable += int(not movements)
            category_supported.update(kind for kind, supported in categories.items() if supported)
            asset_total += sum(kind != 'faab' for kind, *_ in movements)
            pick_deals += int(any(kind == 'pick' for kind, *_ in movements))
            faab_deals += int(any(kind == 'faab' for kind, *_ in movements))
            faab_legs += sum(kind == 'faab' for kind, *_ in movements)
            for rid in participants:
                if rid not in teams:
                    continue
                row = teams[rid]
                _add_side(row['franchise'], rid, participants, movements, positions, reference, complete, categories)
                # Current-season ownership snapshots do not prove past tenure.
                owner = identities.get((str(season), rid)) if str(season) != str(current_season) else None
                if belongs_to_manager({'owner_id': owner}, row['current_owner_id'], {}):
                    _add_side(row['manager'], rid, participants, movements, positions, reference, complete, categories)
        acquired = sum(len(r['acquired']) for r in coverage)
        complete_coverage = bool(coverage) and all(r['complete_acquisition'] for r in coverage) and not limitations
        state = ('observed' if events else 'observed_zero') if complete_coverage else 'partial' if events or acquired else 'unavailable'
        note = ('All expected transaction buckets in the listed observed seasons are acquired.' if complete_coverage
                else 'History is partial or unavailable; low counts do not prove low trading activity.')
        unavailable_seasons = sum(row.get('source_state') == 'unavailable' for row in coverage)
        if unavailable_seasons:
            suffix = '' if unavailable_seasons == 1 else 's'
            note += f' {unavailable_seasons} retained season source{suffix} unavailable; independently valid evidence remains included.'
        for rid, row in teams.items():
            row['franchise'], row['manager'] = _plain(row['franchise']), _plain(row['manager'])
            row['attribution'] = 'Manager counts cover this franchise only and use unique historical season-owner evidence, not current ownership. Exact intra-season takeover timing is unestablished; behavior at another franchise is not inferred.'
            row['unattributed_to_current_manager'] = row['franchise']['trades'] - row['manager']['trades']
            row['summary'] = describe_team(row)
        if unknown_clocks:
            limitations.append(f'{unknown_clocks} completed trades lack supported completion clocks; excluded from dated activity conclusions.')
        if composition < len(events):
            limitations.append(f'{len(events) - composition} trades have incomplete directed consideration; asset counts are supported subsets, not complete packages.')
        limitations.extend(['Positions describe acquired/moved players using current catalog identity, not historical slot eligibility.',
                            'Historical youth/veteran preferences are unavailable without transaction-time age evidence.',
                            'Counts describe decisions, not motives, acceptance, skill or historical trade fairness.',
                            'FOIS grades remain RETAINED / NOT REVALIDATED; observations do not regrade trades.'])
        from .activity import summarize_activity
        activity = summarize_activity(raw_rows[:MAX_ROWS], team_map.values(),
            lambda season, rid: identities.get((str(season), rid)) if str(season) != str(current_season) else None)
        core = {'league_id': league, 'method': METHOD, 'trade_count': len(events),
                'activity': activity,
                'coverage': {'state': state, 'explanation': note, 'seasons': coverage}, 'teams': teams,
                'season_counts': dict(sorted(season_counts.items())), 'completed_with_supported_clock': len(timed),
                'first_supported_completion': min(timed) if timed else None, 'latest_supported_completion': max(timed) if timed else None,
                'composition_supported_trades': composition, 'pick_trades': pick_deals, 'faab_trades': faab_deals,
                'composition_partial_trades': composition_partial,
                'composition_unavailable_trades': composition_unavailable,
                'category_supported_trades': dict(category_supported),
                'directed_faab_transfers': faab_legs, 'unique_transferred_player_pick_assets': asset_total,
                'counterparty_pairs': [{'rosters': list(k), 'trades': n} for k, n in sorted(edges.items())],
                'limitations': list(dict.fromkeys(limitations))}
        core['semantic_identity'] = _digest((core, events))
        return core


def supported_asset_count(facts, direction, kind):
    """Known transfers are lower bounds; absent coverage cannot establish zero."""
    count = facts[direction].get(kind, 0)
    covered = facts.get('category_supported_trades', {}).get(kind, 0)
    return count if count or covered == facts['trades'] else None


def describe_team(row):
    facts = row['franchise']
    count = facts['trades']
    picks_in = supported_asset_count(facts, 'incoming', 'pick')
    picks_out = supported_asset_count(facts, 'outgoing', 'pick')
    if not count:
        return 'No completed franchise trades observed; available history does not establish a manager preference.'
    if facts.get('composition_unavailable_trades') == count:
        assets = 'Consideration unavailable; player, exact-pick and FAAB totals are not established. '
        partial = ''
    else:
        assets = (f"Supported exact picks acquired: {picks_in if picks_in is not None else 'Unavailable'}; "
                  f"moved: {picks_out if picks_out is not None else 'Unavailable'}. ")
        partial = (f"Original consideration is incomplete in {facts['incomplete_composition']} deals; asset counts are supported subsets. "
                   if facts['incomplete_composition'] else '')
    return (f"This franchise completed {count} observed trade{'s' if count != 1 else ''}. " + assets
            + partial
            + (f"{row['manager']['trades']} deals have season-observed attribution to the current manager; exact takeover timing is unknown."
               if row['manager']['trades'] else 'Available history does not attribute these decisions to the current manager.'))


def partner_context(report, roster_id, diagnostic=None, received_positions=()):
    row = (report or {}).get('teams', {}).get(str(roster_id))
    if not row:
        return {'summary': 'History does not establish a partner preference; current offer quality remains separate.',
                'soft_tie_break': 0, 'references': [], 'coverage': 'unavailable'}
    facts = row['franchise']
    manager = row['manager']
    diagnostic = diagnostic or {}
    supported = (diagnostic.get('coverage') == 'supported current week'
        and diagnostic.get('numeric_impact_state') == 'supported'
        and diagnostic.get('pre_optimal_points') is not None
        and diagnostic.get('post_optimal_points') is not None
        and diagnostic['post_optimal_points'] >= diagnostic['pre_optimal_points'])
    needs = set((diagnostic or {}).get('need_positions_received') or []) if supported else set()
    matches = sorted(pos for pos in set(received_positions) & needs if manager['acquired_positions'].get(pos, 0) >= MINIMUM_TENDENCY)
    if matches:
        text = 'The current package addresses supported ' + ', '.join(matches) + ' needs. '
        text += 'Season-observed ownership attributes acquisitions of players currently classified at those positions to the current manager in ' + ', '.join(str(manager['acquired_positions'][pos]) for pos in matches) + ' deals at this franchise; exact intra-season tenure remains unestablished. '
    elif needs:
        text = 'The current package addresses supported ' + ', '.join(sorted(needs)) + ' needs, but history does not establish a matching current-manager preference. '
    else:
        text = row['summary'] + ' Current package incentives remain separate from past behavior. '
    if needs and facts['incomplete_composition']:
        if facts.get('composition_unavailable_trades'):
            text += f"Consideration unavailable in {facts['composition_unavailable_trades']} observed franchise trades. "
        if facts.get('composition_partial_trades'):
            text += f"Original consideration is partial in {facts['composition_partial_trades']} observed franchise trades; asset counts are supported subsets. "
    text += (report or {}).get('coverage', {}).get('explanation', '')
    short = (f"Supported {', '.join(matches)} need matches season-attributed current-manager acquisitions. " if matches else
             f"{facts['trades']} completed franchise trades observed; no supported history/need match established. ")
    short += 'Manager preference unestablished. ' if row['manager']['trades'] < MINIMUM_TENDENCY else 'Manager attribution is season-level only. '
    if facts['incomplete_composition']:
        short += 'Consideration unavailable. ' if facts.get('composition_unavailable_trades') == facts['trades'] else 'Consideration incomplete. '
    short += 'History ' + (report or {}).get('coverage', {}).get('state', 'unavailable').replace('_', ' ') + '.'
    return {'summary': text, 'short_summary': short, 'soft_tie_break': int(bool(matches)), 'references': facts['references'],
            'coverage': (report or {}).get('coverage', {}).get('state', 'unavailable'),
            'coverage_explanation': (report or {}).get('coverage', {}).get('explanation', ''),
            'franchise_sample': facts['trades'], 'manager_sample': row['manager']['trades'],
            'consideration_coverage': {key: facts[key] for key in (
                'composition_supported_trades', 'composition_partial_trades',
                'composition_unavailable_trades', 'category_supported_trades')},
            'attribution': row['attribution'], 'source_identity': report['semantic_identity']}


league_gm_observations = LeagueGMObservations()
