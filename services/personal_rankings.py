"""Bounded manager intent over a prepared canonical Market universe.

No provider, solver, history, discovery or cache factories are called here.
The slot curve is an explicitly personal current-value permutation, not a quote.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import re
from threading import RLock

from services.trade_workspace_context import workspace_context
from src.platform.account_context import current_account

METHOD = 'personal-current-market-slot-curve-v1'
MAX_ASSETS = 10_000
POSITIONS = {'QB', 'RB', 'WR', 'TE'}
# Fixed-size synchronization only, never a per-user cache. Short CAS writes and
# header publication share a stripe; no reconstruction or serialization holds it.
_PUBLICATION_LOCKS = tuple(RLock() for _ in range(32))


class PersonalRankingError(ValueError):
    def __init__(self, code, message, status=422):
        super().__init__(message)
        self.code, self.status = code, status


@contextmanager
def personal_publication(context, *, blocking=False):
    key = _digest(context.get('scope') or [])
    lock = _PUBLICATION_LOCKS[int(key[:8], 16) % len(_PUBLICATION_LOCKS)]
    if not lock.acquire(blocking=blocking):
        raise PersonalRankingError('personal_publication_busy', 'Personal preferences are being saved. Retry this operation.', 409)
    try:
        yield
    finally:
        lock.release()


def to_trade_id(asset_id):
    if not isinstance(asset_id, str):
        raise PersonalRankingError('asset_identity_invalid', 'Use a canonical player or exact pick.')
    if re.fullmatch(r'player:[A-Za-z0-9_-]{1,80}', asset_id):
        return asset_id.removeprefix('player:')
    match = re.fullmatch(r'pick:(20\d{2}):([1-9]\d?):([1-9]\d*)', asset_id)
    if match:
        year, round_number, original = match.groups()
        return f'{year}-R{round_number}-{original}'
    raise PersonalRankingError('asset_identity_invalid', 'Player or original-franchise pick identity is unavailable.')


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _number(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and isfinite(value) and 0 <= value <= 1000)


def _league(data):
    return str((data.get('league') or {}).get('league_id') or data.get('league_id') or '')


def _publication_token(data, reader):
    """Cheap immutable-handle fence; no directory reads or analytical work."""
    return [id(data), id(reader), getattr(reader, 'generation', None), getattr(reader, 'semantic_generation', None),
            getattr(reader, 'generated_at', None),
            data.get('asset_market_semantic_revision'),
            (data.get('valuation_intelligence') or {}).get('semantic_generation'),
            (data.get('market_data') or {}).get('generation'),
            id((data.get('market_data') or {}).get('providers')),
            id((data.get('market_data') or {}).get('pick_quotes'))]


def _scope(data, account):
    membership = account.membership if account else None
    if not membership or membership.league_id != _league(data) or not membership.roster_id:
        raise PersonalRankingError('unauthorized_scope', 'Select your connected league and franchise.', 403)
    return membership


def _live_scope(store, account, membership):
    """Recheck revocation and ownership after asynchronous work, without writes."""
    with closing(store.connect()) as connection:
        live = connection.execute(
            "SELECT 1 FROM accounts a JOIN account_sessions s ON s.account_id=a.account_id "
            "JOIN account_league_memberships m ON m.account_id=a.account_id "
            "WHERE a.account_id=? AND a.status='active' AND s.session_id=? "
            "AND s.revoked_at IS NULL AND s.expires_at>? "
            "AND m.league_id=? AND m.roster_id=? AND m.status='active'",
            (account.account_id, account.session_id, datetime.now(timezone.utc).isoformat(),
             membership.league_id, membership.roster_id),
        ).fetchone()
    if live is None:
        raise PersonalRankingError('personal_scope_revoked', 'Your session or franchise access changed. Sign in and reload.', 403)


def _check_market_inputs(data, market_reader):
    compatible = getattr(market_reader, 'compatible_prepared_inputs', None)
    if callable(compatible):
        valid = compatible(data) is True
    else:
        # Legacy readers must still supply explicit matching source identity;
        # absent timestamps are not a substitute for a canonical input marker.
        prepared = getattr(market_reader, 'data', None)
        old_market = (prepared or {}).get('market_data') or {}
        new_market = data.get('market_data') or {}
        old = old_market.get('generation') or old_market.get('generated_at')
        new = new_market.get('generation') or new_market.get('generated_at')
        valid = bool(old and new and old == new)
    if not valid:
        raise PersonalRankingError('market_source_changed',
            'Custom Rankings need a prepared Market update that matches this league’s current evidence. Your saved rankings are unchanged. Check Market, then retry; Neutral Trade remains available.', 409)


def _asset_label(data, key, row=None):
    """Label an exact identity using only the pinned, already prepared snapshot."""
    if row and row.get('display_name') and row['display_name'] != key:
        return str(row['display_name'])
    if key.startswith('player:'):
        player = (data.get('players') or {}).get(key.removeprefix('player:')) or {}
        name = player.get('full_name') or player.get('name') or ' '.join(
            str(player.get(part) or '') for part in ('first_name', 'last_name')).strip()
        return str(name or f"Player {key.removeprefix('player:')} (identity not confirmed)")
    match = re.fullmatch(r'pick:(20\d{2}):([1-9]\d?):([1-9]\d*)', key)
    if match:
        year, round_number, original = match.groups()
        team = next((team for team in data.get('teams') or ()
                     if str(team.get('roster_id')) == original), {})
        label = team.get('name') or team.get('team_name') or team.get('display_name')
        return f"{year} Round {round_number} · original {label or 'franchise ' + original}"
    return 'Unconfirmed asset identity'


def _rejected_row(data, key, row, code, reason, retryable=False):
    return {'asset_id': key, 'label': _asset_label(data, key, row),
            'position': 'PICK' if key.startswith('pick:') else str(row.get('position') or 'Unavailable'),
            'code': code, 'reason': reason, 'retryable': retryable}


def build_universe(data, market_reader, *, requested_ids=()):
    """Read every eligible compact row from one already-published immutable model.

    Preserve the directory's exact Market ordering, including its ID tie order.
    Never materialize canonical dossiers or historical evidence.
    """
    if market_reader is None:
        raise PersonalRankingError('market_unavailable', 'Custom Rankings are pending: a compatible Market ranking list is not ready. Saved rankings are unchanged. Check Market, then retry; Neutral Trade remains available.', 503)
    identity = market_reader.identity()
    league_id = _league(data)
    if not league_id or str(identity.get('league_id')) != league_id:
        raise PersonalRankingError('market_scope_changed', 'Market evidence belongs to a different league. Retry after preparation.', 409)
    _check_market_inputs(data, market_reader)
    publication = _publication_token(data, market_reader)
    source = identity.get('market_generation')
    if not isinstance(source, str) or not source:
        raise PersonalRankingError('market_unavailable', 'Market source identity is unavailable.', 503)
    pick_owners = {}
    player_owners = {}
    for team in data.get('teams') or ():
        rid = int(team.get('roster_id') or 0)
        for player in team.get('players') or ():
            pid = str(player.get('id') or player.get('player_id') or '')
            if pid:
                key = 'player:' + pid
                player_owners[key] = None if key in player_owners and player_owners[key] != rid else rid
        for pick in team.get('picks_owned') or ():
            year, season = pick.get('year'), pick.get('season')
            if year is not None and season is not None and str(year) != str(season):
                continue
            year = year if year is not None else season
            original = pick.get('original_roster_id')
            owner = pick.get('current_owner_id', rid)
            key = f"pick:{year}:{pick.get('round')}:{original}"
            try:
                to_trade_id(key)
                if int(owner) == rid:
                    if key in pick_owners and pick_owners[key] != rid:
                        pick_owners[key] = None
                    else:
                        pick_owners[key] = rid
            except (PersonalRankingError, TypeError, ValueError):
                continue
    def qualify(row, key):
        kind = row.get('asset_type')
        position = row.get('position')
        if (kind == 'player') != key.startswith('player:') or kind not in {'player', 'pick'}:
            unavailable[key] = _rejected_row(data, key, row, 'identity_conflict',
                'The Market asset type does not match this saved exact identity. No replacement identity or personal value was assumed.')
            return None
        if key in player_owners and player_owners[key] is None:
            unavailable[key] = _rejected_row(data, key, row, 'ownership_conflict',
                'This player appears on conflicting current rosters. Its ownership and personal value cannot be confirmed.', True)
            return None
        if kind == 'player' and position not in POSITIONS:
            unavailable[key] = _rejected_row(data, key, row, 'position_ineligible',
                'This player does not have a supported QB, RB, WR or TE identity in the current Market list.')
            return None
        status = str(row.get('status') or '').lower()
        if status in {'retired', 'inactive'}:
            unavailable[key] = _rejected_row(data, key, row, 'asset_' + status,
                f'The current player record is marked {status}, so this asset is not eligible for the current personal value curve. Your saved opinion has not been deleted.')
            return None
        value = (row.get('values') or {}).get('market_value')
        if not _number(value):
            unavailable[key] = _rejected_row(data, key, row,
                'market_price_missing' if value is None else 'market_price_invalid',
                'A compatible current Market price is missing. Missing pricing is not a zero value.' if value is None else
                'The current Market price is outside the supported price contract. It cannot be used as a personal value.', True)
            return None
        owner = player_owners.get(key) if kind == 'player' else pick_owners.get(key)
        if kind == 'pick' and owner is None:
            unavailable[key] = _rejected_row(data, key, row, 'pick_ownership_unavailable',
                'The exact pick has no single confirmed current owner in this league. Another same-year or same-round pick cannot replace it.', True)
            return None
        return row.get('values', {}).get('market_value')

    rows, seen, unavailable = [], set(), {}
    offset, total = 0, None
    while total is None or offset < total:
        page = market_reader.directory(offset=offset, limit=250, sort='market', direction='desc', minimum=0)
        if page.get('market_generation') != source or str(page.get('league_id')) != league_id:
            raise PersonalRankingError('market_source_changed', 'Market publication changed. Retry the same action.', 409)
        total = page.get('total')
        if isinstance(total, bool) or not isinstance(total, int) or total < 0 or total > MAX_ASSETS:
            raise PersonalRankingError('universe_capacity', 'The full ranking universe exceeds the supported bound; nothing was truncated.', 503)
        chunk = page.get('assets') or []
        if not chunk and offset < total:
            raise PersonalRankingError('market_incomplete', 'The complete Market directory is unavailable.', 503)
        for row in chunk:
            key = row.get('asset_id')
            try:
                trade_id = to_trade_id(key)
            except PersonalRankingError:
                continue
            if key in seen:
                raise PersonalRankingError('identity_conflict', 'Duplicate Market asset identity cannot seed rankings.', 503)
            seen.add(key)
            value = qualify(row, key)
            if value is None:
                continue
            kind = row.get('asset_type')
            owner = player_owners.get(key) if kind == 'player' else pick_owners.get(key)
            rows.append({'asset_id': key, 'trade_asset_id': trade_id,
                         'label': _asset_label(data, key, row),
                         'position': 'PICK' if kind == 'pick' else row.get('position'),
                         'market_value': value, 'owner_roster_id': owner,
                         'market_rank': len(rows) + 1})
        offset += len(chunk)
    # The full ranking pass retains its original priced-directory bound. Read
    # only missing saved IDs for diagnostics, rather than scanning all unpriced
    # players or opening dossiers. The existing indexed filter caps each query
    # to 250 exact IDs and returns the same immutable publication identity.
    requested = tuple(dict.fromkeys(requested_ids))
    if len(requested) > MAX_ASSETS:
        raise PersonalRankingError('universe_capacity', 'Saved rankings exceed the supported identity bound; nothing was truncated.', 503)
    known = {row['asset_id'] for row in rows}
    missing = [key for key in requested if key not in known and key not in unavailable]
    for begin in range(0, len(missing), 250):
        batch = tuple(missing[begin:begin + 250])
        page = market_reader.directory(offset=0, limit=250, sort='market', direction='desc',
                                       minimum=None, availability_asset_ids=batch)
        if page.get('market_generation') != source or str(page.get('league_id')) != league_id:
            raise PersonalRankingError('market_source_changed', 'Market publication changed while reviewing saved assets. Retry rankings.', 409)
        total = page.get('total')
        chunk = page.get('assets') or []
        if type(total) is not int or not 0 <= total <= len(batch) or len(chunk) != total:
            raise PersonalRankingError('market_incomplete', 'The exact saved-asset review is incomplete. Retry rankings; no saved preferences were changed.', 503)
        returned = set()
        for row in chunk:
            key = row.get('asset_id')
            if key not in batch or key in returned:
                raise PersonalRankingError('identity_conflict', 'Saved-asset review returned a conflicting exact identity.', 503)
            returned.add(key)
            if qualify(row, key) is not None:
                raise PersonalRankingError('market_source_changed', 'The priced Market list changed during saved-asset review. Retry rankings.', 409)
    for key in missing:
        if key in unavailable:
            continue
        player = ((data.get('players') or {}).get(key.removeprefix('player:')) or {}) if key.startswith('player:') else {}
        status = str(player.get('status') or '').lower()
        if status in {'retired', 'inactive'}:
            unavailable[key] = _rejected_row(data, key, player, 'asset_' + status,
                f'The current player record is marked {status}, and the exact asset is absent from the current eligible Market list. Your saved opinion has not been deleted.')
        else:
            unavailable[key] = _rejected_row(data, key, player, 'asset_not_in_market',
                'This saved exact asset is absent from the current Market list. Its current identity and price cannot be confirmed; no replacement asset or zero price was assumed.', True)
    _check_market_inputs(data, market_reader)
    if _publication_token(data, market_reader) != publication:
        raise PersonalRankingError('market_source_changed', 'Market changed while rankings loaded. Your saved rankings are unchanged. Retry rankings.', 409)
    if not rows:
        raise PersonalRankingError('market_unavailable', 'Custom Rankings need supported prices and exact asset identities. No eligible priced assets are ready in this Market list. Check Market, then retry rankings; your saved preferences are unchanged.', 503)
    # Pricing eligibility and exact ownership are separate facts. A missing
    # price does not make an owned player's saved Protect preference inactive.
    for key, rejected in unavailable.items():
        owners = player_owners if key.startswith('player:') else pick_owners
        rejected['owner_roster_id'] = owners.get(key)
    generation = _digest([league_id, source, getattr(market_reader, 'semantic_generation', None),
                          (data.get('market_data') or {}).get('generation'),
                          [(r['asset_id'], r['market_value'], r['owner_roster_id']) for r in rows]])
    return {'generation': generation, 'source_generation': source,
            'source_semantic_generation': str(getattr(market_reader, 'semantic_generation', None) or source),
            'league_id': league_id, 'rows': rows, 'unavailable_rows': unavailable}


def personal_values(document, universe):
    """Permute the existing price curve; tiers never manufacture cardinal prices.

    No interpolation/extrapolation, inflation, clipping or personal price copies.
    Every saved rank must have compatible current evidence, otherwise numerical
    Custom assessment is withheld. New assets require an explicit Restart.
    """
    rows = {r['asset_id']: r for r in universe['rows']}
    order = document.get('order') or []
    baseline = (document.get('baseline') or {}).get('ids') or []
    if not order or len(set(order)) != len(order) or set(order) != set(baseline):
        return {'available': False, 'values': {}, 'reason': 'Saved ranking order is incomplete or invalid.'}
    order_set = set(order)
    missing = [(index, key) for index, key in enumerate(order, 1) if key not in rows]
    if missing:
        rejected = universe.get('unavailable_rows') or {}
        issues = []
        for saved_rank, key in missing:
            issue = dict(rejected.get(key) or {'asset_id': key, 'label': key,
                'position': 'PICK' if key.startswith('pick:') else 'Unavailable',
                'code': 'asset_not_in_market', 'retryable': True,
                'reason': 'This saved exact asset is absent from the current Market list. Its current identity and price cannot be confirmed; no replacement asset or zero price was assumed.'})
            issue.update(saved_rank=saved_rank, can_remove=len(order) > 1)
            issues.append(issue)
        first = issues[0]
        count = len(issues)
        reason = (f"Custom values need attention for {first['label']}"
                  + (f' and {count - 1} other saved asset(s)' if count > 1 else '')
                  + f". {first['reason']} Review affected assets or retry; your saved order, tiers and preferences are unchanged. Neutral DTOS remains available.")
        return {'available': False, 'values': {}, 'reason': reason,
                'unavailable_ids': [key for _rank, key in missing], 'compatibility_issues': issues,
                'new_asset_ids': [key for key in rows if key not in order_set]}
    # Only the saved cohort supplies the curve: a new unranked asset cannot
    # silently push every existing opinion into a different slot.
    order_set = set(order)
    curve = sorted((rows[key]['market_value'] for key in order), reverse=True)
    return {'available': True, 'values': dict(zip(order, curve)), 'reason': None,
            'new_asset_ids': [key for key in rows if key not in order_set], 'method': METHOD}


def view_state(store, data, market_reader, account):
    from src.core.accounts.personal_store import load_personal
    membership = _scope(data, account)
    _live_scope(store, account, membership)
    document = load_personal(store, account.account_id, membership.league_id, membership.roster_id)
    universe = build_universe(data, market_reader, requested_ids=(document or {}).get('order') or ())
    values = personal_values(document, universe) if document else {'available': False, 'values': {}, 'reason': 'Create Custom Rankings to personalize. Your starting list is already ordered by Market; Neutral DTOS remains available.'}
    current = {row['asset_id']: row for row in universe['rows']}
    order = document['order'] if document else list(current)
    # Retain unresolved saved rows visibly, never substitute another identity.
    order_set = set(order)
    keys = [*order, *(key for key in current if key not in order_set)]
    preferences = (document or {}).get('preferences') or {}
    rows = []
    for index, key in enumerate(keys, 1):
        rejected = (universe.get('unavailable_rows') or {}).get(key) or {}
        row = dict(current.get(key) or {'asset_id': key, 'label': rejected.get('label') or _asset_label(data, key),
            'position': rejected.get('position') or ('PICK' if key.startswith('pick:') else 'Unavailable'),
            'market_value': None, 'owner_roster_id': rejected.get('owner_roster_id'), 'market_rank': None})
        row.update(rank=index, personal_rank=index if key in order_set and document else None,
                   personal_value=values['values'].get(key), owned=row['owner_roster_id'] == membership.roster_id,
                   preferences=preferences.get(key, {}), tier_start=key in ((document or {}).get('tiers') or []),
                   custom_ranked=key in order_set and bool(document), identity_available=key in current)
        rows.append(row)
    context = workspace_context(data, membership.roster_id)
    return {'initialized': document is not None, 'revision': (document or {}).get('revision', 0),
            'mode': (document or {}).get('mode', 'neutral'), 'generation': universe['generation'],
            'baseline_generation': ((document or {}).get('baseline') or {}).get('generation'),
            'baseline_source_generation': ((document or {}).get('baseline') or {}).get('source_generation'),
            'rows': rows, 'context': {k: context[k] for k in ('league_id', 'roster_id', 'binding')},
            'personal_available': values['available'], 'method': METHOD,
            'limitations': [values['reason']] if values.get('reason') else [],
            'new_asset_ids': values.get('new_asset_ids', []),
            'compatibility_issues': values.get('compatibility_issues', []),
            'eligible_asset_count': len(current), 'saved_asset_count': len(document['order']) if document else 0,
            'recovery_url': '/account/my-dtos#personal-compatibility',
            'method_explanation': 'Your saved global order receives the descending current Market price slots of that same saved cohort. Moving up cannot lower a personal value. Tiers are labels and do not change prices. New assets need Restart Rankings; no past prices are reconstructed. Removing one asset from your Custom order is an explicit membership edit: other ranks and tier breaks stay in order, but remaining personal values may change because that asset’s current price slot leaves the curve. The saved baseline generation identifies the original seed publication, not a new Market quote.'}


def apply_command(store, data, market_reader, account, payload, *, verify_source=None):
    from src.core.accounts.personal_store import load_personal, save_personal
    membership = _scope(data, account)
    _live_scope(store, account, membership)
    universe = build_universe(data, market_reader)
    context = workspace_context(data, membership.roster_id)
    expected_context = {k: context[k] for k in ('league_id', 'roster_id', 'binding')}
    if payload.get('context') != expected_context or payload.get('market_generation') != universe['generation']:
        raise PersonalRankingError('personal_context_changed', 'League, session or Market evidence changed. Reload before saving.', 409)
    revision = payload.get('expected_revision')
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise PersonalRankingError('invalid_revision', 'A valid preference revision is required.')
    document = load_personal(store, account.account_id, membership.league_id, membership.roster_id)
    if revision != (document or {}).get('revision', 0):
        raise PersonalRankingError('personal_revision_changed', 'Your rankings changed in another tab. Reload before editing.', 409)
    command = payload.get('command')
    ids = [r['asset_id'] for r in universe['rows']]
    if command in {'initialize', 'restart'}:
        if command == 'initialize' and document:
            raise PersonalRankingError('already_initialized', 'Use Restart Rankings to replace a saved custom order.', 409)
        if command == 'restart' and payload.get('confirmation') != 'RESTART RANKINGS':
            raise PersonalRankingError('confirmation_required', 'Confirm that customized order and tiers will be lost.')
        if not ids:
            raise PersonalRankingError('market_unavailable', 'No eligible priced assets are available to seed rankings.', 503)
        document = {'schema': 1, 'baseline': {'generation': universe['generation'], 'ids': ids,
                    'source_generation': universe['source_generation'],
                    'source_semantic_generation': universe['source_semantic_generation']},
                    'order': ids, 'tiers': [], 'preferences': {} if payload.get('reset_preferences') is True else (document or {}).get('preferences', {}),
                    'mode': 'custom'}
    elif not document:
        raise PersonalRankingError('rankings_not_started', 'Initialize the full Market-seeded rankings first.', 409)
    else:
        document = {k: deepcopy(v) for k, v in document.items() if k not in {'revision', 'created_at', 'updated_at'}}
        key = payload.get('asset_id')
        if command in {'reorder', 'tiers', 'preferences'} and key not in document['order']:
            raise PersonalRankingError('asset_not_ranked', 'This asset is not in your saved baseline. Restart to include new assets.')
        if command == 'remove_asset':
            if payload.get('confirmation') != 'REMOVE FROM CUSTOM ORDER':
                raise PersonalRankingError('confirmation_required', 'Confirm removal of this exact asset from your Custom order. Its own tier break is removed; other ranks, tiers and Target/Avoid/Protect preferences are preserved. Remaining personal values may change.')
            if key not in document['order']:
                raise PersonalRankingError('asset_not_ranked', 'This exact asset is not in your saved Custom order.', 409)
            if len(document['order']) <= 1:
                raise PersonalRankingError('last_ranked_asset', 'Keep at least one ranked asset. Use Neutral DTOS or explicitly Restart Rankings instead.')
            document['order'].remove(key)
            document['baseline']['ids'].remove(key)
            document['tiers'] = [asset for asset in document['tiers'] if asset != key]
        elif command == 'reorder':
            position = payload.get('to_position')
            if isinstance(position, bool) or not isinstance(position, int) or not 1 <= position <= len(document['order']):
                raise PersonalRankingError('invalid_position', 'Choose a valid position in the complete overall order.')
            document['order'].remove(key)
            document['order'].insert(position - 1, key)
        elif command == 'tiers':
            if type(payload.get('tier_start')) is not bool:
                raise PersonalRankingError('invalid_tier', 'Choose whether a tier begins at this asset.')
            tiers = set(document['tiers'])
            tiers.add(key) if payload['tier_start'] else tiers.discard(key)
            document['tiers'] = [i for i in document['order'] if i in tiers]
        elif command == 'preferences':
            flags = payload.get('preferences')
            if not isinstance(flags, dict) or set(flags) - {'target', 'avoid', 'protect'} or any(type(v) is not bool for v in flags.values()):
                raise PersonalRankingError('invalid_preference', 'Use Target, Avoid and Protect controls.')
            if flags.get('target') and flags.get('avoid'):
                raise PersonalRankingError('conflicting_preferences', 'An acquisition cannot be both a Target and Avoid.')
            row = next((r for r in universe['rows'] if r['asset_id'] == key), None)
            if flags.get('protect') and (row is None or row['owner_roster_id'] != membership.roster_id):
                raise PersonalRankingError('not_owned', 'Only an exact currently owned asset can be protected.')
            if any(flags.values()):
                document['preferences'][key] = flags
            else:
                document['preferences'].pop(key, None)
        elif command == 'mode' and payload.get('mode') in {'neutral', 'custom'}:
            document['mode'] = payload['mode']
        else:
            raise PersonalRankingError('invalid_command', 'Choose a supported rankings action.')
    with personal_publication({'scope': [account.account_id, membership.league_id, membership.roster_id]}, blocking=True):
        _check_market_inputs(data, market_reader)
        if verify_source is not None:
            verify_source()
        save_personal(store, account.account_id, membership.league_id, membership.roster_id, document,
                      expected_revision=revision, expected_session_id=account.session_id)
    return view_state(store, data, market_reader, account)


def resolve_personal_context(data, payload, *, store=None, market_reader=None, account=None, require_revision=True):
    from src.core.accounts.personal_store import load_personal
    account = account or current_account()
    mode = payload.get('valuation_mode', 'neutral')
    if mode not in {'neutral', 'custom'}:
        raise PersonalRankingError('invalid_mode', 'Choose Neutral DTOS or Custom DTOS.')
    if store is None or account is None:
        if mode == 'custom':
            raise PersonalRankingError('personal_unavailable', 'Sign in and prepare Custom Rankings before using Custom DTOS.', 403)
        return {'mode': 'neutral'}
    membership = _scope(data, account)
    _live_scope(store, account, membership)
    doc = load_personal(store, account.account_id, membership.league_id, membership.roster_id)
    revision = (doc or {}).get('revision', 0)
    if require_revision and (type(payload.get('personal_revision')) is not int or payload.get('personal_revision') != revision):
        raise PersonalRankingError('personal_revision_changed', 'Personal preferences changed. Reload this workspace.', 409)
    preferences = {to_trade_id(key): flags for key, flags in ((doc or {}).get('preferences') or {}).items()}
    context = {'mode': mode, 'revision': revision, 'preferences': preferences,
               'scope': [account.account_id, membership.league_id, membership.roster_id],
               'baseline_generation': ((doc or {}).get('baseline') or {}).get('generation'), 'method': METHOD}
    if mode == 'neutral':
        return context
    if not doc:
        raise PersonalRankingError('rankings_not_started', 'Initialize your complete Custom Rankings first.', 409)
    universe = build_universe(data, market_reader, requested_ids=doc['order'])
    if require_revision and payload.get('personal_market_generation') != universe['generation']:
        raise PersonalRankingError('personal_market_changed', 'The personal price curve changed with Market evidence. Reload before evaluating.', 409)
    result = personal_values(doc, universe)
    if not result['available']:
        raise PersonalRankingError('personal_evidence_unavailable', result['reason'], 409)
    context.update(values={to_trade_id(k): v for k, v in result['values'].items()},
                   neutral_values={r['trade_asset_id']: r['market_value'] for r in universe['rows']},
                   market_generation=universe['generation'], source_generation=universe['source_generation'],
                   publication_token=_publication_token(data, market_reader))
    return context


def validate_personal_context(data, payload, context, **kwargs):
    from src.core.accounts.personal_store import load_personal
    account = kwargs.get('account') or current_account()
    membership = _scope(data, account)
    store = kwargs.get('store')
    if store is None:
        raise PersonalRankingError('personal_unavailable', 'Personal preferences cannot be verified.', 503)
    _live_scope(store, account, membership)
    doc = load_personal(store, account.account_id, membership.league_id, membership.roster_id)
    if ((doc or {}).get('revision', 0) != context.get('revision')
            or context.get('scope') != [account.account_id, membership.league_id, membership.roster_id]
            or payload.get('valuation_mode', 'neutral') != context.get('mode')
            or (context.get('mode') == 'custom'
                and _publication_token(data, kwargs.get('market_reader')) != context.get('publication_token'))):
        raise PersonalRankingError('personal_context_changed', 'Personal or source evidence changed during this operation. Retry.', 409)


def personal_bootstrap(data, active_id, *, store=None, market_reader=None, account=None):
    account = account or current_account()
    if account is None or store is None:
        return {'mode': 'neutral', 'revision': 0, 'initialized': False, 'available': False}
    try:
        state = view_state(store, data, market_reader, account)
    except PersonalRankingError as exc:
        # Optional personal preparation cannot take Neutral Trade navigation down.
        from src.core.accounts.personal_store import load_personal
        membership = _scope(data, account)
        doc = load_personal(store, account.account_id, membership.league_id, membership.roster_id)
        return {'mode': 'neutral', 'revision': (doc or {}).get('revision', 0),
                'initialized': doc is not None, 'available': False, 'personal_available': False,
                'limitations': [str(exc)]}
    if state['context']['roster_id'] != active_id:
        raise PersonalRankingError('unauthorized_franchise', 'Only your franchise can use your personal rankings.', 403)
    result = {key: state[key] for key in ('mode', 'revision', 'initialized', 'generation', 'baseline_generation', 'personal_available', 'limitations', 'compatibility_issues', 'recovery_url')}
    result.update(market_generation=state['generation'], available=state['personal_available'], values={})
    if state['personal_available']:
        context = resolve_personal_context(data, {'valuation_mode': 'custom', 'personal_revision': state['revision'],
            'personal_market_generation': state['generation']}, store=store, market_reader=market_reader, account=account)
        result['values'] = context['values']
    return result
