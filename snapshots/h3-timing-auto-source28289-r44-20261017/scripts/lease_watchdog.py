"""Bound the lifetime of the exact task service, including a disconnected client."""
import json
import time

import service


if __name__ == '__main__':
    record = json.loads((service.RUN / 'processes/service.json').read_text())
    deadline = time.monotonic() + 43200
    while time.monotonic() < deadline:
        actual = service.current_identity(record['pid'])
        if actual is None or actual != record['identity']:
            break
        time.sleep(20)
    else:
        current = json.loads((service.RUN / 'processes/service.json').read_text())
        if current['pid'] == record['pid'] and current['identity'] == record['identity']:
            service.assert_owned(record)
            service.stop(expected_record=record)
