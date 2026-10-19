"""One bounded CPU phase. Real scoring requires a later root authorization file."""
import os
for _key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '4'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import argparse
import contextlib
import fcntl
import hashlib
import json
from pathlib import Path
import signal
import sys
import time
import unittest
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
DESIGN = ROOT.parent/'source_anchor_selection_design'
LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
sys.path.insert(0, str(ROOT/'vendor'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


@contextlib.contextmanager
def cpu_lock():
    if not LOCK.is_file():
        raise ValueError('Shared CPU lock missing; verify resource policy before execution')
    with LOCK.open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(75)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def timeout(_signum, _frame):
    raise TimeoutError('Bounded phase time limit reached')


def verify_record(record):
    p = Path(record['path'])
    if not p.is_file():
        raise ValueError(f'Bound input missing: {p}')
    if 'bytes' in record and p.stat().st_size != record['bytes']:
        raise ValueError(f'Bound input size mismatch: {p}')
    if sha(p) != record['sha256']:
        raise ValueError(f'Bound input SHA mismatch: {p}')
    return p


def verify_design():
    binding = read(ROOT/'DESIGN_BINDING.json')
    for name, record in binding['files'].items():
        verify_record(dict(record, path=str(DESIGN/name)))
    for name, record in read(DESIGN/'FREEZE.json')['files'].items():
        verify_record(dict(record, path=str(DESIGN/name)))
    for name, record in read(ROOT/'VENDOR_BINDING.json').items():
        verify_record(dict(record, path=str(ROOT/'vendor'/name)))
    return binding


def verify_execution():
    f = ROOT/'FREEZE.json'
    frozen = read(f)
    for name, record in frozen['files'].items():
        verify_record(dict(record, path=str(ROOT/name)))
    return sha(f)


def authorization(path, action, source_id, run_id=None, index=None):
    if path is None:
        raise ValueError('Root must explicitly authorize real numerical execution after review')
    a = read(path)
    if a.get('approved') is not True or a.get('authorizer') != 'root':
        raise ValueError('Numerical authorization must be approved by root')
    if a.get('execution_freeze_sha256') != verify_execution():
        raise ValueError('Execution authorization freeze mismatch')
    if a.get('design_freeze_sha256') != sha(DESIGN/'FREEZE.json'):
        raise ValueError('Authorization design mismatch')
    if source_id not in a.get('source_ids', []):
        raise ValueError('Source is outside numerical authorization')
    if action not in a.get('actions', []):
        raise ValueError('Phase is outside numerical authorization')
    if run_id is not None and run_id not in a.get('run_ids', []):
        raise ValueError('Target run is outside numerical authorization')
    if index is not None and index not in a.get('endpoint_indices', []):
        raise ValueError('Target index is outside numerical authorization')
    return {'authorization_path': str(Path(path).resolve()), 'authorization_sha256': sha(path)}


def pose_schema(path):
    """Only format, identity/timebase, and shape checks; no feature computation."""
    raw = read(path)
    video = raw['video']
    expected = (24, 1312, 736, 141)
    actual = tuple(video[k] for k in ('fps', 'width', 'height', 'container_frame_count'))
    if actual != expected:
        raise ValueError(f'Pose geometry/timebase mismatch: {path}: {actual}')
    rows = raw['frames']
    if len(rows) != 141 or [r['frame'] for r in rows] != list(range(141)):
        raise ValueError('Pose frame index mismatch')
    for i, row in enumerate(rows):
        if abs(row['time_s']-i/24) > 1e-8:
            raise ValueError('Pose physical time mismatch')
        selected = row['selected_person']
        if selected is not None:
            if type(selected) is not int or not 0 <= selected < len(row['persons']):
                raise ValueError('Invalid selected_person index')
            person = row['persons'][selected]
            if len(person['coco17_xy']) != 17 or any(len(x) != 2 for x in person['coco17_xy']) or len(person['coco17_score']) != 17:
                raise ValueError('Malformed COCO17 arrays')
    return {'path': str(path), 'frame_count': 141, 'timebase_valid': True, 'shape_valid': True}


def source_binding(source_id):
    return next(x for x in read(DESIGN/'SOURCE_BINDING.json')['sources'] if x['source_id'] == source_id)


def source_paths(binding):
    paths = {'identity': verify_record(binding['identity_pose'])}
    for view in binding.get('views', []):
        if view['view'] == 'identity':
            continue
        if not view.get('local_verified') or 'local_pose' not in view:
            raise ValueError('Source views pending; migration numerical phase is unavailable')
        paths[view['view']] = verify_record(view['local_pose'])
        complete = read(verify_record(view['local_complete']))
        verify_record(view['local_validated_manifest'])
        if complete['status'] != 'complete' or complete['inverse_pose_sha256'] != view['pose_sha256'] or complete['identity_pose_sha256'] != binding['identity_pose']['sha256']:
            raise ValueError('Source transformed-view completion mismatch')
    if set(paths) != {'identity', 'flip', 'pad16'}:
        raise ValueError('Source requires identity, flip, and pad16 inverse pose')
    for path in paths.values():
        pose_schema(path)
    return paths


def check_metadata():
    t = time.monotonic()
    verify_design()
    report = {'status': 'passed', 'scope': 'format and hash only; no numerical pose features or source/target scores',
              'sources': [], 'targets': [], 'runtime': sys.version}
    for source in read(DESIGN/'SOURCE_BINDING.json')['sources']:
        row = {'source_id': source['source_id'], 'identity': pose_schema(verify_record(source['identity_pose']))}
        if source['source_id'] == 'source05':
            row['three_views'] = {k: pose_schema(p) for k, p in source_paths(source).items()}
        else:
            row['transformed_views'] = 'pending binding; target numerical use blocked'
        report['sources'].append(row)
    count = 0
    for run in read(DESIGN/'TARGET_BINDING.json')['targets']:
        if [x['index'] for x in run['endpoints']] != list(range(20)):
            raise ValueError('Target binding requires 20 ordered endpoints')
        for key in ('run_gate', 'file_inventory', 'download_record'):
            verify_record(run[key])
        for ep in run['endpoints']:
            for file in ep['files'].values():
                verify_record(file)
                count += 1
            pose_schema(ep['files']['native.pose.json']['path'])
        report['targets'].append({'run_id': run['run_id'], 'endpoints': 20, 'bound_files': 100})
    report.update(target_files_verified=count, elapsed_seconds=time.monotonic()-t)
    return report


def load_features(paths):
    import timing_metrics as m
    loaded, errors = {}, []
    for name, path in paths.items():
        for c in (.3, .5):
            try:
                loaded[name, c] = m.load_pose(path, c)
            except ValueError as e:
                if str(e) != 'Insufficient reliable torso anchors for scale normalization':
                    raise
                errors.append({'input': name, 'confidence': c, 'reason': str(e)})
    return loaded, errors


def source_phase(source_id, approval):
    from anchor_selection import run_source, candidates, select
    from timing_metrics import clean
    phase_start = time.monotonic()
    record = source_binding(source_id)
    paths = source_paths(record)
    output = ROOT/'results'/source_id/'SOURCE_SELECTION.json'
    if output.exists():
        raise ValueError('Source result already exists; immutable phase cannot overwrite')
    feature_start = time.monotonic()
    loaded, errors = load_features(paths)
    feature_seconds = time.monotonic()-feature_start
    if errors:
        rows = [dict(r, Q=0., V=0., r=0., source_status='source_unobservable',
                     rejection_reasons=errors, motion={'value': None}) for r in candidates()]
        result = {'candidates': rows, 'selection': select(rows, record['identity_pose']['sha256']),
                  'source_errors': errors, 'source_scan_seconds': 0., 'source_pair_distance_slots': 0}
    else:
        result = run_source(loaded, record['identity_pose']['sha256'])
    preprocessing = {}
    for v in record['views']:
        if v['view'] != 'identity':
            comp = read(v['local_complete']['path'])
            preprocessing[v['view']] = {'pose_elapsed_seconds': comp['elapsed_seconds'],
                                       'complete_sha256': v['local_complete']['sha256']}
    result.update(source_id=source_id, design_freeze_sha256=sha(DESIGN/'FREEZE.json'),
                  execution_freeze_sha256=verify_execution(), approval=approval,
                  pose_inputs={k: {'path': str(p), 'sha256': sha(p)} for k, p in paths.items()},
                  source_transformed_pose_preprocessing_cost=preprocessing,
                  feature_load_seconds=feature_seconds,
                  phase_seconds_before_output_serialization=time.monotonic()-phase_start,
                  target_numeric_opened=False, created_unix=time.time(),
                  interpretation='Post-hoc observer-position diagnostic; source relative margin does not predict generation risk',
                  independent_labels=False, actuator_S=None)
    write_new(output, clean(result))
    receipt = {'status': 'complete', 'source_id': source_id, 'result': str(output),
               'sha256': sha(output), 'execution_freeze_sha256': verify_execution(),
               'target_numeric_opened': False, 'created_unix': time.time(),
               'phase_seconds_including_selection_serialization': time.monotonic()-phase_start}
    write_new(output.with_name('SOURCE_COMPLETE.json'), receipt)
    return receipt


def completed_source(source_id):
    directory = ROOT/'results'/source_id
    receipt = read(directory/'SOURCE_COMPLETE.json')
    if receipt['status'] != 'complete' or receipt['execution_freeze_sha256'] != verify_execution():
        raise ValueError('Completed source selection is not bound to current execution')
    p = verify_record({'path': str(directory/'SOURCE_SELECTION.json'), 'sha256': receipt['sha256']})
    result = read(p)
    if result['design_freeze_sha256'] != sha(DESIGN/'FREEZE.json') or result['target_numeric_opened'] is not False:
        raise ValueError('Source selection provenance mismatch')
    return result, receipt


def endpoint_phase(source_id, run_id, index, approval):
    from anchor_selection import candidates
    from target_diagnostic import observe, unknown_observation, compare_coverage
    phase_start = time.monotonic()
    selection, receipt = completed_source(source_id)  # Before target numeric access.
    source = source_binding(source_id)
    source_paths(source)
    run = next(x for x in read(DESIGN/'TARGET_BINDING.json')['targets'] if x['run_id'] == run_id)
    if run['source_id'] != source_id:
        raise ValueError('Target belongs to another source')
    ep = next(x for x in run['endpoints'] if x['index'] == index)
    out = ROOT/'results'/source_id/run_id/f'endpoint_{index:03d}.json'
    if out.exists():
        raise ValueError('Target result already exists; immutable phase cannot overwrite')
    target_path = verify_record(ep['files']['native.pose.json'])
    for record in ep['files'].values():
        verify_record(record)
    pose_schema(target_path)
    feature_start = time.monotonic()
    loaded, errors = load_features({'source': source['identity_pose']['path'], 'target': target_path})
    feature_seconds = time.monotonic()-feature_start
    methods = {'source_margin': selection['selection']['source_margin'], **selection['selection']['baselines']}
    descriptions = {name: method['rows'] for name, method in methods.items()}
    descriptions['full279'] = candidates()
    # 186 has identical old descriptors; measured independently to record cost.
    descriptions['historical186'] = candidates(lengths=(16, 32))
    result = {'schema': 'source-anchor-endpoint-v1', 'source_id': source_id, 'run_id': run_id,
              'index': index, 'source_selection_sha256': receipt['sha256'], 'approval': approval,
              'target_pose_sha256': ep['files']['native.pose.json']['sha256'], 'methods': {},
              'history_limit': run['history_limit'], 'target_errors': errors,
              'common_feature_load_seconds': feature_seconds,
              'strict_comparison_eligible': selection['selection']['strict_comparison_eligible'],
              'label': 'UNKNOWN', 'created_unix': time.time()}
    start = time.monotonic()
    for name, descriptors in descriptions.items():
        if errors:
            report = unknown_observation(descriptors, errors)
        else:
            report = observe({c: loaded['source', c] for c in (.3, .5)},
                             {c: loaded['target', c] for c in (.3, .5)}, descriptors)
        report['budget'] = methods[name]['budget'] if name in methods else {'K': len(descriptors)}
        report['baseline_feasible'] = methods[name]['feasible'] if name in methods else True
        result['methods'][name] = report
    for name, report in result['methods'].items():
        report['relative_full279'] = compare_coverage(report['summary'], result['methods']['full279']['summary'])
        report['relative_historical186'] = compare_coverage(report['summary'], result['methods']['historical186']['summary'])
    result['elapsed_seconds'] = time.monotonic()-start
    result['phase_seconds_before_output_serialization'] = time.monotonic()-phase_start
    result['common_VAE_pose_cost_saved'] = False
    write_new(out, result)
    return {'status': 'complete', 'result': str(out), 'sha256': sha(out), 'index': index,
            'elapsed_seconds': result['elapsed_seconds'],
            'phase_seconds_including_result_serialization': time.monotonic()-phase_start}


def finalize(source_id, run_id, approval):
    from target_diagnostic import trajectory_summary
    selection, receipt = completed_source(source_id)
    run = next(x for x in read(DESIGN/'TARGET_BINDING.json')['targets'] if x['run_id'] == run_id)
    if run['source_id'] != source_id:
        raise ValueError('Target belongs to another source')
    directory = ROOT/'results'/source_id/run_id
    endpoints = [read(directory/f'endpoint_{i:03d}.json') for i in range(20)]
    if any(x['source_selection_sha256'] != receipt['sha256'] or x['run_id'] != run_id or x['index'] != i
           or x['target_pose_sha256'] != run['endpoints'][i]['files']['native.pose.json']['sha256']
           for i, x in enumerate(endpoints)):
        raise ValueError('Mixed target provenance')
    result = {'status': 'complete', 'run_id': run_id, 'approval': approval,
              'source_selection_sha256': receipt['sha256'], 'endpoint_denominator': 20,
              'strict_comparison_eligible': selection['selection']['strict_comparison_eligible'],
              'methods': {name: trajectory_summary(endpoints, name) for name in endpoints[0]['methods']},
              'endpoint_result_hashes': {f'endpoint_{i:03d}.json': sha(directory/f'endpoint_{i:03d}.json') for i in range(20)},
              'created_unix': time.time(), 'independent_accuracy': None, 'actuator_S': None}
    if not result['strict_comparison_eligible']:
        result['comparison_status'] = 'indeterminate_no_matched_five_method_comparison'
    else:
        result['comparison_status'] = 'conditional_observer_position_evidence_only'
    write_new(directory/'TRAJECTORY_SUMMARY.json', result)
    return {'status': 'complete', 'result': str(directory/'TRAJECTORY_SUMMARY.json'),
            'sha256': sha(directory/'TRAJECTORY_SUMMARY.json')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=('check', 'self-test', 'source', 'endpoint', 'finalize'))
    p.add_argument('--source-id', default='source05')
    p.add_argument('--run-id')
    p.add_argument('--index', type=int)
    p.add_argument('--authorization')
    p.add_argument('--report')
    a = p.parse_args()
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm({'check': 180, 'self-test': 180, 'source': 1800, 'endpoint': 900, 'finalize': 180}[a.phase])
    with cpu_lock():
        if a.phase == 'self-test':
            suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'))
            t = time.monotonic()
            r = unittest.TextTestRunner(verbosity=2).run(suite)
            result = {'status': 'passed' if r.wasSuccessful() else 'failed', 'tests': r.testsRun,
                      'errors': len(r.errors), 'failures': len(r.failures), 'elapsed_seconds': time.monotonic()-t,
                      'scope': 'synthetic only; no real numerical scoring', 'python': sys.executable,
                      'tested_python_files': {str(x.relative_to(ROOT)): sha(x) for x in sorted(ROOT.rglob('*.py'))
                                              if '__pycache__' not in x.parts}}
            if a.report:
                write_new(a.report, result)
            print(json.dumps(result))
            return 0 if r.wasSuccessful() else 1
        verify_design()
        if a.phase == 'check':
            result = check_metadata()
        else:
            if a.phase in ('endpoint', 'finalize') and not a.run_id:
                p.error('--run-id required')
            if a.phase == 'endpoint' and (a.index is None or not 0 <= a.index < 20):
                p.error('--index 0..19 required')
            approval = authorization(a.authorization, a.phase, a.source_id, a.run_id, a.index)
            if a.phase == 'source':
                result = source_phase(a.source_id, approval)
            elif a.phase == 'endpoint':
                result = endpoint_phase(a.source_id, a.run_id, a.index, approval)
            else:
                result = finalize(a.source_id, a.run_id, approval)
        if a.report:
            write_new(a.report, result)
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
