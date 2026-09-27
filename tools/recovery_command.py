"""Explicit operator recovery; no production action on import or startup."""
import argparse
import json
from pathlib import Path

from tools.recovery_backup import receipt_verifier, verify_local
from tools.recovery_build import build_fois, build_projection
from tools.recovery_guard import RecoveryGuard
from tools.recovery_reads import mixed_reads
from tools.retained_storage_recovery import RetainedRecovery
from tools.staged_fois_cutover import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'prepare', 'activate', 'rollback', 'accept', 'remove-old', 'verify-backup'))
    parser.add_argument('--kind', choices=('fois', 'projection'))
    parser.add_argument('--live', type=Path)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--receiver-public-key', type=Path)
    parser.add_argument('--source-sha256')
    parser.add_argument('--candidate-sha256')
    parser.add_argument('--exact-old', type=Path)
    parser.add_argument('--peer', type=Path)
    parser.add_argument('--league', action='append')
    parser.add_argument('--rehearsal', action='store_true')
    parser.add_argument('--temporary-root', type=Path, help='Local rehearsal temporary root only')
    parser.add_argument('--package', type=Path)
    parser.add_argument('--local-private-key', type=Path)
    parser.add_argument('--local-scratch', type=Path)
    args = parser.parse_args()
    if args.action == 'verify-backup':
        if not all((args.package, args.local_private_key, args.local_scratch)):
            parser.error('Local package, private key and scratch required')
        report = verify_local(args.package, args.local_private_key.read_bytes(), args.local_scratch)
        with args.receipt.open('x', encoding='utf-8') as out:
            json.dump(report, out, sort_keys=True)
        print(json.dumps({'backup_verified': True, **report['receipt']}))
        return
    if not all((args.live, args.kind, args.receiver_public_key)):
        parser.error('Explicit live store, kind and pinned receiver key required')
    live = args.live.absolute()
    guard = RecoveryGuard(live.parent, rehearsal=args.rehearsal, temporary_root=args.temporary_root)
    verifier = receipt_verifier(args.receiver_public_key.read_bytes())
    backup = json.loads(args.receipt.read_text(encoding='utf-8'))
    tool = RetainedRecovery(live, args.kind, guard, verifier)
    if args.action in ('build', 'prepare'):
        if not args.candidate or not args.source_sha256:
            parser.error('Pinned source and explicit candidate required')
        if sha256(live) != args.source_sha256:
            raise ValueError('Source differs from authorized generation')
    if args.action == 'build':
        builder = build_fois if args.kind == 'fois' else build_projection
        result = builder(live, args.candidate, guard, backup, verifier)
    elif args.action == 'prepare':
        if not args.candidate_sha256:
            parser.error('Pinned candidate checksum required')
        result = tool.prepare(args.candidate, backup, source_sha256=args.source_sha256,
                              candidate_sha256=args.candidate_sha256)
    elif args.action == 'activate':
        result = tool.activate()
    elif args.action == 'rollback':
        result = tool.rollback()
    elif args.action == 'accept':
        if not args.peer or not args.league:
            parser.error('Mixed-format peer and explicit leagues required')
        peer = args.peer.resolve(strict=True)
        if peer.parent != live.parent or peer == live:
            raise ValueError('Peer outside admitted recovery scope')
        peer_hash = sha256(peer)

        def read_validator(kind, _old, active):
            result = mixed_reads(active if kind == 'fois' else peer,
                                 peer if kind == 'fois' else active, args.league)
            if sha256(peer) != peer_hash:
                raise ValueError('Peer generation changed during mixed-format proof')
            return {**result, 'peer_sha256': peer_hash, 'peer_path': str(peer)}
        result = tool.accept(read_validator)
    else:
        if not args.exact_old:
            parser.error('Exact recorded old-store target required')
        result = tool.remove_old(args.exact_old.absolute())
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
