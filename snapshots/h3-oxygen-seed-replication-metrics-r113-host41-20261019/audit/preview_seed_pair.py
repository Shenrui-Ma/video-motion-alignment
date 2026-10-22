"""Read a completed per-seed pair while the other registered seed continues."""
from pathlib import Path
import argparse, json, shutil, sys, time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import verify_static, verify_pair, verify_run, read, save, sha, bound, require, ARMS, SEEDS
from consume import remote_json, fetch
from media import seed_paths, make_comparison, frame_pages

def main(seed, gate_name=None):
    cfg = verify_static(); require(seed in SEEDS, 'registered seed required')
    gate_name = gate_name or f'analysis/postrun/seed{seed}/PAIR_RUNTIME_GATE.json'
    require(not Path(gate_name).is_absolute() and '..' not in Path(gate_name).parts, 'relative preview gate required')
    gate = remote_json(cfg, gate_name)
    if gate is None:
        print(json.dumps({'state': 'WAIT_SEED_PAIR_GATE', 'seed': seed})); return
    verify_pair(gate, seed, cfg)
    destination = ROOT / 'audit' / f'actual_seed{seed}_preview'
    require(not destination.exists(), 'existing preview must remain intact')
    stage = ROOT / 'audit' / f'preview_intake_{seed}_{time.time_ns()}'
    stage.mkdir()
    files = {'PAIR_GATE.json': gate_name, 'service.json': 'processes/service.json',
             'deploy_manifest.json': 'deploy_manifest.json', 'runtime.json': 'configs/runtime.json'}
    for arm in ARMS:
        run = cfg['runs'][str(seed)][arm]
        files.update({run + '_graph.json': f'configs/graphs/{run}.json',
                      run + '_job.json': f'logs/{run}_job.json',
                      run + '_history.json': f'logs/{run}_history.json',
                      run + '_router.json': f'audit/router/{run}.json',
                      run + '_conditioning.json': f'audit/{run}_conditioning.json',
                      run + '_noise.json': f'audit/{run}_noise.json',
                      run + '.mp4': str(Path(gate['runs'][arm]['video']['file']).relative_to(cfg['producer_remote']))})
    for name, remote in files.items(): fetch(cfg, remote, stage / name)
    require(read(stage / 'PAIR_GATE.json') == gate == remote_json(cfg, gate_name), 'pair gate changed during transfer')
    require(sha(stage / 'deploy_manifest.json') == cfg['producer_seal_sha256'], 'producer seal differs')
    require(sha(stage / 'runtime.json') == cfg['producer_runtime_sha256'], 'actual runtime differs')
    require(read(stage / 'service.json') == gate['service_owner'], 'actual owner differs')
    for arm in ARMS: verify_run(stage, gate, seed, arm, cfg)
    shutil.copy2(cfg['source']['file'], stage / 'source.mp4')
    require(sha(stage / 'source.mp4') == cfg['source']['sha256'], 'source changed')
    save(stage / 'PREVIEW_INTAKE.json', {'passed': True, 'seed': seed,
         'scope': 'Completed pair preview while registered batch remains active',
         'all_four_complete': False, 'release_required_for_this_read_only_preview': False,
         'consumer_freeze_sha256': sha(ROOT / 'CONSUMER_FREEZE.json'),
         'producer_seal_sha256': cfg['producer_seal_sha256'],
         'files': {p.name: sha(p) for p in stage.iterdir() if p.is_file()},
         'valid_frames': 98, 'fps': 24, 'GPU_started': False})
    stage.rename(destination)
    media = destination / 'media'; media.mkdir()
    paths = seed_paths(destination, seed)
    make_comparison(paths, media)
    pages = frame_pages(paths, media)
    save(media / 'PREVIEW_PRESENTATION.json', {'seed': seed, 'roles': ['source', 'native', 'fixed'],
         'input_binding': bound(destination / 'PREVIEW_INTAKE.json'),
         'pair_gate': bound(destination / 'PAIR_GATE.json'),
         'preregistered_events': bound(ROOT / 'configs/PREREGISTERED_EVENTS.json'),
         'video': bound(media / 'comparison.mp4'), 'pages': pages, 'valid_frames': 98,
         'all_four_complete': False, 'status': 'PER_SEED_ACTUAL_PAIR_READY_FOR_VISUAL_REVIEW'})
    print(json.dumps({'seed': seed, 'folder': str(destination),
                      'presentation': bound(media / 'PREVIEW_PRESENTATION.json')}, ensure_ascii=False))

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--seed', type=int, required=True)
    p.add_argument('--gate')
    a = p.parse_args(); main(a.seed, a.gate)
