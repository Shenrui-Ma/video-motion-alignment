"""Administrative idle exemption for an exact, bounded Native review request."""
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review_wait(root, owner, now_wall, now_mono, memory, lookup):
    root = Path(root)
    request_path = root / 'audit/NATIVE_VISUAL_REVIEW_REQUEST.json'
    if not request_path.exists():
        return {'active': False, 'reason': 'no_review_request'}
    try:
        request = read(request_path)
        assert request['schema'] == 'r150-native-visual-review-request-v1'
        created = float(request['created_unix'])
        timeout = float(request['timeout_seconds'])
        assert math.isfinite(created) and math.isfinite(timeout)
        assert timeout == 600 and owner['started_unix'] <= created <= now_wall
        assert 0 <= now_wall - created < timeout
        assert read(root / 'processes/service.json') == owner
        assert lookup(owner['pid']) == owner['identity']
        contract = read(root / 'configs/scientific_contract.json')
        assert contract['condition_recovery']['requires_shared_cache_native'] is True
        rows = [row for row in contract['cases'] if row['run_id'] == request['run_id']]
        assert len(rows) == 1 and rows[0]['arm'] == 'native'
        spec = rows[0]
        assert request['source_id'] == spec['source_id']
        gate_path = root / 'analysis/postrun' / spec['source_id'] / (spec['run_id'] + '_GATE.json')
        assert request['native_gate'] == str(gate_path)
        assert request['review_file'] == str(root / 'audit/NATIVE_VISUAL_REVIEW.json')
        assert request['native_gate_sha256'] == sha(gate_path)
        gate = read(gate_path)
        assert gate['schema'] == 'r149-schedule-job-gate-v1' and gate['passed'] is True
        assert gate['run_id'] == spec['run_id'] and gate['role'] == 'native'
        assert gate['service_owner'] == owner
        assert request['video_sha256'] == gate['video']['sha256']
        assert request['video'] == gate['video']['file']
        assert request['producer_seal_sha256'] == gate['producer_seal_sha256'] == sha(root / 'deploy_manifest.json')
        controller = read(root / 'processes/controller.json')
        assert controller['role'] == 'controller'
        assert controller['service_pid'] == owner['pid'] and controller['service_identity'] == owner['identity']
        assert lookup(controller['pid']) == controller['identity']
        state = read(root / 'logs/controller_state.json')
        assert state['status'] == 'waiting_native_visual_review' and state['current'] is None
        assert state['completed'] == [spec['run_id']]
        digest = sha(request_path)
        if 'request_sha256' not in memory:
            memory.update(request_sha256=digest, deadline_monotonic=now_mono + timeout - (now_wall-created))
        assert memory['request_sha256'] == digest  # A rewrite cannot renew the lease.
        assert now_mono < memory['deadline_monotonic']
        return {'active': True, 'request_sha256': digest, 'run_id': spec['run_id'],
                'expires_unix': created + timeout, 'deadline_monotonic': memory['deadline_monotonic']}
    except (AssertionError, KeyError, TypeError, ValueError, OSError) as error:
        return {'active': False, 'reason': 'review_binding_or_deadline_invalid', 'error': repr(error)}


def exempt_idle(reason, review):
    return None if reason == 'bounded_idle_review_expired' and review['active'] else reason
