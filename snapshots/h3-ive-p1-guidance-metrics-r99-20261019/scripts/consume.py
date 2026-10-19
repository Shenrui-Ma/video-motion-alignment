"""Read actual R99 paired gates, collect media, and publish same-time triplets."""
import argparse
import base64
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'configs/contract.json').read_text())
REMOTE = Path(CONFIG['producer_remote'])
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', CONFIG['host']]
FFMPEG = '/opt/homebrew/bin/ffmpeg'
FFPROBE = '/opt/homebrew/bin/ffprobe'
REQUIRED_CHECKS = (
    'producer_seal', 'same_host_numerical_runtime', 'actual_runtime_device',
    'actual_history', 'actual_service_generation', 'actual_condition_snapshot',
    'all_conditions_equal_actual_Native', 'pre_DiT_condition_gate',
    'actual_parent_six_condition_tensors', 'actual20NFE20Euler450routes',
    'valid_physical_support', 'sampled_finite', 'same_sampler_grid_and_initial_packed_noise',
    'AV_prediction_prefix_0_5_bitwise_equal', 'actual_raw_AV_noise_equal_Native', 'output_geometry')
HELPER = Path('/Users/researcher/DevProjects/h3-ive-subject-capacity-metrics-r89-20261018/scripts')
sys.path.insert(0, str(HELPER))
spec = importlib.util.spec_from_file_location('r89_display', HELPER / 'render_pair.py')
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def bound(path):
    return {'file': str(Path(path).resolve()), 'sha256': sha(path)}


def remote_json(path):
    require(Path(path).is_relative_to(REMOTE) and '..' not in Path(path).parts,
            'remote path outside producer')
    code = ('import json;from pathlib import Path;p=Path(' + repr(str(path)) + ');'
            'print(p.read_text() if p.exists() else "null")')
    out = subprocess.run(SSH + [shlex.join(['python3', '-c', code])],
                         capture_output=True, text=True, check=True, timeout=50)
    return json.loads(out.stdout)


def fetch(path, destination):
    require(Path(path).is_relative_to(REMOTE) and '..' not in Path(path).parts,
            'remote transfer outside producer')
    subprocess.run(['rsync', '-az', '-e', 'ssh -o BatchMode=yes -o ConnectTimeout=12',
                    CONFIG['host'] + ':' + str(path), str(destination)],
                   check=True, timeout=240)


def verify_gate(source, gate):
    c = CONFIG['cases'][source]
    require(gate.get('schema') == 'r99-historical-native-paired-runtime-gate-v1'
            and gate.get('passed') is True, 'actual paired gate not passed')
    require(gate.get('source_id') == source, 'source mismatch')
    checks = gate.get('checks', {})
    require(checks and all(value is True for value in checks.values()), 'failed gate checks')
    require(all(checks.get(name) is True for name in REQUIRED_CHECKS), 'required gate evidence missing')
    require(gate.get('runtime_profile_sha256') == CONFIG['producer_runtime_sha256'],
            'producer runtime binding differs')
    runs = gate['runs']
    native, forced = runs['native'], runs['forced']
    require(native['run_id'] == c['run_id'] and native['video']['sha256'] == c['native_video']['sha256'],
            'historical ordinary output mismatch')
    require(forced['run_id'] == f'r99_{source}_seed2026101701_forced', 'guided run mismatch')
    require((native['NFE'], native['routed_blocks'], forced['NFE'], forced['routed_blocks'])
            == (20, 0, 20, 450), 'execution count mismatch')
    require(native['valid_frames'] == forced['valid_frames'] == c['valid_frames'],
            'physical support mismatch')
    prefix = gate['prefix_tensor_comparison']
    require(len(prefix) == 6, 'pre-intervention prefix absent')
    for i, row in enumerate(prefix):
        require(row['step_zero_based'] == i and row['video'] is True and row['audio'] is True,
                'pre-intervention AV prediction differs')
        require(row['parent_file_sha256'] == c['first_six_predictions'][i]['sha256'],
                'wrong historical prediction')
    path = Path(forced['video']['file'])
    require(path.is_relative_to(REMOTE / 'output') and '..' not in path.parts,
            'guided output outside producer')
    return gate


