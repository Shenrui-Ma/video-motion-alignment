"""Read-only verification of completed numeric outputs, then exclusive manifest."""
from pathlib import Path
import hashlib
import json
import fcntl
import sys
import time

P = Path(__file__).resolve().parents[1]
LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


with LOCK.open('a') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('CPU lock busy')
        sys.exit(75)
    original = json.loads((P/'FREEZE.json').read_text())
    for name, record in original['files'].items():
        assert sha(P/name) == record['sha256']
    summary = json.loads((P/'audit/TARGET_RESULT_SUMMARY.json').read_text())
    paths = []
    for run in summary['runs']:
        directory = P/'results/source05'/run
        final = json.loads((directory/'TRAJECTORY_SUMMARY.json').read_text())
        assert len(final['endpoint_result_hashes']) == 20
        for name, h in final['endpoint_result_hashes'].items():
            assert sha(directory/name) == h
        paths.extend(sorted(directory.glob('*.json')))
    paths.extend([Path(__file__), P/'audit/TARGET_RESULT_SUMMARY.json', P/'audit/ALL_QUALIFIED_DELAY_ROWS.json'])
    for pattern in ('bad_endpoint*', 'normal_endpoint*', 'bad_finalize*', 'normal_finalize*'):
        paths.extend(sorted((P/'audit').glob(pattern)))
    records = {str(q.relative_to(P)): {'sha256': sha(q), 'bytes': q.stat().st_size}
               for q in sorted(set(paths)) if q.is_file()}
    freeze = {'status': '40_endpoints_two_finalizations_complete', 'files': records,
              'original_execution_freeze_sha256': sha(P/'FREEZE.json'),
              'original_23_sealed_files_reverified': True,
              'source_selection_sha256': '3b64976dcf8173d58dc1aaa4f18f1a1c281791eeedf512b960c0f816a1083b8b',
              'root_target_authorization_sha256': sha(P/'ROOT_TARGET_AUTHORIZATION.json'),
              'endpoint_hashes_reverified': 40, 'CPU_only': True, 'GPU_calls': 0,
              'protocol_changed': False, 'independent_accuracy': None, 'unix': time.time()}
    with (P/'audit/TARGET_RESULT_FREEZE.json').open('x') as f:
        json.dump(freeze, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({'files': len(records), 'freeze_sha256': sha(P/'audit/TARGET_RESULT_FREEZE.json'),
                      'summary_sha256': sha(P/'audit/TARGET_RESULT_SUMMARY.json'),
                      'bad_final_sha256': sha(P/'results/source05/r27_s05_bad1311_auto/TRAJECTORY_SUMMARY.json'),
                      'normal_final_sha256': sha(P/'results/source05/r27_s05_normal1313_auto/TRAJECTORY_SUMMARY.json')}))
