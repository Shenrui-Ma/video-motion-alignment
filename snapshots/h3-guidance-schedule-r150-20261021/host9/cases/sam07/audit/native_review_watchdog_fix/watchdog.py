"""Run the sealed lease guard with only its valid Native-review idle exemption."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import lease_watchdog as original
import service
from review_wait import review_wait, exempt_idle, sha


def main():
    owner = original.read(ROOT / 'processes/service.json')
    service.assert_owned(owner)
    original.HERE = Path(__file__).resolve().parent / 'runtime'
    original.HERE.mkdir(exist_ok=True)
    memory = {}
    previous_update = original.update_reason
    previous_save = original.save_best_effort
    review = {'active': False, 'reason': 'not_observed'}

    def update(state, now, queue, limits, known_job=None):
        nonlocal review
        reason = previous_update(state, now, queue, limits, known_job)
        review = review_wait(ROOT, owner, time.time(), now, memory, service.current_identity)
        return exempt_idle(reason, review)

    def save(name, value):
        if name == 'STATE.json':
            value = dict(value, native_review=review)
        previous_save(name, value)
        if name == 'STATE.json' and not (original.HERE / 'READY.json').exists():
            service.write_json(original.HERE / 'READY.json', {
                'passed': True, 'pid': os.getpid(), 'identity': service.identity(os.getpid()),
                'owner': owner, 'sealed_lease_sha256': sha(ROOT / 'scripts/lease_watchdog.py'),
                'observed_unix': time.time(), 'first_state': value})

    original.update_reason = update
    original.save_best_effort = save
    original.main()


if __name__ == '__main__':
    main()
