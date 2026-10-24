"""CPU-only preflight binding of a fresh lane's a1 audit to queue progress_file."""
import json
from pathlib import Path


def validate_progress_bindings(root):
    root = Path(root).resolve()
    cfg = json.loads((root / 'CONFIG.json').read_text())
    if str(root) != cfg['root'] or str(root.parent) != cfg['allowed_root']:
        raise ValueError('Progress binding root differs from CONFIG')
    checked = []
    for arm in cfg['arms']:
        manifest = json.loads((root / 'manifests' / (arm + '.json')).read_text())
        job_id = 'interval_short_0177_' + arm
        attempt = job_id + '__a1'
        if len(manifest['jobs']) != 1 or manifest['jobs'][0]['id'] != job_id:
            raise ValueError('Progress binding requires one expected job per manifest')
        job = manifest['jobs'][0]
        expected = root / 'audit' / 'router' / (attempt + '.json')
        if job.get('progress_file') != str(expected):
            raise ValueError('progress_file must bind this lane and its sole a1 attempt')
        if expected.is_symlink() or expected.resolve() != expected or expected.exists():
            raise ValueError('Progress audit must be a fresh lane-local path without symlink')
        metadata = job['metadata']
        if metadata.get('cohort') != 'interval_short0177_20261024' or metadata.get('method') != arm:
            raise ValueError('Progress binding cohort/method mismatch')
        if metadata['route_audit'].replace('{attempt_id}', attempt) != str(expected):
            raise ValueError('Progress file differs from result router binding')
        timing = root / 'audit' / 'timing' / (attempt + '.json')
        if metadata['timing_file'].replace('{attempt_id}', attempt) != str(timing):
            raise ValueError('Timing binding points to another lane or attempt')
        graph_path = root / 'graphs' / (job_id + '.json')
        if job['graph'] != str(graph_path):
            raise ValueError('Graph binding points to another lane')
        graph = json.loads(graph_path.read_text())
        graph = graph.get('prompt', graph)
        routers = [n['inputs'] for n in graph.values() if n.get('class_type') == 'H3StudySchedule']
        timers = [n['inputs'] for n in graph.values() if n.get('class_type') == 'H3StudyTiming']
        if len(routers) != 1 or len(timers) != 1:
            raise ValueError('Expected one router and one timing node')
        if routers[0]['audit_dir'] != str(expected.parent) or routers[0]['run_id'] != '{attempt_id}' or routers[0]['schedule'] != arm:
            raise ValueError('Graph router does not write the bound attempt audit')
        if timers[0]['output_dir'] != str(timing.parent) or timers[0]['run_id'] != '{attempt_id}':
            raise ValueError('Graph timing does not write the bound attempt audit')
        checked.append({'arm': arm, 'job_id': job_id, 'attempt_id': attempt, 'progress_file': str(expected)})
    return {'passed': True, 'fresh_attempts': checked, 'router_write_semantics': 'Initialization, each completed 50-block forward, or error; no periodic heartbeat'}
