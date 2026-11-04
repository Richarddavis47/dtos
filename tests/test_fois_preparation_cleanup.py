"""Real scratch preparation under repeated cancellation and process interruption."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from src.core.fois import process_execution as execution
from src.core.fois.repository import FOISRepository
from tests.test_fois_process_execution import cache_input, fixture


async def delivery_checkpoint():
    """Deliver cancellation callbacks while the writer is held by a barrier."""
    for _ in range(4):
        checkpoint = asyncio.get_running_loop().create_future()
        asyncio.get_running_loop().call_soon(checkpoint.set_result, None)
        await checkpoint


class PreparationCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await execution.shutdown_fois_executor()

    async def exercise(self, root, *, cancellations=0, failure=False):
        repository = FOISRepository(root / 'fois.sqlite3')
        cache = cache_input(root, fixture())
        before = repository.path.read_bytes(), cache.read_bytes()
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        original = execution._prepare_working_database
        worker_errors = []
        premature = []

        def controlled(source, target, league):
            try:
                # Start actual scratch storage before holding the rest of the
                # real preparation. Cleanup must not remove/recreate this path.
                FOISRepository(target)
                entered.set()
                if not release.wait(10):
                    raise AssertionError('Preparation barrier was not released')
                original(source, target, league)
                if failure:
                    raise OSError('controlled preparation failure')
            except Exception as exc:
                worker_errors.append(exc)
                raise
            finally:
                finished.set()

        with mock.patch.object(execution, '_prepare_working_database', side_effect=controlled), \
                mock.patch.object(execution, '_submit', wraps=execution._submit) as submit, \
                mock.patch.object(execution, '_validate_and_publish', wraps=execution._validate_and_publish) as publish:
            task = asyncio.create_task(execution.generate_fois_isolated(fixture(), repository, cache_file=cache))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                directories = list(root.glob('.dtos-fois-compute-*'))
                self.assertEqual(len(directories), 1)
                for index in range(cancellations):
                    task.cancel(f'cancel-{index}')
                    await delivery_checkpoint()
                    if task.done() or not directories[0].exists():
                        premature.append(index)
            finally:
                release.set()
                self.assertTrue(await asyncio.to_thread(finished.wait, 5))

            if cancellations:
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(asyncio.shield(task), 10)
                self.assertTrue(task.cancelled())
            elif failure:
                with self.assertRaisesRegex(OSError, 'controlled preparation failure'):
                    await asyncio.wait_for(task, 10)
            else:
                scores, _, metrics = await asyncio.wait_for(task, 10)
                self.assertEqual(len(scores), 2)
                self.assertEqual(metrics['exit_status'], 0)

            residue = list(root.glob('.dtos-fois-compute-*'))
            self.assertFalse(residue, f'Temporary preparation residue: {residue}')
            self.assertEqual(premature, [], 'Scratch was removed before its active preparation finished')
            if cancellations or failure:
                submit.assert_not_called()
                publish.assert_not_called()
                self.assertEqual((repository.path.read_bytes(), cache.read_bytes()), before)
            else:
                submit.assert_called_once()
                publish.assert_called_once()
            self.assertEqual(len(worker_errors), int(failure))
            if failure:
                self.assertIsInstance(worker_errors[0], OSError)
        return {'cancellations': cancellations, 'failure': failure, 'scratch_directories': 0,
                'active_copy_removed': False, 'abandoned_publications': 0}

    async def test_second_cancellation_does_not_remove_an_active_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            await self.exercise(Path(directory), cancellations=2)

    async def test_many_cancellations_preserve_copy_and_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            await self.exercise(Path(directory), cancellations=20)

    async def test_cancelled_failed_preparation_remains_cancelled_and_cleans(self):
        with tempfile.TemporaryDirectory() as directory:
            await self.exercise(Path(directory), cancellations=3, failure=True)

    async def test_preparation_failure_cleans_without_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            await self.exercise(Path(directory), failure=True)

    async def test_success_cleans_after_real_compute_and_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            await self.exercise(Path(directory))

    async def test_repeated_mixed_operations_leave_no_temporary_storage_growth(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for _ in range(5):
                for cancellations, failure in ((0, False), (0, True), (1, False), (2, False), (8, False), (3, True)):
                    rows.append(await self.exercise(root, cancellations=cancellations, failure=failure))
            self.assertEqual(len(rows), 30)
            self.assertFalse(list(root.glob('.dtos-fois-compute-*')))
            print(json.dumps({'operations': len(rows), 'scratch_directories': 0,
                              'scratch_bytes': 0, 'abandoned_publications': 0,
                              'canonical_unchanged_after_every_failed_or_cancelled_operation': True}))

    @unittest.skipUnless(os.name == 'posix', 'POSIX SIGTERM/SIGKILL controls run on Linux')
    async def test_graceful_process_interrupt_drains_repeated_cancellation(self):
        await self.interrupted_process(force=False)

    @unittest.skipUnless(os.name == 'posix', 'POSIX SIGTERM/SIGKILL controls run on Linux')
    async def test_hard_kill_cannot_run_cleanup_but_preserves_canonical_source(self):
        await self.interrupted_process(force=True)

    async def interrupted_process(self, *, force):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = 'from pathlib import Path; import sys; from tests.test_fois_preparation_cleanup import interruption_child; interruption_child(Path(sys.argv[1]))'
            process = subprocess.Popen([sys.executable, '-c', command, str(root)],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, start_new_session=True)
            try:
                ready = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), 10)
                self.assertEqual(ready.strip(), 'PREPARING')
                canonical = (root / 'fois.sqlite3').read_bytes()
                cache = (root / 'cache.json').read_bytes()
                process.send_signal(signal.SIGKILL if force else signal.SIGTERM)
                if force:
                    stdout, stderr = await asyncio.to_thread(process.communicate, timeout=10)
                    self.assertEqual(process.returncode, -signal.SIGKILL, stdout + stderr)
                    # A hard kill cannot execute finally blocks. Never pretend
                    # this is an application cleanup pass or delete live work.
                    residue = list(root.glob('.dtos-fois-compute-*'))
                    self.assertEqual(len(residue), 1)
                    print(json.dumps({'interruption': 'SIGKILL', 'expected_residual_directories': 1,
                                      'canonical_unchanged': True, 'automatic_cleanup_claimed': False}))
                else:
                    observed = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), 10)
                    self.assertEqual(observed.strip(), 'INTERRUPTED')
                    stdout, stderr = await asyncio.to_thread(process.communicate, input='release\n', timeout=10)
                    self.assertEqual(process.returncode, 0, stdout + stderr)
                    row = json.loads(stdout.strip())
                    self.assertEqual(row, {'cancelled': True, 'scratch_directories': 0, 'writer_errors': 0})
                    self.assertFalse(list(root.glob('.dtos-fois-compute-*')))
                self.assertEqual((root / 'fois.sqlite3').read_bytes(), canonical)
                self.assertEqual((root / 'cache.json').read_bytes(), cache)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    await asyncio.to_thread(process.communicate, timeout=5)
                # The disposable fixture's owner removes its known test files
                # only after process exit; this is not a production scavenger.


def interruption_child(root):
    """Controlled real preparation with an actual graceful POSIX signal."""
    async def main():
        repository = FOISRepository(root / 'fois.sqlite3')
        cache = cache_input(root, fixture())
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        original = execution._prepare_working_database
        errors = []

        def controlled(*arguments):
            try:
                FOISRepository(arguments[1])
                entered.set()
                if not release.wait(20):
                    raise AssertionError('Interruption barrier was not released')
                original(*arguments)
            except Exception as exc:
                errors.append(type(exc).__name__)
                raise
            finally:
                finished.set()

        with mock.patch.object(execution, '_prepare_working_database', side_effect=controlled), \
                mock.patch.object(execution, '_submit', side_effect=AssertionError('Abandoned work submitted')):
            task = asyncio.create_task(execution.generate_fois_isolated(fixture(), repository, cache_file=cache))

            async def interrupt():
                for _ in range(3):
                    task.cancel()
                    await delivery_checkpoint()
                print('INTERRUPTED', flush=True)

            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(interrupt()))
            try:
                assert await asyncio.to_thread(entered.wait, 5)
                print('PREPARING', flush=True)
                assert (await asyncio.to_thread(sys.stdin.readline)).strip() == 'release'
            finally:
                release.set()
                assert await asyncio.to_thread(finished.wait, 5)
            try:
                await task
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError('Interrupted preparation resumed')
            row = {'cancelled': task.cancelled(), 'scratch_directories': len(list(root.glob('.dtos-fois-compute-*'))),
                   'writer_errors': len(errors)}
            print(json.dumps(row), flush=True)
            assert row == {'cancelled': True, 'scratch_directories': 0, 'writer_errors': 0}

    asyncio.run(main())
