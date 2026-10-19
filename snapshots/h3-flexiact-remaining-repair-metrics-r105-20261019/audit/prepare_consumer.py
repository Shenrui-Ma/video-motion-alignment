"""Prepare CPU collection and media for three actual future R105 task pairs."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'h3-flexiact-remaining-repair-metrics-r104-20261019'
PRODUCER = ROOT.parent / 'h3-timing-flexiact-remaining-repair-r105-20261019'
OLD = ('fitness__game_man_4', 'human2animal_1__movie_man_11', 'crouch__movie_man_5')
NEW = ('human2animal_2__movie_man_11', 'crouch__movie_man_4', 'human2animal_3__game_man_4')
TASKS = (
    '将深蓝西装年长男子迁移到盘腿坐姿前屈动作，采用目标图室外铺装路面、草地与植被场景。',
    '将深蓝泳裤男子迁移到两轮下蹲起立动作，采用目标图蓝海与天空背景。',
    '将绿披肩动漫男子迁移到低位前倾后屈腿抬升的动作，采用目标图白背景。',
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


assert not (ROOT / 'CONSUMER_FREEZE.json').exists()
for folder in ('scripts', 'tests', 'configs', 'inputs', 'incoming', 'incoming_pairs',
               'showcase', 'showcase_pairs', 'prepared'):
    (ROOT / folder).mkdir(exist_ok=True)
for folder in ('scripts', 'tests'):
    for src in (PARENT / folder).glob('*.py'):
        text = src.read_text().replace('r104', 'r105').replace('R104', 'R105')
        for old, new in zip(OLD, NEW):
            text = text.replace(old, new)
        text = text.replace('8568', '8569').replace(
            '/data5/researcher/h3_runs/timing_flexiact_remaining_repair_r105_20261019',
            '/home/researcher/h3_runs/timing_flexiact_remaining_repair_r105_20261019')
        (ROOT / folder / src.name).write_text(text)

spec = read(PRODUCER / 'configs/scientific_contract.json')
runtime = read(PRODUCER / 'configs/runtime.json')
assert tuple(spec['source_ids']) == NEW
contract = read(PARENT / 'configs/contract.json')
contract.update(schema='r105-native-and-paired-media-consumer-v1',
                producer_local=str(PRODUCER), producer_remote=runtime['remote_root'],
                producer_seal_sha256=sha(PRODUCER / 'deploy_manifest.json'),
                producer_contract_sha256=sha(PRODUCER / 'configs/scientific_contract.json'),
                producer_runtime_sha256=sha(PRODUCER / 'configs/runtime.json'),
                source_order=list(NEW), sources=[])
for index, key in enumerate(NEW):
    native = next(c for c in spec['cases'] if c['source_id'] == key and c['arm'] == 'native')
    forced = next(c for c in spec['cases'] if c['source_id'] == key and c['arm'] == 'forced')
    row = {
        'source_id': key, 'run_id': native['run_id'], 'forced_run_id': forced['run_id'],
        'graph_sha256': sha(PRODUCER / 'configs/graphs' / (native['run_id'] + '.json')),
        'forced_graph_sha256': sha(PRODUCER / 'configs/graphs' / (forced['run_id'] + '.json')),
        'geometry': native['geometry'], 'valid_frames': native['valid_frame_count'],
        'crop_xywh': native['evaluation_crop_xywh'], 'evaluation_indices': native['evaluation_indices'],
        'evaluation_fps': 8, 'prompt_version': native['prompt_version'], 'prompt': native['prompt'],
        'display_task': TASKS[index], 'reference_image_expected': native['reference_image_expected'],
        'original_task': {'pair_id': native['original_pair_id'], 'group': native['group'],
                          'motion_source_id': native['motion_source_id'], 'target_identity': native['identity'],
                          'edit_prompt': TASKS[index], 'prompt_scope': 'Frozen six-part repair of original source and target assets.'},
    }
    for kind, field in (('source', 'video'), ('provenance', 'provenance'), ('portrait', 'portrait')):
        name = native[field]
        dest = ROOT / 'inputs' / name
        shutil.copy2(PRODUCER / 'inputs' / name, dest)
        row[kind] = {'file': 'inputs/' + name, 'sha256': sha(dest), 'bytes': dest.stat().st_size}
    contract['sources'].append(row)
put(ROOT / 'configs/contract.json', contract)
for name, rel in (('producer_runtime.json', 'configs/runtime.json'),
                  ('producer_scientific_contract.json', 'configs/scientific_contract.json'),
                  ('producer_seal.json', 'deploy_manifest.json')):
    shutil.copy2(PRODUCER / rel, ROOT / 'configs' / name)

test = ROOT / 'tests/test_flex_scope.py'
text = test.read_text()
for key, old_group, new_group in (
    (NEW[0], 'original_official_pair', 'official_assets_crosspair'),
    (NEW[1], 'official_assets_crosspair', 'original_official_pair'),
    (NEW[2], 'original_official_pair', 'official_assets_crosspair'),
):
    text = text.replace(f"c.info('{key}')['original_task']['group'],'{old_group}'",
                        f"c.info('{key}')['original_task']['group'],'{new_group}'")
import re
tokens = contract['sources'][1]['reference_image_expected']['expected_DiT_visual_patch_tokens']
text = re.sub(r"(c\.info\('crouch__movie_man_4'\)\['reference_image_expected'\]\['expected_DiT_visual_patch_tokens'\],)\d+", rf'\g<1>{tokens}', text)
test.write_text(text)
put(ROOT / 'audit/PREPARATION_ORIGIN.json', {
    'parent_consumer': str(PARENT), 'parent_freeze_sha256': sha(PARENT / 'CONSUMER_FREEZE.json'),
    'producer': str(PRODUCER), 'producer_seal_sha256': sha(PRODUCER / 'deploy_manifest.json'),
    'GPU_started': False, 'watcher_started': False,
})
print(json.dumps({'consumer': str(ROOT), 'sources': list(NEW)}))
