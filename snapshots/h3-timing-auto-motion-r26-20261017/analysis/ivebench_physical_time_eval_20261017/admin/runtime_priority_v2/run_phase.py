"""Keep the frozen evaluator and give pending production observers CPU priority."""
import argparse
import json
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
FROZEN_ROOT = HERE.parent.parent
EXPECTED_FREEZE = '6e14dbf25ed28567848396f01eb70827ad0476570c542c44f3b757485a5ca794'


def pending_observer(root):
    return any(
        (request.parent / 'native.mp4').exists()
        and not (request.parent / 'response.json').exists()
        and not (request.parent / 'failure.json').exists()
        for request in (Path(root) / 'audit/observations').glob('step*/request.json')
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['pose', 'pair', 'manifest'])
    args, remainder = parser.parse_known_args()
    sys.path.insert(0, str(FROZEN_ROOT))
    import pose90
    pose90.require(pose90.sha(FROZEN_ROOT / 'FREEZE.json') == EXPECTED_FREEZE,
                   'original evaluator freeze differs')
    pose90.frozen()
    # Only the scheduling predicate changes; all data validation and arithmetic
    # execute from the previously frozen modules and retain their receipts.
    pose90.online_pending = lambda: pending_observer(pose90.AUTO)
    target = FROZEN_ROOT / {'pose': 'pose90.py', 'pair': 'run_pair.py', 'manifest': 'manifest.py'}[args.phase]
    sys.argv = [str(target)] + remainder
    if args.phase == 'pose':
        return pose90.main()
    runpy.run_path(str(target), run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
