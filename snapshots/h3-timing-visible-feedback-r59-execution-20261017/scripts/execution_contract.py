"""Read-only contracts for the R59 migration; this module never starts a process."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SHA = '9656edfb57c8bfcd205869f7cd510bfcab4b811d52177fc045c4fa3e7b63bb13'
SOURCES = ('short_0210', 'short_0230', 'short_0263', 'short_0352', 'short_0370')
ARMS = ('native', 'visible_only', 'visible_fallback', 'weak_only')
PARENT_PRODUCER = Path('/data3/researcher/h3_runs/timing_ivebench_prompt_adaptation_r57_20261017')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def safe(root, relative):
    root, relative = Path(root), Path(relative)
    require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe relative path')
    path = root / relative
    require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), 'symlink/outside path')
    return path


def file_record(path):
    path = Path(path)
    return {'bytes': path.stat().st_size, 'sha256': sha(path)}


def checked_file(root, relative, inventory):
    require(relative in inventory, 'missing inventory entry: ' + relative)
    path = safe(root, relative)
    require(path.is_file() and file_record(path) == inventory[relative], 'changed archived file: ' + relative)
    return path


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')


def verify_candidate(root=ROOT):
    root = Path(root)
    candidate = root / 'candidate'
    require(sha(candidate / 'PREPARATION_MANIFEST.json') == CANDIDATE_SHA, 'candidate seal differs')
    manifest = read(candidate / 'PREPARATION_MANIFEST.json')
    for relative, record in manifest['files'].items():
        checked_file(candidate, relative, {relative: record})
    protocol = read(candidate / 'configs/protocol.json')
    cases = protocol['cases']
    expected = [(source, arm) for source in SOURCES for arm in ARMS]
    require([(row['source_id'], row['arm']) for row in cases] == expected, 'fixed four-arm registry differs')
    require(protocol['steps'] == 20 and protocol['weak']['alpha'] == .25 and protocol['weak']['indices'] == list(range(6, 15)), 'frozen schedule differs')
    plan = read(root / 'configs/EXECUTION_PLAN.json')
    require(plan['candidate_manifest_sha256'] == CANDIDATE_SHA, 'execution candidate binding differs')
    require([job['run_id'] for job in plan['jobs']] == [row['run_id'] for row in cases if row['arm'] != 'native'], '15-run execution registry differs')
    return protocol


def verify_parent_anchors(archive, expected_manifest_sha, runs):
    archive = Path(archive)
    require(isinstance(expected_manifest_sha, str) and re.fullmatch('[0-9a-f]{64}', expected_manifest_sha), 'actual root-verified R57 deployment SHA is required')
    for name in ('RUN_GATE.json', 'RUNTIME_GATE.json', 'FILE_INVENTORY.json', 'deploy_manifest.json'):
        require(safe(archive, name).is_file(), 'actual completed R57 archive pending: ' + name)
    require(sha(archive / 'deploy_manifest.json') == expected_manifest_sha, 'actual R57 deployment anchor differs')
    gate = read(archive / 'RUN_GATE.json')
    runtime = read(archive / 'RUNTIME_GATE.json')
    inventory = read(archive / 'FILE_INVENTORY.json')
    require(gate.get('passed') is True and gate.get('run_id') == 'batch' and gate.get('runs') == runs, 'fixed-five parent gate failed')
    require(gate.get('file_inventory_sha256') == sha(archive / 'FILE_INVENTORY.json') and gate.get('runtime_gate_sha256') == sha(archive / 'RUNTIME_GATE.json'), 'parent archive anchors changed')
    require(runtime.get('passed') is True and bool(runtime.get('checks')) and all(value is True for value in runtime['checks'].values()), 'parent runtime validation failed')
    require(set(runtime['runs']) == set(runs), 'parent runtime run set differs')
    for relative, expected in read(archive / 'deploy_manifest.json')['files'].items():
        path = checked_file(archive, relative, inventory)
        require(file_record(path) == {key: expected[key] for key in ('bytes', 'sha256')}, 'parent deployed code/config differs: ' + relative)
    for run in runs:
        require(all(runtime['checks'].get(run + '_actual_' + key) is True for key in ('reference_equal_P0', 'initial_AV_noise_equal_P0')), 'actual reference/noise pairing to P0 missing')
        counts = runtime['runs'][run]
        require(counts['NFE'] == counts['Euler_updates'] == counts['callback_count'] == 20, 'parent Euler/forward count differs')
    return gate, runtime, inventory


def readiness(root=ROOT):
    """Report actual preflight readiness; pending parent/resources remain blocked."""
    root = Path(root)
    verify_candidate(root)
    plan = read(root / 'configs/EXECUTION_PLAN.json')
    pending = list(plan['pending_gates'])
    binding = root / 'prepared_parent/PARENT_BINDING.json'
    if binding.is_file():
        record = read(binding)
        require(record['candidate_manifest_sha256'] == CANDIDATE_SHA and record['status'] == 'ACTUAL_PARENT_BYTES_VERIFIED', 'parent intake receipt differs')
        for relative, expected in record['materialized_files'].items():
            checked_file(root / 'prepared_parent', relative, {relative: expected})
        pending.remove('actual_R57_parent_archive')
    from preflight import check
    try:
        check(root, live=True)
    except (ValueError, FileNotFoundError) as error:
        return {'status': 'BLOCKED', 'GPU_launch_authorized': False, 'pending_gates': pending,
                'first_blocker': str(error), 'launch_implementation_status': plan['launch_implementation_status'],
                'candidate_science_verified': True, 'jobs_pending': len(plan['jobs'])}
    return {'status': 'READY_FOR_ROOT_CONTROLLED_LAUNCH', 'GPU_launch_authorized': 'root-only exact process gate',
            'pending_gates': ['root_exact_service_generation'], 'jobs_pending': len(plan['jobs'])}
