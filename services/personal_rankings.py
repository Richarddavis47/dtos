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
from src.core.accounts.personal_store import ABSOLUTE_METHOD, RELATIVE_METHOD, VALUATION_METHODS

METHOD = ABSOLUTE_METHOD
METHOD_LABELS = {ABSOLUTE_METHOD: 'Absolute Slot', RELATIVE_METHOD: 'Relative Priced-Order'}
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
        return str(name or 'Player identity not confirmed')
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
        # Sleeper's game/roster status is not a dynasty-price admission rule.
        # An inactive player can still have a verified current Market price.
        # Require that exact price below; never infer it from status or activity.
        if status == 'retired':
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
                         'market_rank': len(rows) + 1,
                         **({'limitation': 'Sleeper currently marks this player inactive. A compatible dynasty Market price is available; this is not confirmation that the player is available to play.'}
                            if kind == 'player' and str(row.get('status') or '').lower() == 'inactive' else {})})
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
        if status == 'retired':
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
            'generated_at': identity.get('generated_at') or getattr(market_reader, 'generated_at', None),
            'source_semantic_generation': str(getattr(market_reader, 'semantic_generation', None) or source),
            'league_id': league_id, 'rows': rows, 'unavailable_rows': unavailable}


def valuation_method(document):
    schema = (document or {}).get('schema', 1)
    method = (document or {}).get('valuation_method', METHOD)
    if (type(schema) is not int or schema not in (1, 2) or not isinstance(method, str) or method not in VALUATION_METHODS
            or schema == 1 and method != METHOD):
        raise PersonalRankingError('valuation_method_unsupported',
            'This Custom valuation method needs a compatible application version. Neutral remains available.', 409)
    return method


def personal_values(document, universe):
    """Choose an explicitly saved contract; legacy documents keep Absolute."""
    method = valuation_method(document)
    result = _absolute_values(document, universe)
    order = document.get('order') or []
    valid_order = bool(order) and len(set(order)) == len(order) and set(order) == set((document.get('baseline') or {}).get('ids') or [])
    if method == RELATIVE_METHOD and valid_order:
        rows = {r['asset_id']: r for r in universe['rows']}
        priced_order = [key for key in document['order'] if key in rows]
        curve = sorted((rows[key]['market_value'] for key in priced_order), reverse=True)
        result['values'] = dict(zip(priced_order, curve))
        result['partial_available'] = bool(priced_order) and not result['available']
        if not result['available']:
            result['reason'] = (f'{len(priced_order)} saved assets have Relative Custom values. '
                f'{len(document["order"]) - len(priced_order)} saved assets lack compatible prices and remain unvalued. '
                'Their saved positions and preferences are unchanged. Supported-only Custom packages can be assessed; Neutral remains independent.')
    return {**result, 'method': method}


