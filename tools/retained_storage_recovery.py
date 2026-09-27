"""Guarded path activation with retained old inode; never invoked by startup.

No application connection routing changes are needed. The configured active
path switches atomically, while a hardlink keeps the *original bytes* intact.
No full-size rollback file is copied onto the service. Journal transitions are
fsynced; interrupted transitions fail closed and retain both generations.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path

from src.platform.storage_gate import database_gate
from tools.recovery_guard import ADMISSION, RESERVE, MIB
from tools.staged_fois_cutover import checked_path, proof, require_no_sidecars, sha256, sync_directory
from tools.projection_retention_migration import verify_copy


def equivalence(kind, old, new):
    for path in (old, new):
        require_no_sidecars(path)
    if kind == 'fois':
        before = proof(old)
        if proof(new) != before:
            raise ValueError('FOIS semantic equivalence failed')
        return before
    if kind == 'projection':
        return verify_copy(old, new)
    raise ValueError('Unknown storage kind')


def atomic_record(path, value):
    pending = path.with_name(path.name + '.pending')
    with pending.open('x', encoding='utf-8') as out:
        json.dump(value, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    os.replace(pending, path)
    sync_directory(path.parent)


class RetainedRecovery:
    """One explicit recovery per pinned source generation.

    backup_verifier validates a signed off-host receipt (not a local DB path).
    read_validator must execute the mixed/app read proof, not assert coverage.
    Commands recheck exact identities at every destructive boundary.
    """

    def __init__(self, live, kind, guard, backup_verifier):
        self.live = Path(live).absolute()
        self.kind = kind
        self.guard = guard
        self.backup_verifier = backup_verifier
        if self.live.parent != guard.root or kind not in ('fois', 'projection'):
            raise ValueError('Recovery scope mismatch')
        self.record = self.live.with_name(self.live.name + '.retained-recovery.json')

    @contextmanager
    def boundary(self):
        self.guard.check()
        with database_gate(self.live, exclusive=True):
            self.guard.check()
            yield

    def read_record(self):
        checked_path(self.record)
        result = json.loads(self.record.read_text(encoding='utf-8'))
        if result['live'] != str(self.live) or result['kind'] != self.kind:
            raise ValueError('Recovery record scope mismatch')
        for field in ('old', 'candidate'):
            path = Path(result[field])
            if path.parent != self.live.parent or path == self.live:
                raise ValueError('Recovery path outside admitted scope')
        expected_old = self.live.with_name(self.live.name + '.retained-' + result['source_sha256'])
        if Path(result['old']) != expected_old:
            raise ValueError('Unknown old-store removal target')
        return result

    def verify_generation(self, state, *, active, old=True):
        if sha256(checked_path(self.live)) != state[active + '_sha256']:
            raise ValueError('Active store generation changed')
        require_no_sidecars(self.live)
        if old:
            original = checked_path(state['old'])
            if sha256(original) != state['source_sha256']:
                raise ValueError('Retained old store changed')
            require_no_sidecars(original)
        self.backup_verifier(state['backup'], state['source_sha256'], state['source_bytes'])

    def prepare(self, candidate, backup, *, source_sha256, candidate_sha256):
        with self.boundary():
            if self.record.exists() or self.record.with_name(self.record.name + '.pending').exists():
                raise RuntimeError('Existing recovery requires explicit review')
            live, candidate = checked_path(self.live), checked_path(candidate)
            if candidate.parent != live.parent or os.path.samefile(live, candidate):
                raise ValueError('Candidate must be distinct and on the same filesystem')
            if sha256(live) != source_sha256 or sha256(candidate) != candidate_sha256:
                raise ValueError('Pinned source/candidate checksum mismatch')
            if source_sha256 == candidate_sha256:
                raise ValueError('No-op recovery prohibited')
            cap = (72 if self.kind == 'fois' else 112) * MIB
            if candidate.stat().st_size > cap:
                raise RuntimeError('Candidate exceeds admitted size')
            self.guard.check(required=RESERVE)
            self.backup_verifier(backup, source_sha256, live.stat().st_size)
            comparison = equivalence(self.kind, live, candidate)
            old = live.with_name(live.name + '.retained-' + source_sha256)
            if old.exists() or old.is_symlink():
                raise RuntimeError('Existing retained path requires review')
            state = dict(live=str(live), kind=self.kind, old=str(old), candidate=str(candidate),
                         source_sha256=source_sha256, candidate_sha256=candidate_sha256,
                         source_bytes=live.stat().st_size, backup=backup,
                         equivalence=comparison, phase='prepared')
            atomic_record(self.record, state)
            return state

    def activate(self):
        with self.boundary():
            state = self.read_record()
            if state['phase'] != 'prepared':
                raise RuntimeError('Activation already attempted; explicit review required')
            self.verify_generation(state, active='source', old=False)
            candidate = checked_path(state['candidate'])
            if sha256(candidate) != state['candidate_sha256']:
                raise ValueError('Candidate changed')
            # Full equivalence is recorded during prepare. Exact file hashes
            # above pin that proof; do not repeatedly decode the entire history.
            self.guard.check(required=RESERVE)
            state['phase'] = 'activating'
            atomic_record(self.record, state)
            # Linking rather than copying consumes no database-sized allocation.
            os.link(self.live, state['old'])
            sync_directory(self.live.parent)
            # The old inode is now retained. Consume the validated candidate
            # name in the atomic path switch, avoiding a second active alias.
            os.replace(candidate, self.live)
            sync_directory(self.live.parent)
            state['phase'] = 'active'
            atomic_record(self.record, state)
            self.verify_generation(state, active='candidate')
            return state

    def switch(self, target):
        pending = self.live.with_name(self.live.name + '.activation-pending')
        if pending.exists() or pending.is_symlink():
            raise RuntimeError('Interrupted activation requires explicit review')
        os.link(target, pending)
        sync_directory(self.live.parent)
        os.replace(pending, self.live)
        sync_directory(self.live.parent)

    def rollback(self):
        with self.boundary():
            state = self.read_record()
            if state['phase'] not in ('active', 'accepted', 'activating'):
                raise RuntimeError('Rollback not admitted in this phase')
            old = checked_path(state['old'])
            if sha256(old) != state['source_sha256']:
                raise ValueError('Retained old store changed')
            if sha256(self.live) not in (state['source_sha256'], state['candidate_sha256']):
                raise ValueError('Unknown active generation')
            for path in (old, self.live):
                require_no_sidecars(path)
            self.backup_verifier(state['backup'], state['source_sha256'], state['source_bytes'])
            candidate = Path(state['candidate'])
            if sha256(self.live) == state['candidate_sha256']:
                if candidate.exists() or candidate.is_symlink():
                    raise RuntimeError('Unexpected candidate path during rollback')
                # Retain the rejected new bytes for inspection without copying.
                os.link(self.live, candidate)
                sync_directory(self.live.parent)
            self.switch(old)
            state['phase'] = 'rolled_back'
            atomic_record(self.record, state)
            self.verify_generation(state, active='source')
            return state

    def accept(self, read_validator):
        with self.boundary():
            state = self.read_record()
            if state['phase'] != 'active':
                raise RuntimeError('Acceptance requires active unaccepted candidate')
            self.verify_generation(state, active='candidate')
            # Both pinned hashes still match the full preparation proof.
            # Validator runs read-only, without acquiring this same storage gate.
            result = read_validator(self.kind, Path(state['old']), self.live)
            if not result or result.get('passed') is not True:
                raise RuntimeError('Post-cutover application reads failed')
            self.verify_generation(state, active='candidate')
            state.update(phase='accepted', application_reads=result)
            atomic_record(self.record, state)
            return state

    def remove_old(self, exact_target):
        with self.boundary():
            state = self.read_record()
            if state['phase'] != 'accepted' or not state.get('application_reads', {}).get('passed'):
                raise RuntimeError('Old-store removal requires explicit post-cutover acceptance')
            target = checked_path(exact_target)
            if target != Path(state['old']) or os.path.samefile(target, self.live):
                raise ValueError('Unknown or active store removal prohibited')
            self.verify_generation(state, active='candidate')
            reads = state['application_reads']
            if reads.get('peer_path'):
                peer = checked_path(reads['peer_path'])
                if peer.parent != self.live.parent or sha256(peer) != reads['peer_sha256']:
                    raise ValueError('Mixed-format peer changed after acceptance')
            if target.stat().st_nlink != 1:
                raise RuntimeError('Unexpected old-store alias; cannot prove reclaim')
            state['phase'] = 'removing'
            atomic_record(self.record, state)
            target.unlink()
            sync_directory(target.parent)
            state['phase'] = 'removed'
            atomic_record(self.record, state)
            return state


def admit_build(guard):
    """Mandatory entry gate; never infer free space from earlier measurements."""
    return guard.check(required=ADMISSION, temporary_output=1024 * 1024)
