"""Offline queue candidate validation; localhost mock server only."""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

here = Path(__file__).resolve().parent
execution = here.parents[2]
original = execution / 'inference/package/queue/durable_comfy_queue.py'
candidate = here / 'durable_comfy_queue.after.py'
base_tests = execution / 'queue/test_durable_comfy_queue.py'

with tempfile.TemporaryDirectory(prefix='h3-job-attempt-limit-') as tmp:
    target = Path(tmp)
    shutil.copyfile(candidate, target / 'durable_comfy_queue.py')
    shutil.copyfile(base_tests, target / 'test_durable_comfy_queue_base.py')
    shutil.copyfile(here / 'test_durable_job_attempts.py', target / 'test_durable_job_attempts.py')
    proc = subprocess.run([sys.executable, '-m', 'unittest', 'test_durable_job_attempts', '-v'],
                          cwd=target, text=True, capture_output=True)
    text = proc.stdout + proc.stderr
    print(text)
    evidence = {'timestamp': datetime.datetime.now().astimezone().isoformat(),
                'status': 'PASS' if proc.returncode == 0 else 'FAIL',
                'exit_code': proc.returncode,
                'interpreter': sys.executable,
                'network': 'localhost mock HTTP server only; no remote hosts',
                'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
                'base_tests_sha256': hashlib.sha256(base_tests.read_bytes()).hexdigest(),
                'output': text}
    (here / 'queue_attempt_limit_test_result.json').write_text(json.dumps(evidence, indent=2) + '\n')
    raise SystemExit(proc.returncode)