def _absolute_values(document, universe):
    """Permute the existing price curve; tiers never manufacture cardinal prices.

    No interpolation/extrapolation, inflation, clipping or personal price copies.
    A missing quote remains a reserved input, never a removed/zero-priced asset.
    Only slots identical under every possible compatible completion are usable.
    New assets require an explicit Restart.
    """
    rows = {r['asset_id']: r for r in universe['rows']}
    order = document.get('order') or []
    baseline = (document.get('baseline') or {}).get('ids') or []
    if not order or len(set(order)) != len(order) or set(order) != set(baseline):
        return {'available': False, 'partial_available': False, 'values': {},
                'reason': 'Saved ranking order is incomplete or invalid.'}
    order_set = set(order)
    missing = [(index, key) for index, key in enumerate(order, 1) if key not in rows]
    if missing:
        rejected = universe.get('unavailable_rows') or {}
        issues = []
        for saved_rank, key in missing:
            issue = dict(rejected.get(key) or {'asset_id': key, 'label': 'An asset in your saved order',
                'position': 'PICK' if key.startswith('pick:') else 'Unavailable',
                'code': 'asset_not_in_market', 'retryable': True,
                'reason': 'This saved exact asset is absent from the current Market list. Its current identity and price cannot be confirmed; no replacement asset or zero price was assumed.'})
            issue.update(saved_rank=saved_rank, can_remove=len(order) > 1)
            issues.append(issue)
        first = issues[0]
        count = len(issues)
        # Order statistics are monotone in each input. These are internal
        # extremal completions of the existing 0..1000 domain, NOT prices for
        # missing assets. Agreement proves a slot cannot depend on those inputs.
        # Keep every saved slot; never compress the priced subset's curve.
        known = [rows[key]['market_value'] for key in order if key in rows]
        lower = sorted([*known, *([0] * count)], reverse=True)
        upper = sorted([*known, *([1000] * count)], reverse=True)
        exact = {key: lower[index] for index, key in enumerate(order)
                 if key in rows and lower[index] == upper[index]}
        reason = (f"Current Market evidence needs attention for {first['label']}"
                  + (f' and {count - 1} other saved asset(s)' if count > 1 else '')
                  + f". {first['reason']} "
                  + (f'{len(exact)} saved assets still have exact personal values; Custom calculations can use those assets only. '
                     if exact else 'No personal values can yet be verified without the missing prices. ')
                  + 'Review affected assets or retry; your saved order, tiers and preferences are unchanged. Neutral DTOS remains available.')
        return {'available': False, 'partial_available': bool(exact), 'values': exact, 'reason': reason,
                'unavailable_ids': [key for _rank, key in missing], 'compatibility_issues': issues,
                'new_asset_ids': [key for key in rows if key not in order_set]}
    # Only the saved cohort supplies the curve: a new unranked asset cannot
    # silently push every existing opinion into a different slot.
    order_set = set(order)
    curve = sorted((rows[key]['market_value'] for key in order), reverse=True)
    return {'available': True, 'partial_available': False, 'values': dict(zip(order, curve)), 'reason': None,
            'new_asset_ids': [key for key in rows if key not in order_set], 'method': METHOD}


def _review_reference(document, universe):
    """Bounded identity/digest acknowledgment, never a saved price map."""
    result = personal_values(document, universe)
    rows = {r['asset_id'] for r in universe['rows']}
    return {'generation': universe['generation'], 'source_generation': universe['source_generation'],
            'generated_at': universe.get('generated_at'),
            'priced_ids': [key for key in document['order'] if key in rows],
            'value_digest': _digest(result['values'])}


