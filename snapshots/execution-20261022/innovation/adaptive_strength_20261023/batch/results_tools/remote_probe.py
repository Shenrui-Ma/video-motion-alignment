"""Read-only JSON probe. Executed via SSH stdin; never creates remote files."""
import hashlib
import json
from pathlib import Path
import sys
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path, known):
    path = Path(path)
    if not path.is_file():
        return {'path': str(path), 'status': 'missing'}
    stat = path.stat()
    version = [stat.st_mtime_ns, stat.st_size]
    out = {'path': str(path), 'version': version, 'mtime_unix': stat.st_mtime,
           'bytes': stat.st_size}
    if known.get(str(path)) == version:
        return dict(out, status='unchanged')
    raw = path.read_bytes()
    try:
        return dict(out, status='read', sha256=hashlib.sha256(raw).hexdigest(),
                    data=json.loads(raw))
    except ValueError as error:
        return dict(out, status='unreadable', error=str(error))


def inference(request):
    root = Path(request['run_root'])
    known = request.get('known', {})
    manifest_path = root / request.get('manifest', 'jobs.json')
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {'jobs': []}
    by_id = {j['id']: j for j in manifest['jobs']}
    state_path = root / 'queue_state/state.json'
    state = json.loads(state_path.read_text()).get('jobs', {}) if state_path.is_file() else {}
    rows = []
    for planned in request['jobs']:
        job_id = planned['id']
        actual = by_id.get(job_id)
        meta = (actual or planned).get('metadata', {})
        job_state = state.get(job_id, {})
        result_path = root / 'queue_state/results' / (job_id + '.json')
        result = read_json(result_path, known)
        result_doc = json.loads(result_path.read_text()) if result_path.is_file() else {}
        attempt = result_doc.get('attempt_id') or job_state.get('attempt_id')
        if attempt is None and job_state.get('attempts', 0) > 0:
            attempt = job_id + '__a' + str(job_state['attempts'])
        actual_meta = result_doc.get('metadata') or meta
        # Resolve by actual producer root, not canonical source-host metadata.
        method = actual_meta.get('method', planned.get('metadata', {}).get('method'))
        audit_kind = {'coverage_blend25': 'coverage_blend',
                      'dynamic_anchor': 'feature_anchor'}.get(method, 'feature_guidance')
        row = {'job_id': job_id, 'registered': actual is not None,
               'queue_state': job_state, 'actual_attempt_id': attempt,
               'method': method, 'result': result,
               'graph': read_json(root / (actual or planned)['graph'], known),
               'artifact_status': 'pending', 'media': []}
        if attempt:
            row['audit'] = read_json(root / 'audit' / audit_kind / (attempt + '.json'), known)
            row['timing'] = read_json(root / 'audit/timing' / (attempt + '.json'), known)
        for media in result_doc.get('files', []):
            path = Path(media['path'])
            item = {'path': str(path), 'recorded_sha256': media.get('sha256')}
            if not path.is_file():
                item['status'] = 'missing'
            else:
                stat = path.stat()
                version = [stat.st_mtime_ns, stat.st_size]
                prior = request.get('known_media', {}).get(str(path), {})
                sha = prior.get('actual_sha256') if prior.get('version') == version else digest(path)
                item.update(version=version, bytes=stat.st_size, actual_sha256=sha,
                            status='verified' if sha == item['recorded_sha256'] else 'sha_mismatch')
            row['media'].append(item)
        rows.append(row)
    return {'fetched_at_unix': time.time(), 'run_root': str(root),
            'manifest_path': str(manifest_path), 'manifest_sha256': digest(manifest_path) if manifest_path.exists() else None,
            'jobs': rows}


def metrics(request):
    root = Path(request['metrics_root'])
    paths = {'manifest': root / 'code/manifest.json', 'evaluation': root / 'evaluation/summary.json'}
    out = {'fetched_at_unix': time.time(), 'sources': {}}
    for name, path in paths.items():
        artifact = read_json(path, {})
        if artifact['status'] != 'read':
            out[name] = {'jobs': []} if name == 'manifest' else {'rows': []}
        else:
            data = artifact.pop('data')
            key = 'jobs' if name == 'manifest' else 'rows'
            data[key] = [r for r in data.get(key, []) if
                r.get('task_id') in request['tasks'] and
                (r.get('method') in ('source', 'native', 'global_weak') or
                 r.get('job_id', r.get('id')) in request['job_ids'])]
            out[name] = {key: data[key]}
        out['sources'][name] = artifact
    return out


if __name__ == '__main__':
    request = json.load(sys.stdin)
    result = (metrics if request.get('kind') == 'metrics' else inference)(request)
    json.dump(result, sys.stdout, allow_nan=False)
