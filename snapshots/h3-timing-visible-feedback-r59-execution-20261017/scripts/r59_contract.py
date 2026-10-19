"""Exact frozen R59 graphs, four registered arms, fifteen executable jobs."""
import copy
import shutil
from pathlib import Path
from execution_contract import ROOT, SOURCES, ARMS, read, sha, require, safe, verify_candidate

REMOTE = Path('/data3/researcher/h3_runs/timing_visible_feedback_r59_execution_20261017')
ORIGINAL_REMOTE = '/data3/researcher/h3_runs/timing_visible_feedback_r59_20261017'
PARENT_FIELDS = {'parent_status', 'parent_root', 'parent_conditioning', 'parent_noise',
                 'parent_captures', 'parent_file_inventory', 'parent_graph', 'parent_graph_sha256'}


def cases(root=ROOT):
    root = Path(root)
    prepared = read(root / 'candidate/configs/protocol.json')['cases']
    rows = read(root / 'configs/protocol.json')['cases']
    require(len(rows) == len(prepared) == 20, 'fixed four-arm case set differs')
    require([(row['source_id'], row['arm']) for row in rows] == [(source, arm) for source in SOURCES for arm in ARMS], 'case order differs')
    for actual, planned in zip(rows, prepared):
        require(set(actual) - set(planned) <= PARENT_FIELDS, 'unregistered case field')
        require({key: value for key, value in actual.items() if key not in PARENT_FIELDS} == {key: value for key, value in planned.items() if key not in PARENT_FIELDS}, 'candidate scientific case changed')
    return rows


def executable_cases(root=ROOT):
    return [case for case in cases(root) if case['arm'] != 'native']


def derive_graph(case, root=ROOT):
    """Only task-owned absolute audit paths change from the sealed candidate."""
    graph = copy.deepcopy(read(Path(root) / 'candidate/configs/graphs' / (case['run_id'] + '.json')))
    for node, field in (('5', 'audit_dir'), ('6', 'audit_dir'), ('50', 'audit_dir'), ('51', 'source_audit_dir'), ('52', 'output_dir')):
        value = graph[node]['inputs'][field]
        require(value.startswith(ORIGINAL_REMOTE + '/'), 'candidate graph administrative path differs')
        graph[node]['inputs'][field] = str(REMOTE) + value[len(ORIGINAL_REMOTE):]
    return graph


def registry(root=ROOT):
    root = Path(root)
    rows = executable_cases(root)
    names = [case['run_id'] for case in rows]
    queue = read(root / 'configs/queue.json')
    require(set(queue) == {'jobs', 'finalize'} and queue['jobs'] == names and type(queue['finalize']) is bool, 'fixed15 queue differs')
    require(read(root / 'configs/scientific_contract.json')['case_order'] == names, 'scientific execution order differs')
    return {case['run_id']: {'source_id': case['source_id'], 'seed': case['seed'], 'arm': case['arm'],
                            'case': case, 'graph_sha256': sha(root / 'configs/graphs' / (case['run_id'] + '.json'))}
            for case in rows}, names


def audit_dir(value):
    path = Path(value)
    require(path.is_absolute() and not path.is_symlink() and path.resolve() == REMOTE / 'audit', 'audit root outside isolated R59 execution')
    return path.resolve()


audit_root = audit_dir


def validate_job(run, root=ROOT, inputs=True):
    root = Path(root)
    found = [case for case in executable_cases(root) if case['run_id'] == run]
    require(len(found) == 1, 'unknown executable arm/run; Native is reused from R57')
    case = found[0]
    path = safe(root, 'configs/graphs/' + run + '.json')
    require(read(path) == derive_graph(case, root), 'graph differs from sealed candidate plus root relocation')
    require(case['prompt'] == (root / case['prompt_file']).read_text() and sha(root / case['prompt_file']) == case['prompt_sha256'], 'P1 prompt changed')
    require(case['reference_image_count'] == 0 and case['reference_video_count'] == 1, 'reference inventory changed')
    if inputs:
        require(case['parent_status'] == 'READY', 'actual R57 parent pending')
        require(sha(root / case['parent_graph']) == case['parent_graph_sha256'] == case['parent_planned_graph_sha256'], 'actual parent graph differs')
        require(read(root / case['parent_graph']) == read(root / case['parent_planned_graph']), 'actual P1 graph differs')
        for key in ('video', 'provenance'):
            require(sha(safe(root / 'inputs', case[key])) == case[key + '_sha256'], 'actual source input differs')
    return {'case': case, 'graph_sha256': sha(path)}


def prepare_loader_inputs(run, root=ROOT):
    root = Path(root)
    result = validate_job(run, root)
    case = result['case']
    folder = root / 'input'
    folder.mkdir(exist_ok=True)
    source, destination = root / 'inputs' / case['video'], safe(folder, case['video'])
    if not destination.exists():
        with source.open('rb') as before, destination.open('xb') as after:
            shutil.copyfileobj(before, after)
    require(sha(destination) == case['video_sha256'], 'loader input changed')
    return result