def method_preview(document, universe, target, *, account, context):
    if not isinstance(target, str) or target not in VALUATION_METHODS:
        raise PersonalRankingError('valuation_method_unsupported', 'Choose Absolute Slot or Relative Priced-Order.')
    proposed = {**document, 'schema': 2, 'valuation_method': target}
    before, after = personal_values(document, universe), personal_values(proposed, universe)
    rows = {r['asset_id']: r for r in universe['rows']}
    # Validate the exact prospective representation before inviting confirmation.
    # A method opt-in must not silently enlarge the existing document budget.
    from src.core.accounts.personal_store import encode_document
    proposed['method_review'] = _review_reference(proposed, universe)
    encoded = encode_document({k: v for k, v in proposed.items() if k not in {'revision', 'created_at', 'updated_at'}})
    owned = account.membership.roster_id
    def summary(result):
        return {'method': result['method'], 'label': METHOD_LABELS[result['method']],
                'personal_value_count': len(result['values']),
                'owned_value_count': sum(rows[k]['owner_roster_id'] == owned for k in result['values']),
                'unpriced_count': len(document['order']) - sum(k in rows for k in document['order'])}
    def item(key):
        row = rows.get(key) or (universe.get('unavailable_rows') or {}).get(key) or {}
        return {'asset_id': key, 'label': row.get('label') or 'Saved asset',
                'market_value': row.get('market_value'),
                'current_value': before['values'].get(key), 'proposed_value': after['values'].get(key)}
    changed = [k for k in document['order'] if before['values'].get(k) != after['values'].get(k)]
    missing = [k for k in document['order'] if k not in rows]
    examples = list(dict.fromkeys([*changed[:5], *missing[:1], *document['order'][:3]]))[:8]
    # Illustrative arithmetic only, never a generated offer or qualification.
    outgoing = next((k for k in document['order'] if k in rows and rows[k]['owner_roster_id'] == owned), None)
    incoming = next((k for k in document['order'] if k in rows and rows[k]['owner_roster_id'] not in (None, owned)), None)
    packages = []
    if outgoing and incoming:
        def totals(values, keys):
            return sum(values[k] for k in keys) if all(k in values for k in keys) else None
        sent = [outgoing]
        pick = next((k for k in document['order'] if k.startswith('pick:') and k != outgoing
                     and k in rows and rows[k]['owner_roster_id'] == owned), None)
        for keys in [sent, *([sent + [pick]] if pick else [])]:
            packages.append({'sent': [item(k) for k in keys], 'received': [item(incoming)],
                'current': {'sent': totals(before['values'], keys), 'received': totals(before['values'], [incoming])},
                'proposed': {'sent': totals(after['values'], keys), 'received': totals(after['values'], [incoming])}})
    token = _digest([account.account_id, account.session_id, context, document,
                     universe['generation'], universe.get('generated_at'), target])
    reviewed = set((document.get('method_review') or {}).get('priced_ids') or ())
    priced = set(document['order']) & set(rows)
    changed_population = bool(document.get('method_review'))
    eligibility_changes = [{'label': item(k)['label'], 'change': 'Price now compatible' if k in priced else 'Price no longer compatible'}
                           for k in document['order'] if changed_population and ((k in reviewed) != (k in priced))]
    return {'current': summary(before), 'proposed': summary(after), 'examples': [item(k) for k in examples],
            'eligibility_changes': eligibility_changes[:8], 'eligibility_change_count': len(eligibility_changes),
            'saved_document_bytes': len(encoded.encode('utf-8')),
            'packages': packages, 'preview_token': token, 'ranking_revision': document['revision'],
            'market_generation': universe['generation'], 'source_generation': universe['source_generation'],
            'generated_at': universe.get('generated_at'),
            'disclosure': 'Relative uses your order among compatible priced saved assets. Unpriced rows stay saved without a value or numerical price slot. New or lost compatible quotes can reprice other assets without an NFL performance change. Neutral prices do not change. Example packages compare personal totals only; they are not recommendations.'}


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
        row['personal_value_available'] = key in values['values']
        if document and key in order_set and key in current and key not in values['values']:
            row['personal_value_reason'] = 'This personal rank depends on Market prices missing elsewhere in your saved order. Its neutral Market price is still available.'
        rows.append(row)
    context = workspace_context(data, membership.roster_id)
    method = valuation_method(document)
    review = (document or {}).get('method_review') or {}
    publication_changed = (method == RELATIVE_METHOD and review.get('generation') != universe['generation']
                           and review.get('value_digest') != _digest(values['values']))
    priced_ids = set((document or {}).get('order') or ()) & set(current)
    reviewed_ids = set(review.get('priced_ids') or ())
    return {'initialized': document is not None, 'revision': (document or {}).get('revision', 0),
            'mode': (document or {}).get('mode', 'neutral'), 'generation': universe['generation'],
            'baseline_generation': ((document or {}).get('baseline') or {}).get('generation'),
            'baseline_source_generation': ((document or {}).get('baseline') or {}).get('source_generation'),
            'rows': rows, 'context': {k: context[k] for k in ('league_id', 'roster_id', 'binding')},
            'personal_available': values['available'], 'method': method, 'method_label': METHOD_LABELS[method],
            'source_generation': universe['source_generation'], 'market_generated_at': universe.get('generated_at'),
            'method_review': {'publication_changed': publication_changed,
                'added_count': len(priced_ids - reviewed_ids) if publication_changed else 0,
                'removed_count': len(reviewed_ids - priced_ids) if publication_changed else 0,
                'reviewed_source_generation': review.get('source_generation'),
                'message': ('Market evidence changed since your last method review. Relative values have been recalculated from the current compatible population and saved order. New or lost quotes can reprice other assets; this alone is not an NFL performance change. Review the current comparison before acting.' if publication_changed else None)},
            'personal_partial_available': values.get('partial_available', False),
            'personal_value_count': len(values['values']),
            'limitations': [values['reason']] if values.get('reason') else [],
            'new_asset_ids': values.get('new_asset_ids', []),
            'compatibility_issues': values.get('compatibility_issues', []),
            'eligible_asset_count': len(current), 'saved_asset_count': len(document['order']) if document else 0,
            'recovery_url': '/account/my-dtos#personal-compatibility',
            'method_explanation': ('Relative Custom assigns descending compatible prices to priced saved assets in their relative saved order. Unpriced rows keep their saved positions without a numerical price slot. Moving up cannot lower a personal value at the same publication. New or lost compatible quotes can reprice other assets, without an NFL performance change. Tiers and flags do not set prices; Neutral remains unchanged. New assets are not added to your saved cohort automatically.' if method == RELATIVE_METHOD else 'Your saved global order receives the descending current Market price slots of that same saved cohort. Moving up cannot lower a personal value. Tiers are labels and do not change prices. When quotes are missing, every saved position stays reserved. A priced asset receives a personal value only if that slot is identical for every possible missing price within the supported Market scale. Missing assets never receive guessed prices. New assets need Restart Rankings; no past prices are reconstructed. Removing one asset from your Custom order is an explicit membership edit: other ranks and tier breaks stay in order, but remaining personal values may change because that asset’s current price slot leaves the curve. The saved baseline generation identifies the original seed publication, not a new Market quote.')}


