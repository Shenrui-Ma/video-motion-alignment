"""Administrative NVML sampling for one exact service; never starts CUDA."""
import json
import math
import threading
import time


def sample_owner(owner, identity, processes, now=time.time):
    row = {'unix': now(), 'pid': owner['pid'], 'gpu_uuid': owner['gpu_uuid']}
    try:
        actual = identity(owner['pid'])
        if actual is None:
            return dict(row, status='process_absent')
        if actual != owner['identity']:
            return dict(row, status='identity_changed')
        matches = [r for r in processes() if r['pid'] == owner['pid']]
        if any(r['gpu_uuid'] != owner['gpu_uuid'] for r in matches) or len(matches) > 1:
            raise ValueError('own PID appeared on unexpected or duplicate GPU')
        value = 0.0 if not matches else float(matches[0]['used_memory_mib'])
        if not math.isfinite(value) or value < 0:
            raise ValueError('invalid own residency')
        return dict(row, status='observed', own_memory_mib=value,
                    allocation_present=bool(matches))
    except Exception as error:
        return dict(row, status='unknown', error=repr(error))


def summarize(owner, rows):
    observed = [r['own_memory_mib'] for r in rows if r['status'] == 'observed']
    return {'schema': 'r89-own-pid-memory-summary-v1', 'pid': owner['pid'],
            'identity': owner['identity'], 'gpu_uuid': owner['gpu_uuid'],
            'samples': len(rows), 'valid_samples': len(observed),
            'unknown_samples': sum(r['status'] == 'unknown' for r in rows),
            'max_observed_own_memory_mib': max(observed) if observed else None,
            'metric_scope': 'Exact service PID NVML residency sampled at nominal 5s intervals; probe latency can extend them; maximum observed value, not continuous allocator peak or whole-card used memory.',
            'true_allocator_peak_measured': False}


class OwnMemorySampler:
    def __init__(self, owner, audit, service, interval=5):
        self.owner, self.audit, self.service = owner, audit, service
        self.interval, self.rows = interval, []
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._loop, daemon=True, name='r89-own-memory')

    def start(self):
        self.thread.start()

    def _loop(self):
        while not self.stop_event.is_set():
            row = sample_owner(self.owner, self.service.current_identity, self.service.compute_processes)
            with self.lock:
                self.rows.append(row)
            try:
                with (self.audit/'OWN_GPU_MEMORY.jsonl').open('a') as handle:
                    handle.write(json.dumps(row)+'\n')
            except Exception:
                # Administrative recording failure cannot terminate the numerical job.
                pass
            if row['status'] in ('process_absent', 'identity_changed'):
                return
            self.stop_event.wait(self.interval)

    def snapshot(self, name):
        with self.lock:
            value = summarize(self.owner, list(self.rows))
        self.service.write_json(self.audit/name, value)
        return value

    def finish(self):
        self.stop_event.set()
        self.thread.join(timeout=15)
        value = self.snapshot('OWN_GPU_MEMORY_SUMMARY.json')
        value['sampler_thread_exited'] = not self.thread.is_alive()
        self.service.write_json(self.audit/'OWN_GPU_MEMORY_SUMMARY.json', value)

