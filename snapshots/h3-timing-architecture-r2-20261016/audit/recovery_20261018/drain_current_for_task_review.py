"""Finish the admitted GPU job, then hold a task-incompatible queue for review."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    sys.path.insert(0, str(root / 'scripts'))
    import service
    import job

    owner = read(root / 'processes/service.json')
    controller = read(root / 'processes/controller.json')
    service.assert_owned(owner)
    assert service.current_identity(controller['pid']) == controller['identity']
    assert controller['service_pid'] == owner['pid']
    assert controller['service_identity'] == owner['identity']
    audit = root / 'audit/task_scope_review_hold_20261018'
    audit.mkdir(exist_ok=False)
    service.write_json(audit / 'PRIOR.json', {
        'owner': owner, 'controller': controller,
        'queue': read(root / 'configs/queue.json'),
        'state': read(root / 'logs/controller_state.json'),
        'reason': 'User requires source-scene-preserving subject/element edits; this queued task explicitly inherits target-image scene. Finish current job and review task before further sampling.',
        'unix': time.time()})
    paused = False
    accepted = False
    try:
        assert service.current_identity(controller['pid']) == controller['identity']
        os.kill(controller['pid'], signal.SIGSTOP)
        paused = True
        queue = service.queue_at(service.PORT)
        assert len(queue['queue_running']) == 1 and not queue['queue_pending'], queue
        prompt_id = queue['queue_running'][0][1]
        candidates = [(p, read(p)) for p in (root / 'logs').glob('*_job.json')]
        matches = [(p, row) for p, row in candidates if row.get('prompt_id') == prompt_id]
        assert len(matches) == 1, (prompt_id, len(matches))
        path, row = matches[0]
        name = path.name.removesuffix('_job.json')
        service.write_json(audit / 'DRAINING.json', {
            'run': name, 'prompt_id': prompt_id, 'controller_paused': controller,
            'service_keeps_current_inference': owner, 'unix': time.time()})
        accepted = True
        print(json.dumps({'draining': name, 'service_pid': owner['pid'],
                          'controller_pid': controller['pid']}), flush=True)
        deadline = time.monotonic() + 4 * 3600
        while True:
            result = job.status(name)
            status = result.get('status') or 'running'
            status = status['status_str'] if isinstance(status, dict) else status
            service.write_json(audit / 'STATUS.json', {'run': name, 'status': status, 'unix': time.time()})
            if status == 'success':
                history = read(root / 'logs' / f'{name}_history.json')
                assert history['status']['completed'] is True
                assert history['status']['status_str'] == 'success'
                break
            if status in ('error', 'unknown_missing', 'submission_uncertain'):
                raise RuntimeError((name, status))
            assert time.monotonic() < deadline
            time.sleep(10)
        queue = service.queue_at(service.PORT)
        assert not queue['queue_running'] and not queue['queue_pending']
        cleanup = service.stop(expected_record=owner)
        assert service.current_identity(controller['pid']) == controller['identity']
        os.kill(controller['pid'], signal.SIGTERM)
        os.kill(controller['pid'], signal.SIGCONT)
        assert service.wait_absent(controller['pid'], 30)
        paused = False
        completed = []
        for run in read(root / 'configs/queue.json')['jobs']:
            path = root / 'logs' / f'{run}_history.json'
            if path.exists() and read(path)['status']['completed'] is True and read(path)['status']['status_str'] == 'success':
                completed.append(run)
        service.write_json(root / 'logs/controller_state.json', {
            'status': 'task_scope_review_hold', 'completed': completed, 'current': None,
            'unix': time.time(), 'administrative_hold': str(audit)})
        service.write_json(audit / 'COMPLETE.json', {
            'current_job_completed': name, 'completed': completed, 'cleanup': cleanup,
            'controller_absent': True, 'scientific_queue_preserved': True, 'unix': time.time()})
    except BaseException as error:
        cleanup_errors = []
        try:
            service.write_json(audit / 'FAILURE.json', {'error': repr(error), 'accepted': accepted, 'unix': time.time()})
        except BaseException as write_error:
            cleanup_errors.append(repr(write_error))
        if not accepted and paused and service.current_identity(controller['pid']) == controller['identity']:
            os.kill(controller['pid'], signal.SIGCONT)
        elif accepted:
            try:
                service.stop(expected_record=owner)
            except BaseException as cleanup_exception:
                cleanup_errors.append(repr(cleanup_exception))
            try:
                if service.current_identity(controller['pid']) == controller['identity']:
                    os.kill(controller['pid'], signal.SIGTERM)
                    os.kill(controller['pid'], signal.SIGCONT)
                    assert service.wait_absent(controller['pid'], 30)
            except BaseException as cleanup_exception:
                cleanup_errors.append(repr(cleanup_exception))
        try:
            service.write_json(audit / 'FAILURE_CLEANUP.json', {'errors': cleanup_errors, 'unix': time.time()})
        except BaseException:
            pass
        raise


if __name__ == '__main__':
    main()