def apply_command(store, data, market_reader, account, payload, *, verify_source=None):
    from src.core.accounts.personal_store import load_personal, save_personal
    membership = _scope(data, account)
    _live_scope(store, account, membership)
    document = load_personal(store, account.account_id, membership.league_id, membership.roster_id)
    universe = build_universe(data, market_reader, requested_ids=(document or {}).get('order') or ())
    context = workspace_context(data, membership.roster_id)
    expected_context = {k: context[k] for k in ('league_id', 'roster_id', 'binding')}
    if payload.get('context') != expected_context or payload.get('market_generation') != universe['generation']:
        raise PersonalRankingError('personal_context_changed', 'League, session or Market evidence changed. Reload before saving.', 409)
    revision = payload.get('expected_revision')
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise PersonalRankingError('invalid_revision', 'A valid preference revision is required.')
    if revision != (document or {}).get('revision', 0):
        raise PersonalRankingError('personal_revision_changed', 'Your rankings changed in another tab. Reload before editing.', 409)
    command = payload.get('command')
    ids = [r['asset_id'] for r in universe['rows']]
    if command in {'method_preview', 'valuation_method'}:
        if not document:
            raise PersonalRankingError('rankings_not_started', 'Create Custom Rankings before comparing methods.', 409)
        preview = method_preview(document, universe, payload.get('valuation_method'), account=account, context=expected_context)
        if command == 'method_preview':
            _live_scope(store, account, membership)
            if verify_source is not None:
                verify_source()
            return {'method_preview': preview}
        if (payload.get('confirmation') != 'APPLY VALUATION METHOD'
                or payload.get('preview_token') != preview['preview_token']):
            raise PersonalRankingError('method_preview_changed', 'Open a fresh valuation comparison and explicitly confirm it. No preferences changed.', 409)
    if command in {'initialize', 'restart'}:
        if command == 'initialize' and document:
            raise PersonalRankingError('already_initialized', 'Use Restart Rankings to replace a saved custom order.', 409)
        if command == 'restart' and payload.get('confirmation') != 'RESTART RANKINGS':
            raise PersonalRankingError('confirmation_required', 'Confirm that customized order and tiers will be lost.')
        if not ids:
            raise PersonalRankingError('market_unavailable', 'No eligible priced assets are available to seed rankings.', 503)
        previous_method = valuation_method(document)
        document = {'schema': 1, 'baseline': {'generation': universe['generation'], 'ids': ids,
                    'source_generation': universe['source_generation'],
                    'source_semantic_generation': universe['source_semantic_generation']},
                    'order': ids, 'tiers': [], 'preferences': {} if payload.get('reset_preferences') is True else (document or {}).get('preferences', {}),
                    'mode': 'custom'}
        if previous_method == RELATIVE_METHOD:
            document.update(schema=2, valuation_method=previous_method)
            document['method_review'] = _review_reference(document, universe)
    elif not document:
        raise PersonalRankingError('rankings_not_started', 'Initialize the full Market-seeded rankings first.', 409)
    else:
        document = {k: deepcopy(v) for k, v in document.items() if k not in {'revision', 'created_at', 'updated_at'}}
        key = payload.get('asset_id')
        if command in {'reorder', 'tiers', 'preferences'} and key not in document['order']:
            raise PersonalRankingError('asset_not_ranked', 'This asset is not in your saved baseline. Restart to include new assets.')
        if command == 'valuation_method':
            document.update(schema=2, valuation_method=payload['valuation_method'])
            document['method_review'] = _review_reference(document, universe)
        elif command == 'remove_asset':
            if payload.get('confirmation') != 'REMOVE FROM CUSTOM ORDER':
                raise PersonalRankingError('confirmation_required', 'Confirm removal of this exact asset from your Custom order. Its own tier break is removed; other ranks, tiers and Target/Avoid/Protect preferences are preserved. Remaining personal values may change.')
            if key not in document['order']:
                raise PersonalRankingError('asset_not_ranked', 'This exact asset is not in your saved Custom order.', 409)
            if len(document['order']) <= 1:
                raise PersonalRankingError('last_ranked_asset', 'Keep at least one ranked asset. Use Neutral DTOS or explicitly Restart Rankings instead.')
            document['order'].remove(key)
            document['baseline']['ids'].remove(key)
            document['tiers'] = [asset for asset in document['tiers'] if asset != key]
            if document.get('method_review'):
                document['method_review']['priced_ids'] = [k for k in document['method_review']['priced_ids'] if k != key]
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
            # Protection is ownership intent, not a price endorsement. The
            # exact owner is independently prepared even if pricing is absent.
            row = next((r for r in universe['rows'] if r['asset_id'] == key), None)
            if row is None:
                row = (universe.get('unavailable_rows') or {}).get(key)
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
               'baseline_generation': ((doc or {}).get('baseline') or {}).get('generation'), 'method': valuation_method(doc)}
    if mode == 'neutral':
        return context
    if not doc:
        raise PersonalRankingError('rankings_not_started', 'Initialize your complete Custom Rankings first.', 409)
    universe = build_universe(data, market_reader, requested_ids=doc['order'])
    if require_revision and payload.get('personal_market_generation') != universe['generation']:
        raise PersonalRankingError('personal_market_changed', 'The personal price curve changed with Market evidence. Reload before evaluating.', 409)
    result = personal_values(doc, universe)
    if not (result['available'] or result.get('partial_available')):
        raise PersonalRankingError('personal_evidence_unavailable', result['reason'], 409)
    context.update(values={to_trade_id(k): v for k, v in result['values'].items()},
                   availability='full' if result['available'] else 'partial',
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
            or valuation_method(doc) != context.get('method')
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
                'method': valuation_method(doc), 'method_label': METHOD_LABELS[valuation_method(doc)],
                'readiness_code': exc.code, 'limitations': [str(exc)]}
    if state['context']['roster_id'] != active_id:
        raise PersonalRankingError('unauthorized_franchise', 'Only your franchise can use your personal rankings.', 403)
    result = {key: state[key] for key in ('mode', 'revision', 'initialized', 'generation', 'baseline_generation', 'personal_available', 'personal_partial_available', 'personal_value_count', 'limitations', 'compatibility_issues', 'recovery_url', 'method', 'method_label', 'method_review')}
    result.update(market_generation=state['generation'],
                  available=state['personal_available'] or state['personal_partial_available'], values={})
    if result['available']:
        context = resolve_personal_context(data, {'valuation_mode': 'custom', 'personal_revision': state['revision'],
            'personal_market_generation': state['generation']}, store=store, market_reader=market_reader, account=account)
        result['values'] = context['values']
    return result
