"""Bind R141 facts to existing R123 consumer helpers; no GPU entry."""
from pathlib import Path
from fractions import Fraction
import ast
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020')
PRODUCER = Path('/Users/researcher/DevProjects/h3-timing-oxygen-generic-retention-r141-20261020')
SEAL = '2d038d50dbdac335788223d8e5f1925cdbb90e730ed673edd0649cad3af91f5d'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, data):
    assert not p.exists(), p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.link(src, dst)


assert not (ROOT / 'CONSUMER_FREEZE.json').exists()
assert sha(PRODUCER / 'deploy_manifest.json') == SEAL
science = json.loads((PRODUCER / 'configs/scientific_contract.json').read_text())
runtime = json.loads((PRODUCER / 'configs/runtime.json').read_text())
n, f = [next(c for c in science['cases'] if c['arm'] == arm) for arm in ('native', 'forced')]
assert n['source_id'] == f['source_id'] == 'short_0252'
assert n['prompt'] == f['prompt'] and n['seed'] == f['seed'] == 2026101703
shared = {}
for src in sorted((BASE / 'scripts').glob('*.py')):
    if src.name.startswith('test_'):
        continue
    shared[src.stem] = {'file': str(src), 'sha256': sha(src)}
    code = f'''"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path({str(src)!r})
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == {sha(src)!r}
'''
    if src.stem in ('render_native', 'render_pair'):
        old = 'R123复核饮酒男子加眼镜。提示词保留官方 edit_prompt 原句，前面加入任务类型与参考视频标识。'
        new = 'R141复核老人替换任务。使用官方编辑原句、参考视频绑定和通用保留要求；同源 seed1703，不增加独立来源。'
        code += f'_text = _data.decode()\nassert _text.count({old!r}) == 1\n_text = _text.replace({old!r}, {new!r}).replace("R123", "R141")\n'
        code += 'exec(compile(_text, str(_shared), "exec"), globals())\n'
    else:
        if src.stem in ('consume_native', 'consume_pair'):
            code += f'import sys as _sys\nif __name__ == "__main__" and "--output" not in _sys.argv:\n _sys.argv += ["--output", {str(ROOT / "showcase" / (src.stem + ".html"))!r}]\n'
        code += 'exec(compile(_data, str(_shared), "exec"), globals())\n'
    if src.stem == 'common':
        code += '''
SOURCES = ('short_0252',)
GENERIC_RETENTION = "\\n\\nretention_analysis:\\n<Video 1>: Preserve the source video's people, scene, framing, camera motion, and actions, except for changes explicitly requested in the summary."
def verify_official_prompt(p, graph=None):
    expected = TASK_ENVELOPE + p['original_task']['edit_prompt'] + GENERIC_RETENTION
    require(p['prompt_version'] == 'official_edit_prompt_with_task_reference_and_generic_retention', 'prompt version differs')
    require(p['prompt'] == expected, 'official instruction or generic envelope changed')
    if graph is not None:
        require(graph['5']['inputs']['prompt'] == expected, 'actual graph prompt differs')
REQUIRED_CHECKS = tuple('native_registered_initial_noise_equal' if k == 'native_r121_initial_noise_equal' else k for k in REQUIRED_CHECKS)
'''
    ast.parse(code)
    dest = ROOT / 'scripts' / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(code)

for name in (n['video'], n['provenance'], n['original_source']):
    link(PRODUCER / 'inputs' / name, ROOT / 'inputs' / name)
provenance = json.loads((ROOT / 'inputs' / n['provenance']).read_text())
original_count = len(provenance['original_pts'])
assert original_count == 102 and provenance['effective_frame_count'] == 98
assert all(abs(t - i / 25) < 1e-8 for i, t in enumerate(provenance['original_pts']))
source = dict(source_id=n['source_id'], run_id=n['run_id'], forced_run_id=f['run_id'],
              geometry=science['geometry'], prompt=n['prompt'], prompt_version=n['prompt_version'],
              original_task=n['original_task'], task_scope=n['task_scope'], evaluation_scope=n['evaluation_scope'],
              valid_frames=98, crop_xywh=n['evaluation_crop_xywh'], reference_image_expected=False,
              reference_image=None, reference_video_count=1,
              clip=dict(start_frame=0, end_frame_inclusive=101, start_pts_rational='0',
                        end_pts_rational_inclusive='101/25', end_exclusive_rational='102/25',
                        duration_rational='102/25'))
for key, name in [('source', n['video']), ('provenance', n['provenance'])]:
    p = ROOT / 'inputs' / name
    source[key] = {'file': 'inputs/' + name, 'sha256': sha(p), 'bytes': p.stat().st_size}
source['original_media'] = {'file': str(ROOT / 'inputs' / n['original_source']), 'sha256': n['original_source_sha256']}
for c, field in [(n, 'graph_sha256'), (f, 'forced_graph_sha256')]:
    p = PRODUCER / 'configs/graphs' / (c['run_id'] + '.json')
    link(p, ROOT / 'configs/graphs' / p.name)
    source[field] = sha(p)
for src, dst in [('configs/scientific_contract.json', 'configs/producer_scientific_contract.json'),
                 ('configs/runtime.json', 'configs/producer_runtime.json'),
                 ('design/PREREGISTERED_EVENTS.json', 'configs/PREREGISTERED_EVENTS.json')]:
    link(PRODUCER / src, ROOT / dst)
events = json.loads((PRODUCER / 'design/PREREGISTERED_EVENTS.json').read_text())
save(ROOT / 'configs/SOURCE_EVENT_REVIEW_CUES.json', {'schema': 'r141-inherited-source-events-v1', 'items': [{
    'source_id': n['source_id'], 'prepared_frame_brackets': {e['name']: e['source_frames'] for e in events['events']},
    'evidence': {'file': str(PRODUCER / 'design/PREREGISTERED_EVENTS.json'), 'sha256': sha(PRODUCER / 'design/PREREGISTERED_EVENTS.json')},
    'scope': 'Inherited source-only events, evaluation only; no inference window input.'}]})
save(ROOT / 'configs/contract.json', dict(schema='r141-native-paired-consumer-binding-v1',
    producer_local=str(PRODUCER), producer_remote=runtime['remote_root'], producer_seal_sha256=SEAL,
    producer_contract_sha256=sha(PRODUCER / 'configs/scientific_contract.json'),
    producer_runtime_sha256=sha(PRODUCER / 'configs/runtime.json'), host=runtime['host'],
    source_order=['short_0252'], sources=[source], fixed_source_denominator=1, new_independent_sources=0,
    method=dict(name='fixed temporal guidance', steps_zero_based_inclusive=[6, 14], alpha=1, reference_images=0, caption='时序引导'),
    no_gpu_entry=True, no_auto_submission=True))
save(ROOT / 'configs/SHARED_CONSUMER_CODE.json', shared)
files = {str(p.relative_to(ROOT)): sha(p) for d in ('scripts', 'configs', 'inputs')
         for p in (ROOT / d).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
save(ROOT / 'CONSUMER_FREEZE.json', dict(schema='r141-shared-consumer-binding-v1', files=files,
    scope='Manifest and thin wrappers only; original R123 gate schema retained, registered-noise name and exact R141 prompt adapted.'))
print(sha(ROOT / 'CONSUMER_FREEZE.json'))
