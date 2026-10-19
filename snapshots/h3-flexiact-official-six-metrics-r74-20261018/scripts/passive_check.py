"""Verify the deployed consumer on CPU, including real imports and display filters."""
import importlib
import os
import platform
import shutil
import subprocess
import sys
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
from common import *


def main():
    start = time.monotonic()
    cfg = verify_runtime()
    require(str(ROOT) == cfg['root_host41'], 'check the actual .41 deployment')
    require(sys.executable == cfg['python_host41'], 'wrong actual Python')
    out = ROOT / 'audit/passive_check'
    out.mkdir(parents=True, exist_ok=False)
    pins = read(ROOT / 'configs/NUMERICAL_INHERITANCE.json')
    for path, row in pins.items():
        require(sha(ROOT / path) == row['sha256'], 'inherited code changed: ' + path)
    producer = Path(cfg['producer_root_host41'])
    require(sha(producer / 'deploy_manifest.json') == cfg['producer_seal_sha256'], 'producer seal differs')
    require(read(producer / 'configs/admission.json')['scope'] == 'own_user_video_jobs', 'producer admission scope differs')
    import torch
    require(not torch.cuda.is_initialized(), 'CPU check unexpectedly initialized CUDA')
    deps = {}
    for name in ['numpy', 'cv2', 'onnxruntime', 'PIL', 'einops', 'imageio', 'matplotlib']:
        module = importlib.import_module(name)
        deps[name] = {'version': str(getattr(module, '__version__', 'unknown')), 'file': str(getattr(module, '__file__', None))}
    sys.path.insert(0, str(METRIC / 'vendor/co-tracker'))
    from cotracker.predictor import CoTrackerPredictor
    require(CoTrackerPredictor is not None, 'tracker import failed')
    import physical
    protocol = physical.protocol()
    probe = load('r74_passive_pose', ROOT / 'runtime/source_pose/pose_probe.py')
    for path in ['src/custom_controlnet_aux/dwpose/dw_onnx/cv_ox_det.py', 'src/custom_controlnet_aux/dwpose/dw_torchscript/jit_pose.py']:
        probe.import_file('r74_passive_' + Path(path).stem, Path(protocol['aux_root']) / path)
    run_tracks = load('r74_passive_tracks', METRIC / 'run_tracks.py')
    source_info = {}
    for action in MOTIONS:
        item = source_item(action)
        path = METRIC / item['file']
        require(sha(path) == item['sha256'], 'official source changed')
        source_info[action] = {'source49': bound(path), 'timebase': run_tracks.check_timebase(path), 'source158': bound(physical.source_video(action))}
    font = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    require(font.is_file(), 'Chinese display font missing')
    from make_triptych import build
    smoke = out / 'source_only_render_smoke.mp4'
    source = physical.source_video(MOTIONS[0])
    cmd = build([source] * 3, str(font), smoke, 2)
    subprocess.run(cmd, check=True, timeout=120)
    info = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries', 'stream=width,height,nb_read_frames,avg_frame_rate', '-of', 'json', str(smoke)], check=True, capture_output=True, text=True).stdout)['streams'][0]
    require(info['width'] == 3456 and info['height'] == 856 and info['nb_read_frames'] == '2' and info['avg_frame_rate'] == '24/1', 'display smoke geometry/time differs')
    require(not torch.cuda.is_initialized(), 'CPU check unexpectedly initialized CUDA')
    result = {'passed': True, 'hostname': platform.node(), 'python': sys.executable, 'torch': torch.__version__, 'CUDA_initialized': False, 'consumer_freeze_sha256': sha(ROOT / 'CONSUMER_FREEZE.json'), 'numeric_files_checked': len(pins), 'dependencies': deps, 'sources': source_info, 'physical_protocol': bound(ROOT / 'configs/physical_protocol.json'), 'source_only_render_smoke': {'video': bound(smoke), 'probe': info, 'scope': 'Administrative display smoke: the same source is repeated three times. No model result.'}, 'elapsed_seconds': time.monotonic() - start, 'free_storage_bytes': shutil.disk_usage(ROOT).free}
    save(out / 'RESULT.json', result)
    print(json.dumps({k: result[k] for k in ['passed', 'hostname', 'torch', 'CUDA_initialized', 'numeric_files_checked', 'consumer_freeze_sha256', 'elapsed_seconds', 'free_storage_bytes']}, indent=2))


if __name__ == '__main__':
    main()