def collect(source):
    dest = ROOT / 'incoming' / source
    if dest.exists():
        receipt = read(dest / 'COLLECTION.json')
        for name, digest in receipt['files'].items():
            require(Path(name).name == name and sha(dest / name) == digest, 'intake modified')
        verify_gate(source, read(dest / 'PAIR_RUNTIME_GATE.json'))
        return dest
    gate_path = REMOTE / 'analysis/postrun' / source / 'PAIR_RUNTIME_GATE.json'
    gate = remote_json(gate_path)
    if gate is None:
        return None
    verify_gate(source, gate)
    owner = remote_json(REMOTE / 'processes/service.json')
    require(owner == gate['service_owner'], 'actual service generation mismatch')
    seal = remote_json(REMOTE / 'deploy_manifest.json')
    require(seal == read(ROOT / 'configs/producer_deploy_manifest.json'), 'producer seal changed')
    staging = ROOT / 'audit' / f'collect_{source}_{time.time_ns()}'
    staging.mkdir()
    fetch(gate_path, staging / 'PAIR_RUNTIME_GATE.json')
    require(read(staging / 'PAIR_RUNTIME_GATE.json') == gate, 'gate changed during download')
    run = gate['runs']['forced']
    fetch(run['video']['file'], staging / 'forced.mp4')
    require(sha(staging / 'forced.mp4') == run['video']['sha256'], 'guided video hash mismatch')
    paths = {'graph': f"configs/graphs/{run['run_id']}.json",
             'job': f"logs/{run['run_id']}_job.json",
             'history': f"logs/{run['run_id']}_history.json",
             'router': f"audit/router/{run['run_id']}.json"}
    for name, path in paths.items():
        fetch(REMOTE / path, staging / (name + '.json'))
    job, history, graph, router = [read(staging / (x + '.json'))
                                   for x in ('job', 'history', 'graph', 'router')]
    require(job['status'] == 'success' and job['name'] == run['run_id'], 'job incomplete')
    require(job['graph_sha256'] == sha(staging / 'graph.json'), 'actual graph mismatch')
    require(job['service_pid'] == owner['pid'] and job['service_identity'] == owner['identity'],
            'job ownership mismatch')
    require(history['status']['completed'] is True and history['status']['status_str'] == 'success'
            and history['prompt'][2] == graph, 'successful history mismatch')
    require(router['routed_calls'] == 450 and router['routed_by_forward'] == [0]*6+[50]*9+[0]*5,
            'actual intervention schedule mismatch')
    c = CONFIG['cases'][source]
    for name, key in [('native.mp4', 'native_video'), ('source.mp4', 'reference_video')]:
        item = c[key]
        require(sha(item['file']) == item['sha256'], 'historical media modified')
        shutil.copy2(item['file'], staging / name)
    require(remote_json(gate_path) == gate, 'gate changed after download')
    save(staging / 'COLLECTION.json', {'source': source, 'owner': owner,
         'files': {p.name: sha(p) for p in staging.iterdir() if p.is_file()},
         'valid_frames': c['valid_frames'], 'fps': 24, 'crop_xywh': CONFIG['crop_xywh'],
         'metric_status': 'pending official MF; no score inferred from visual review'})
    staging.rename(dest)
    return dest


def uri(path):
    kind = 'video/mp4' if Path(path).suffix == '.mp4' else 'image/jpeg'
    return 'data:' + kind + ';base64,' + base64.b64encode(Path(path).read_bytes()).decode()


def render(source, incoming):
    dest = ROOT / 'showcase' / source
    if dest.exists():
        return read(dest / 'PRESENTATION.json')
    c = CONFIG['cases'][source]
    paths = [incoming / (name + '.mp4') for name in ('source', 'native', 'forced')]
    infos = [display.media_info(path, FFPROBE) for path in paths]
    for info in infos:
        display.check_time(info, 90, 1312, 736)
    staging = ROOT / 'audit' / f'render_{source}_{time.time_ns()}'
    staging.mkdir()
    display.caption_strip(display.choose_font()).save(staging / 'caption.png')
    video = staging / 'full_valid.mp4'
    cmd = display.command(paths, staging / 'caption.png', video,
                          c['valid_frames'], FFMPEG, c['valid_frames'])
    subprocess.run(cmd, check=True, timeout=420)
    display.check_time(display.media_info(video, FFPROBE), c['valid_frames'], 3840, 808)
    poster = staging / 'poster.jpg'
    subprocess.run([FFMPEG, '-v', 'error', '-threads', '1', '-i', str(video),
                    '-frames:v', '1', '-threads', '1', str(poster)], check=True, timeout=60)
    output = Path('/Users/researcher/Downloads') / f'H3_R99_{source}_普通编辑与时序引导_20261019.html'
    require(not output.exists(), 'published result already exists')
    document = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(c['task'])}</title><style>body{{max-width:2200px;margin:28px auto;padding:0 20px;background:#101115;color:#eee;font:18px/1.6 system-ui}}video{{width:100%;background:black}}a{{color:#aad4ff}}</style><h1>{html.escape(c['task'])}</h1><p>IVEBench · 左：参考视频；中：修复提示词后的普通编辑；右：同条件时序引导。</p><video controls playsinline preload="none" poster="{uri(poster)}" src="{uri(video)}"></video><p>{html.escape(CONFIG['method'])}。三列按同一原始时刻展示，24fps，共{c['valid_frames']}帧。</p><p>编辑完成情况、动作时间及官方 Motion Fidelity 待本组成片评测。</p><a id="dl" download="H3_R99_{source}_完整三栏.mp4">下载三栏视频</a><script>document.getElementById('dl').href=document.querySelector('video').src</script></html>'''
    output.write_text(document)
    receipt = {'source': source, 'task': c['task'], 'gate': bound(incoming / 'PAIR_RUNTIME_GATE.json'),
               'inputs': [bound(p) for p in paths], 'valid_frames': c['valid_frames'], 'fps': 24,
               'video': {'file': 'full_valid.mp4', 'sha256': sha(video)}, 'poster': {'file':'poster.jpg','sha256':sha(poster)},
               'html': bound(output), 'method': CONFIG['method'], 'official_MF': 'pending',
               'visual_review': 'pending', 'UI_review': 'not assessed: browser disabled'}
    save(staging / 'PRESENTATION.json', receipt)
    staging.rename(dest)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=CONFIG['cases'], required=True)
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        gate = remote_json(REMOTE / 'analysis/postrun' / args.source / 'PAIR_RUNTIME_GATE.json')
        print(json.dumps({'state': 'PENDING' if gate is None else 'PASSED',
                          'source': args.source, 'verified': gate is not None and bool(verify_gate(args.source, gate))}))
    else:
        incoming = collect(args.source)
        print(json.dumps({'state': 'PENDING', 'source': args.source} if incoming is None
                         else render(args.source, incoming), ensure_ascii=False))
