"""Bound the lifetime of the exact task service, including a disconnected client."""
import json
import time

import service
import startup_barrier as barrier
from primary_lifecycle import observe_primary


if __name__ == '__main__':
    record = json.loads((service.RUN / 'processes/service.json').read_text())
    gate = barrier.read_json(service.RUN / 'processes/pre_cuda_gate.json')
    deadline = time.monotonic() + 9 * 3600
    while time.monotonic() < deadline:
        actual = service.current_identity(record['pid'])
        if actual is None or actual != record['identity']:
            break
        try:
            barrier.verify_live(gate['coordinator'])
            observe_primary(gate['primary'], gate['primary_registry'], gate['primary_root'])
        except (RuntimeError, OSError, ValueError, KeyError):
            service.assert_owned(record)
            service.stop()
            break
        time.sleep(5)
    else:
        current = json.loads((service.RUN / 'processes/service.json').read_text())
        if current['pid'] == record['pid'] and current['identity'] == record['identity']:
            service.assert_owned(record)
            service.stop()
