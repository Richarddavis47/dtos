"""Bounded admission and lifetime ownership for explicit Trade operations.

Cold 180-candidate fixtures measured 188--222 MB incremental container usage,
including response JSON, with both roster-only and 12,229-identity sources.
Reserve 256 MiB for work and another 128 MiB for ordinary overlapping reads.
Clean inactive file pages are a conditional reclaim allowance, never free heap:
credit at most half, capped at 384 MiB, only with complete cgroup evidence.
FOIS's separate raw-memory policy and 768 MiB reserve are unchanged.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from threading import Event
from time import monotonic

from src.platform.lifecycle import lifecycle_coordinator, memory_snapshot, _key_value_file

MIB = 1024 * 1024
WORKING_BYTES = 256 * MIB
SAFETY_BYTES = 128 * MIB
MAX_FILE_CREDIT_BYTES = 384 * MIB
SERVICE_LIMIT_BYTES = 2048 * MIB
TRADE_TIMEOUT_SECONDS = 105.0
_control: ContextVar[TradeControl | None] = ContextVar('trade_execution', default=None)
logger = logging.getLogger('dtos.trade_resources')


class TradeSearchDeferred(RuntimeError):
    """No search started, or unsafe work stopped without publishing a result."""


class TradeSearchTimedOut(RuntimeError):
    pass


class _Stopped(BaseException):
    # Like asyncio cancellation, this must cross broad evaluator Exception
    # handlers without becoming an intelligence/valuation failure.
    def __init__(self, reason):
        self.reason = reason


def observe_memory():
    sample = memory_snapshot()
    stat = _key_value_file('/sys/fs/cgroup/memory.stat')
    if stat is not None:
        sample['file_accounting'] = {
            key: stat.get(key) for key in
            ('anon', 'kernel', 'file', 'inactive_file', 'file_dirty', 'file_writeback', 'shmem', 'unevictable')
        }
    return sample


def _number(value):
    return type(value) is int and value >= 0


def assess_memory(sample):
    current, limit = sample.get('cgroup_current_bytes'), sample.get('cgroup_limit_bytes')
    valid = _number(current) and _number(limit) and limit > 0
    limit = min(limit, SERVICE_LIMIT_BYTES) if valid else None
    stat, events = sample.get('file_accounting') or {}, sample.get('cgroup_memory_events') or {}
    file_valid = (valid and all(_number(stat.get(k)) for k in
        ('file', 'inactive_file', 'file_dirty', 'file_writeback', 'shmem', 'unevictable'))
        and all(_number(events.get(k)) for k in ('oom', 'oom_kill'))
        and stat['inactive_file'] <= stat['file'] <= current)
    clean = max(0, min(stat['inactive_file'], stat['file'] - stat['shmem'])
        - stat['file_dirty'] - stat['file_writeback'] - stat['unevictable']) if file_valid else 0
    credit = min(clean // 2, MAX_FILE_CREDIT_BYTES)
    raw_headroom = limit - current if valid else None
    usable = raw_headroom + credit if valid else None
    admitted = valid and current <= limit and usable >= WORKING_BYTES + SAFETY_BYTES
    return dict(admitted=admitted,
        reason='unknown_telemetry' if not valid else 'ready' if admitted else 'capacity',
        current_bytes=current, limit_bytes=limit, raw_headroom_bytes=raw_headroom,
        clean_inactive_file_bytes=clean, conditional_file_credit_bytes=credit,
        admission_headroom_bytes=usable, working_bytes=WORKING_BYTES, safety_bytes=SAFETY_BYTES,
        events={k: events.get(k) for k in ('oom', 'oom_kill')})


def public_readiness():
    observation = assess_memory(observe_memory())
    busy = not lifecycle_coordinator.trade_search_available()
    logger.info('trade_readiness', extra={'event': 'trade_readiness',
        'diagnostic': {'schema': 'trade-resource-v1', 'observation': observation, 'heavy_work_busy': busy}})
    state = 'deferred' if busy else 'ready' if observation['admitted'] else 'unknown' if observation['reason'] == 'unknown_telemetry' else 'deferred'
    message = ('Capacity is currently available. It will be checked again when you generate.' if state == 'ready'
        else 'Other league preparation or a Trade operation is still finishing. Wait briefly, then choose Generate again; your offer is unchanged.' if busy
        else 'DTOS cannot verify safe search capacity right now. Try Generate again shortly; your offer is unchanged.' if state == 'unknown'
        else 'Trade search is temporarily paused for capacity. Wait briefly, then choose Generate again; your lineup evidence and offer are unchanged.')
    return {'state': state, 'message': message, 'checked_at': datetime.now(timezone.utc).isoformat(),
            'automatic_retry': False}


def _recover_unused(control):
    """One bounded pass, only on an explicit operation, never cache invalidation."""
    from src.core.intelligence.cache import intelligence_cache
    from src.core.trade_intelligence.lineup_memo import lineup_store
    from src.core.fois.process_execution import retire_idle_fois_executor_sync
    from src.platform.memory_reclamation import release_unused_allocator_pages
    retired = retire_idle_fois_executor_sync(force=True)
    expired = 0
    for _ in range(intelligence_cache.max_entries):
        control.stop_check()
        if not intelligence_cache.expire_one():
            break
        expired += 1
    lineup_store.expire()
    trimmed = release_unused_allocator_pages()
    return dict(expired_entries=expired, idle_worker_retired=retired, allocator_trimmed=trimmed)


@dataclass
class TradeControl:
    deadline: float
    cancelled: Event = field(default_factory=Event)
    next_observation: float = 0.0
    initial_events: dict = field(default_factory=dict)

    def stop_check(self):
        if self.cancelled.is_set():
            raise _Stopped('cancelled')
        if monotonic() >= self.deadline:
            raise _Stopped('timeout')

    def checkpoint(self):
        self.stop_check()
        if monotonic() < self.next_observation:
            return
        self.next_observation = monotonic() + .25
        observation = assess_memory(observe_memory())
        usable = observation['admission_headroom_bytes']
        advanced = any(_number(observation['events'].get(k)) and _number(self.initial_events.get(k))
            and observation['events'][k] > self.initial_events[k] for k in ('oom', 'oom_kill'))
        if usable is None or observation['current_bytes'] > observation['limit_bytes'] or usable < SAFETY_BYTES or advanced:
            raise _Stopped('capacity')


def trade_checkpoint():
    control = _control.get()
    if control is not None:
        control.checkpoint()


def _execute(operation, control):
    if not lifecycle_coordinator.try_reserve_trade_search():
        raise TradeSearchDeferred('Other league preparation or a Trade operation is still finishing. Wait briefly, then retry explicitly; your offer is unchanged.')
    token = None
    started = monotonic()
    outcome = 'failed'
    try:
        control.stop_check()
        observation = assess_memory(observe_memory())
        recovery = None
        if not observation['admitted'] and observation['reason'] != 'unknown_telemetry' and observation['raw_headroom_bytes'] >= 16 * MIB:
            recovery = _recover_unused(control)
            observation = assess_memory(observe_memory())
        logger.info('trade_admission', extra={'event': 'trade_admission',
            'diagnostic': {'schema': 'trade-resource-v1', 'observation': observation, 'recovery': recovery}})
        if not observation['admitted']:
            outcome = 'deferred'
            raise TradeSearchDeferred('Trade work is temporarily paused because safe capacity could not be established. Wait briefly, then retry explicitly; your offer and prepared evidence are unchanged.')
        control.initial_events = observation['events']
        token = _control.set(control)
        trade_checkpoint()
        result = operation()
        trade_checkpoint()
        outcome = 'complete'
        return result
    except _Stopped as stopped:
        outcome = stopped.reason
        if stopped.reason == 'timeout':
            raise TradeSearchTimedOut('This Trade operation reached its time limit and stopped. Your offer is unchanged; choose Generate or Evaluate to retry.') from None
        if stopped.reason == 'capacity':
            raise TradeSearchDeferred('Capacity changed while this Trade operation was running. It stopped safely; your offer is unchanged. Wait briefly, then retry explicitly.') from None
        raise
    finally:
        if token is not None:
            _control.reset(token)
        lifecycle_coordinator.release_trade_search()
        logger.info('trade_execution_finished', extra={'event': 'trade_execution_finished',
            'diagnostic': {'schema': 'trade-resource-v1', 'outcome': outcome},
            'duration_ms': round((monotonic()-started)*1000, 3)})


async def run_trade_operation(operation, *, request=None):
    """Own the real thread until it exits, including disconnect/repeated cancel."""
    control = TradeControl(monotonic() + TRADE_TIMEOUT_SECONDS)
    task = asyncio.create_task(asyncio.to_thread(_execute, operation, control))
    cancelled = False
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=.1)
            if request is not None and await request.is_disconnected():
                cancelled = True
                control.cancelled.set()
        if cancelled:
            # Retrieve the result/exception so nothing is left unobserved.
            try:
                task.result()
            except BaseException:
                pass
            raise asyncio.CancelledError()
        return task.result()
    except asyncio.CancelledError:
        control.cancelled.set()
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        try:
            task.result()
        except BaseException:
            pass
        raise
