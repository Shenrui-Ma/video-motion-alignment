"""CPU-only scheduling adapter; frozen consumer implementations retain arithmetic."""
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {'verify_pair', 'collect_pair', 'prepare_pair', 'score_one', 'summarize', 'make_triptych', 'make_checkpoints'}


def main():
    phase, *args = sys.argv[1:]
    if phase not in ALLOWED:
        raise ValueError('CPU phase outside allowlist')
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    sys.path.insert(0, str(ROOT / 'scripts'))
    if phase == 'verify_pair':
        target = Path('/data3/researcher/h3_runs/timing_flexiact_expanded_r66_20261018/analysis/postrun/verify_pair.py')
        sys.path.insert(0, str(target.parent))
    elif phase == 'make_checkpoints':
        target = Path(__file__).with_name('make_checkpoints.py')
    elif phase == 'make_triptych':
        target = Path(__file__).with_name('make_triptych_ffmpeg4.py')
    else:
        target = ROOT / 'scripts' / (phase + '.py')
    sys.argv = [str(target), *args]
    try:
        if phase in ('verify_pair', 'make_checkpoints'):
            from common import cpu_lock
            with cpu_lock():
                runpy.run_path(str(target), run_name='__main__')
        else:
            runpy.run_path(str(target), run_name='__main__')
    except BlockingIOError:
        print('SHARED_CPU_LOCK_BUSY', flush=True)
        return 75
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
