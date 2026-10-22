"""Sequential Native-cache reachability, stops at first frozen Controller ON."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time
from precheck_support import (ROOT, Controller, admission, approved, assert_released,
                              config, geometry, lifetime, measurement, read, require,
                              sha, stop_after, validate_package, write, apps,
                              validate_own_processes)


def run(attempt):
    require(attempt.startswith('host41_precheck_') and attempt.replace('_', '').isalnum(), 'safe attempt name')
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    review = approved(); value = validate_package(external=True)
    directory = ROOT / 'audit' / attempt
    directory.mkdir(exist_ok=False)
    parent = lifetime.identity(os.getpid())
    require(parent is not None and parent['uid'] == 1004, 'exact parent identity')
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGINT, interrupted)
    start = time.monotonic()
    result = dict(schema='r133-native-prefix-observer-reachability-v1', status='running',
                  attempt=attempt, identity=parent, parent_run=value['run_id'], seed=value['seed'],
                  freeze_sha256=sha(ROOT / 'FREEZE.json'), root_review_sha256=sha(ROOT / 'audit/ROOT_REVIEW.json'),
                  first_ON_index=None, steps=[], started_unix=time.time(), DiT_forward_calls=0,
                  interpretation='Native-cache reachability before the first intervention; later closed-loop trajectory untested')
    write(directory / 'STARTED.json', result)
    controller = Controller(geometry(value), arm='visible_only')
    child_records = []
    try:
        result['admission'] = admission(value)
        for index in value['indices']:
            require(time.monotonic() - start < value['max_total_seconds'], 'bounded precheck lifetime')
            step = directory / f'step{index:03d}'; step.mkdir()
            request = dict(index=index, snapshot=value['snapshots'][index], seed=value['seed'],
                           parent_run=value['run_id'], freeze_sha256=result['freeze_sha256'])
            write(step / 'request.json', request)
            common = ['--parent-json', json.dumps(parent)]
            command = [sys.executable, str(ROOT / 'scripts/decode_one.py'), '--index', str(index),
                       '--output', str(step / 'native.mp4')] + common
            decode = lifetime.run_child(command, dict(os.environ, CUDA_VISIBLE_DEVICES=''), step, 'decoder', value['max_decode_seconds'], parent)
            child_records.append(decode['process'])
            write(step / 'DECODER_RELEASED.json', assert_released(decode['process']))
            # This child starts only after the VAE process and its allocation end.
            command = [sys.executable, str(ROOT / 'scripts/pose_one.py'), '--index', str(index), '--directory', str(step)] + common
            pose = lifetime.run_child(command, dict(os.environ, CUDA_VISIBLE_DEVICES=''), step, 'pose', value['max_pose_seconds'], parent)
            child_records.append(pose['process'])
            require(read(step / 'pose_complete.json')['status'] == 'complete', 'pose measurement incomplete')
            observed = read(step / 'observer.json')
            evidence = measurement(index, observed, sha(step / 'request.json'), sha(step / 'observer.json'))
            decision = controller.select(index, evidence)
            write(step / 'DECISION.json', decision)
            row = dict(index=index, decision=decision, observer_sha256=sha(step / 'observer.json'),
                       decoded_sha256=sha(step / 'native.mp4'), decode_wall_seconds=decode['wall_seconds'],
                       pose_wall_seconds=pose['wall_seconds'])
            result['steps'].append(row)
            write(directory / 'RESULT.json', result)
            print(json.dumps(dict(index=index, chosen_full=decision['chosen_full'], reliable_rows=decision['reliable_rows'],
                                  candidate_groups=decision['candidate_groups'], intervals=decision['physical_intervals'])), flush=True)
            if stop_after(decision):
                result['first_ON_index'] = index
                break
        result['status'] = 'complete'
        result['outcome'] = 'first_ON_reached' if result['first_ON_index'] is not None else 'no_ON_in_first_ten'
    except BaseException as error:
        result.update(status='failed', error=repr(error))
        raise
    finally:
        result.update(finished_unix=time.time(), wall_seconds=time.monotonic() - start)
        write(directory / 'RESULT.json', result)
        # run_child owns exact cleanup, including its exception paths.
        identities = [read(p) for p in sorted(directory.glob('step*/*.process.json'))]
        receipts = [assert_released({k: row[k] for k in ('pid', 'uid', 'start_ticks', 'cmdline_sha256')}) for row in identities]
        remaining = apps(); validate_own_processes(remaining, value['runtime'])
        write(directory / 'CHILDREN_RELEASED.json', dict(passed=True, children=receipts,
              fresh_task_cuda_absent=True, preserved_user_service=value['runtime']['preserved_user_service']))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    if args.validate_only:
        value = validate_package(external=True)
        import torch
        require(not torch.cuda.is_initialized(), 'CPU-only validation')
        print(json.dumps(dict(passed=True, snapshot_files=10, CUDA_initialized=False,
                              freeze_sha256=sha(ROOT / 'FREEZE.json'))))
    else:
        require(args.attempt is not None, 'attempt required')
        run(args.attempt)


if __name__ == '__main__':
    main()
