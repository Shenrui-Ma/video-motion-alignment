"""Summarize actual sequential tracker resource receipts without rerunning scoring."""
from pathlib import Path
import argparse, hashlib, json

def read(path):
    return json.loads(Path(path).read_text())

def main(root):
    root = Path(root).resolve()
    actual = root / 'actual_host41'
    result = read(root / 'RESULT_VERIFIED.json')
    assert read(result['release']['file'])['passed']
    summary = {}
    for method in ('reference', 'native', 'guided'):
        report = read(actual / 'tracks' / method / 'REPORT.json')
        audit = actual / 'audit/actual_tracking_capacity4' / method
        observations = read(audit / 'RESOURCE_OBSERVATIONS.json')
        oom = read(audit / 'OOM_DELTA.json')['paths']
        assert report['passed'] and observations['returncode'] == 0
        parent = [row for sample in observations['samples'] for row in sample.get('cgroup', {}).get('ancestors', [])
                  if row['path'] == '/user.slice']
        assert parent
        usage = [read(path) for path in (actual / 'controls').rglob('PROCESS_USAGE.json')
                 if read(path)['pid'] == report['pid']]
        assert len(usage) == 1
        events = {key: {name: value['events_delta'].get(name, 0) for name in ('oom', 'oom_kill', 'oom_group_kill')}
                  for key, value in oom.items()}
        assert all(not value['counter_reset_detected'] for value in oom.values())
        assert not any(value for row in events.values() for value in row.values())
        summary[method] = {
            'maxrss_GiB': usage[0]['maxrss_kib'] / 1024**2,
            'tracking_s': report['tracking_seconds'], 'wall_s': report['wall_seconds'],
            'GPU_allocated_GiB': report['peak_allocated_bytes'] / 1024**3,
            'GPU_reserved_GiB': report['peak_reserved_bytes'] / 1024**3,
            'parent_PSI_some_avg10_range': [min(row['pressure']['some']['avg10'] for row in parent),
                                           max(row['pressure']['some']['avg10'] for row in parent)],
            'minimum_raw_high_GiB': min(row['headroom_bytes']['high'] for row in parent) / 1024**3,
            'minimum_raw_max_GiB': min(row['headroom_bytes']['max'] for row in parent) / 1024**3,
            'OOM_deltas': events,
        }
    path = root / 'RESOURCE_SUMMARY.json'
    assert not path.exists(), 'preserve previous resource summary'
    path.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'resources': summary}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pair_root')
    main(parser.parse_args().pair_root)
