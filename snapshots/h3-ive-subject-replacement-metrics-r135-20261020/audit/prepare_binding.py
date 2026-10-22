"""Create only variant manifests and links to existing consumer/media code."""
from pathlib import Path
import argparse, ast, hashlib, json, os, re, time

BASE = Path('/Users/researcher/DevProjects')
OLD = BASE / 'h3-ive-scrubs-color-metrics-r134-20261020'
SHARED = BASE / 'h3-ive-subject-replacement-metrics-r135-20261020/scripts'

def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), str(path)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def link(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, target)
    assert sha(source) == sha(target)

def main():
    parser = argparse.ArgumentParser()
    for key in ('producer', 'consumer', 'namespace', 'source', 'seal', 'description'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    producer, root = Path(args.producer), Path(args.consumer)
    assert re.fullmatch(r'r[0-9]+', args.namespace)
    assert sha(producer / 'deploy_manifest.json') == args.seal
    assert not (root / 'CONSUMER_FREEZE.json').exists()
    science = read(producer / 'configs/scientific_contract.json')
    assert science['source_ids'] == [args.source] and len(science['cases']) == 2
    native = next(row for row in science['cases'] if row['arm'] == 'native')
    forced = next(row for row in science['cases'] if row['arm'] == 'forced')
    assert native['prompt'] == forced['prompt']
    assert native['prompt_version'] == 'IVEBench-edit-with-generic-retention-v1'
    root.joinpath('scripts').mkdir(parents=True, exist_ok=True)
    modules = {}
    for shim in (OLD / 'scripts').glob('*.py'):
        text = shim.read_text()
        path = Path(re.search(r"_shared=_Path\('([^']+)'\)", text).group(1))
        digest = re.search(r"hexdigest\(\)=='([0-9a-f]{64})'", text).group(1)
        assert sha(path) == digest
        modules[shim.stem] = {'file': str(path), 'sha256': digest}
        target = root / 'scripts' / shim.name
        content = 'from pathlib import Path\nfrom _shared import load\nload(Path(__file__).stem, globals())\n'
        if root / 'scripts' == SHARED:
            assert not target.exists()
            target.write_text(content)
        else:
            link(SHARED / shim.name, target)
    if root / 'scripts' != SHARED:
        link(SHARED / '_shared.py', root / 'scripts/_shared.py')
    contract = read(OLD / 'configs/contract.json')
    row = contract['sources'][0]
    for key in ('source_id', 'run_id', 'geometry', 'prompt_version', 'prompt', 'original_task', 'clip', 'task_scope', 'evaluation_scope'):
        row[key] = native[key]
    row.update(forced_run_id=forced['run_id'], valid_frames=native['valid_frame_count'],
               crop_xywh=native['evaluation_crop_xywh'], expected_prompt_sha256=native['prompt_sha256'])
    for key, name in [('source', native['video']), ('provenance', native['provenance'])]:
        source = producer / 'inputs' / name; target = root / 'inputs' / name
        link(source, target)
        row[key] = {'file': str(target.relative_to(root)), 'sha256': sha(target), 'bytes': target.stat().st_size}
    source = Path(native['original_source']['file']); target = root / 'inputs' / (args.source + '_original.mp4')
    link(source, target)
    assert sha(target) == native['original_source']['sha256']
    row['original_media'] = {'file': str(target), 'sha256': sha(target)}
    for arm, case in [('native', native), ('forced', forced)]:
        source = producer / 'configs/graphs' / (case['run_id'] + '.json'); target = root / 'configs/graphs' / source.name
        link(source, target)
        row['graph_sha256' if arm == 'native' else 'forced_graph_sha256'] = sha(target)
    for name, source in [('producer_runtime.json', producer / 'configs/runtime.json'),
                         ('producer_scientific_contract.json', producer / 'configs/scientific_contract.json'),
                         ('SOURCE_EVENT_REVIEW_CUES.json', producer / 'design/REFERENCE_EVENT_REVIEW_PLAN.json'),
                         ('SOURCE_EVENTS_BEFORE_OUTPUT.json', producer / 'audit/SOURCE_EVENTS_BEFORE_OUTPUT.json')]:
        link(source, root / 'configs' / name)
    runtime = read(producer / 'configs/runtime.json')
    contract.update(namespace=args.namespace, schema=args.namespace + '-native-paired-media-consumer-v1',
                    producer_local=str(producer), producer_remote=runtime['remote_root'], host=runtime['host'],
                    producer_seal_sha256=args.seal, producer_contract_sha256=sha(producer / 'configs/scientific_contract.json'),
                    producer_runtime_sha256=sha(producer / 'configs/runtime.json'), source_order=[args.source],
                    fixed_source_denominator=1, display_description=args.description)
    save(root / 'configs/contract.json', contract)
    save(root / 'configs/SHARED_CODE.json', {'modules': modules, 'consumer_base': str(OLD),
         'consumer_base_freeze_sha256': sha(OLD / 'CONSUMER_FREEZE.json'),
         'adaptations': ['manifest namespace, source, exact prompt, input domain and task description only'],
         'GPU_entry': False, 'automatic_submission': False})
    files = {str(path.relative_to(root)): sha(path) for sub in ['scripts', 'configs', 'inputs']
             for path in (root / sub).rglob('*') if path.is_file() and '__pycache__' not in path.parts}
    for path in (root / 'scripts').glob('*.py'): ast.parse(path.read_text())
    save(root / 'CONSUMER_FREEZE.json', {'schema': 'shared-consumer-variant-manifest-v1', 'files': files,
         'producer_seal_sha256': args.seal, 'GPU_entry': False, 'created_unix': time.time()})
    print(json.dumps({'freeze_sha256': sha(root / 'CONSUMER_FREEZE.json'), 'files': len(files)}))

if __name__ == '__main__': main()
