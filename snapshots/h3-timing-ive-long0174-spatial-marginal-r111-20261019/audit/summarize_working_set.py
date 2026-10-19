"""Read observed session memory; retain the same cache allowance as admission."""
import hashlib
import json
from pathlib import Path
import time

root = Path(__file__).resolve().parents[1]
resource = root / 'logs/resources.jsonl'
rows = []
for line in resource.read_text().splitlines():
    value = json.loads(line)
    snapshot = value.get('cgroup', {}).get('snapshot', {})
    for ancestor in snapshot.get('ancestors', []):
        if '/session-' not in ancestor['path']:
            continue
        stat = ancestor['stat']
        clean = max(0, stat.get('file', 0) - sum(stat.get(k, 0) for k in
                    ('shmem', 'file_mapped', 'file_dirty', 'file_writeback')))
        credited = max(0, clean - 6 * 1024 ** 3)
        rows.append({
            'observed_unix': snapshot['observed_unix'], 'path': ancestor['path'],
            'current_bytes': ancestor['current_bytes'], 'anon_bytes': stat['anon'],
            'file_bytes': stat['file'], 'file_mapped_bytes': stat.get('file_mapped', 0),
            'clean_unmapped_file_bytes': clean, 'credited_file_bytes': credited,
            'adjusted_current_bytes': ancestor['current_bytes'] - credited,
        })
assert rows
result = {
    'created_unix': time.time(), 'samples': len(rows),
    'resource_log': {'file': str(resource), 'sha256': hashlib.sha256(resource.read_bytes()).hexdigest()},
    'retained_file_cache_bytes': 6 * 1024 ** 3,
    'maximum_sampled_adjusted_session': max(rows, key=lambda x: x['adjusted_current_bytes']),
    'maximum_sampled_anon_session': max(rows, key=lambda x: x['anon_bytes']),
    'scope': 'Sampled R111 service session. Mapped file pages remain charged; peak between 20-second samples is unknown. This observation does not change admission or establish R103 peak.',
}
dest = root / 'audit/ACTUAL_WORKING_SET_REVIEW.json'
with dest.open('x') as handle:
    json.dump(result, handle, indent=2)
    handle.write('\n')
print(json.dumps({'file': str(dest), 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest(),
                  'sampled_peak_adjusted_gib': result['maximum_sampled_adjusted_session']['adjusted_current_bytes'] / 1024 ** 3}))
