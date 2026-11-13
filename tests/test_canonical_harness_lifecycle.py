"""Exercise the actual embedded CI helper without running a second validator."""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
import time
import unittest

import psutil


WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/canonical-release-recovery.yml'


def actual_helper():
    source = WORKFLOW.read_text().split(
        "cat > .validation/canonical-release/runner.py <<'PY'\n", 1
    )[1].split('\n          PY\n', 1)[0]
    tree = ast.parse(textwrap.dedent(source))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_canonical_process']
    assert len(nodes) == 1
    namespace = dict(os=os, signal=signal, subprocess=subprocess, psutil=psutil)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(WORKFLOW), 'exec'), namespace)
    return namespace['run_canonical_process']


class CanonicalHarnessLifecycleTests(unittest.TestCase):
    def test_real_normal_execution_completes(self):
        cleanup = {}
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'output.txt'
            with output.open('w') as stream:
                result = actual_helper()([sys.executable, '-c', "print('actually executed')"], stream, 5, cleanup)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), 'actually executed\n')
        self.assertFalse(cleanup['timeout_triggered'])
        self.assertTrue(cleanup['validator_reaped'])

    def test_nonzero_result_is_not_converted_to_success(self):
        with open(os.devnull, 'w') as stream:
            result = actual_helper()([sys.executable, '-c', 'raise SystemExit(7)'], stream, 5, {})
        self.assertEqual(result.returncode, 7)

    def test_timeout_stops_detached_writer_before_manifest_sealing(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            marker = folder / 'writer.json'
            evidence = folder / 'events.log'
            writer = (
                'from pathlib import Path; import os,json,time; '
                f'Path({str(marker)!r}).write_text(json.dumps(dict(pid=os.getpid()))); '
                f'out=open({str(evidence)!r},"a",buffering=1); '
                'exec("for n in range(1000):\\n out.write(str(n)+chr(10)); time.sleep(.01)")'
            )
            parent = (
                'import subprocess,sys,time; '
                f'subprocess.Popen([sys.executable,"-c",{writer!r}],start_new_session={os.name == "posix"!r}); '
                'time.sleep(30)'
            )
            cleanup = {}
            with open(os.devnull, 'w') as stream:
                with self.assertRaises(subprocess.TimeoutExpired):
                    actual_helper()([sys.executable, '-c', parent], stream, 2, cleanup)
            self.assertTrue(marker.is_file(), 'Timeout must exercise an actual writer')
            self.assertGreater(evidence.stat().st_size, 0)
            self.assertTrue(cleanup['timeout_triggered'])
            self.assertGreaterEqual(cleanup['descendant_count'], 1)
            self.assertTrue(cleanup['timeout_cleanup_complete'], cleanup)
            self.assertEqual(cleanup['active_after_count'], 0)
            pid = json.loads(marker.read_text())['pid']
            self.assertFalse(psutil.pid_exists(pid), 'No detached writer may survive timeout')
            sealed = sha256(evidence.read_bytes()).hexdigest()
            time.sleep(.15)
            self.assertEqual(sha256(evidence.read_bytes()).hexdigest(), sealed)

    def test_ci_budget_and_resource_contract_remain_bounded(self):
        source = WORKFLOW.read_text()
        self.assertIn('    timeout-minutes: 160\n', source)
        self.assertIn('        timeout-minutes: 152\n', source)
        self.assertIn('stream, timeout=9000, cleanup=process_cleanup', source)
        self.assertLess(9000, 152 * 60, 'Runner cleanup fits inside step budget')
        self.assertLess(152, 160, 'Job retains bounded setup/artifact time')
        self.assertIn('[sys.executable, "-m", "tools.validation.validate_release"]', source)
        self.assertIn('--memory 2g --memory-swap 2g --cpus 2 --network none', source)
        product = WORKFLOW.with_name('product-browser.yml').read_text()
        # This is the complete-corpus orchestration allowance, not an
        # application/search timeout or a responsiveness performance threshold.
        # Run43327175874 exhausted the old25-minute batch before completion.
        # Check the actual owning blocks; a matching comment/other job cannot
        # satisfy the contract. Preserve10minutes for other steps/cleanup.
        job = re.search(r'(?ms)^  product-browser:\n(.*?)(?=^  [\w-]+:\n|\Z)', product)
        self.assertIsNotNone(job)
        job_minutes = int(re.search(r'(?m)^    timeout-minutes: (\d+)$', job[1])[1])
        batch = job[1].split('      - name: Authenticated product, interaction and accessibility contracts\n', 1)[1].split('\n      - ', 1)[0]
        batch_minutes = int(re.search(r'(?m)^        timeout-minutes: (\d+)$', batch)[1])
        self.assertEqual(job_minutes, 45)
        self.assertEqual(batch_minutes, 35)
        self.assertLess(batch_minutes, job_minutes)
        self.assertEqual(job_minutes - batch_minutes, 10)
        self.assertIn('python -m unittest', batch)
        self.assertIn('--memory=2g --memory-swap=2g --cpus=2 --network=none', batch)


if __name__ == '__main__':
    unittest.main()
