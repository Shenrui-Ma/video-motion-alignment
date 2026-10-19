"""Keep minimal downloads and frozen proofs with current observer priority."""
from pathlib import Path
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import minimal_download
import run_incremental_case
base = minimal_download.base


def remote(args):
    command = ['env', 'TMPDIR=' + base.P['root_remote'] + '/temp', 'CUDA_VISIBLE_DEVICES=',
               'PYTHONDONTWRITEBYTECODE=1', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1',
               base.PYTHON, base.REMOTE + '/audit/priority_v2/remote_entry.py', '--entry', 'incremental', *args]
    result = subprocess.run(base.SSH + [base.HOST, shlex.join(command)], capture_output=True, text=True, timeout=900)
    (HERE / ('remote_' + str(time.time_ns()) + '.log')).write_text(result.stdout + '\nSTDERR\n' + result.stderr)
    return result


run_incremental_case.remote = remote
minimal_download.main()
