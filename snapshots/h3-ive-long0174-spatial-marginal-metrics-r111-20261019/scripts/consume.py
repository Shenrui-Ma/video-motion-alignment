"""Collect only a completed, released R111 run and render its actual four-way comparison."""
import argparse
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from common import ROOT, read, save, sha, bound, require, verify_static, verify_gate
from common import verify_release, verify_job, verify_collection


def remote_path(cfg, relative):
    relative = Path(relative)
    require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe remote path')
    return Path(cfg['producer_remote'])/relative


def remote_json(cfg, relative):
    path = remote_path(cfg, relative)
    code = 'from pathlib import Path;p=Path('+repr(str(path))+');print(p.read_text() if p.exists() else "null")'
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', cfg['host'],
        shlex.join(['python3', '-c', code])], capture_output=True, text=True, check=True, timeout=50)
    import json
    return json.loads(result.stdout)


def fetch(cfg, relative, output):
    path = remote_path(cfg, relative)
    subprocess.run(['rsync', '-az', '-e', 'ssh -o BatchMode=yes -o ConnectTimeout=12',
                    cfg['host']+':'+str(path), str(output)], check=True, timeout=300)


def collect(attempt):
    cfg = verify_static()
    require(attempt.startswith('root_') and attempt.replace('_', '').isalnum(), 'invalid attempt name')
    dest = ROOT/'incoming/long_0174'
    if dest.exists():
        receipt = verify_collection(dest)
        require(receipt['attempt'] == attempt, 'existing intake belongs to a different attempt')
        return dest
    gate_rel = 'analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json'
    gate = remote_json(cfg, gate_rel)
    complete = remote_json(cfg, 'audit/'+attempt+'/COMPLETE.json')
    release = remote_json(cfg, 'audit/'+attempt+'/ROOT_EXIT_RECEIPT.json')
    if gate is None or complete is None or release is None:
        return None
    verify_gate(gate, cfg)
    require(remote_json(cfg, 'deploy_manifest.json') == read(ROOT/'configs/producer_deploy_manifest.json'),
            'deployed producer differs from consumer binding')
    stage = ROOT/'audit'/('intake_'+str(time.time_ns()))
    stage.mkdir(parents=True)
    run = cfg['run_id']
    files = {'PAIR_RUNTIME_GATE.json': gate_rel, 'COMPLETE.json': 'audit/'+attempt+'/COMPLETE.json',
        'ROOT_EXIT_RECEIPT.json': 'audit/'+attempt+'/ROOT_EXIT_RECEIPT.json',
        'STARTED.json': 'audit/'+attempt+'/STARTED.json', 'cleanup.json': 'processes/cleanup.json',
        'service.json': 'processes/service.json', 'graph.json': f'configs/graphs/{run}.json',
        'job.json': f'logs/{run}_job.json', 'history.json': f'logs/{run}_history.json',
        'router.json': f'audit/router/{run}.json', 'spatial.mp4': f'output/{run}_00001_.mp4'}
    for name, rel in files.items():
        fetch(cfg, rel, stage/name)
    require(read(stage/'PAIR_RUNTIME_GATE.json') == gate and read(stage/'COMPLETE.json') == complete
            and read(stage/'ROOT_EXIT_RECEIPT.json') == release, 'producer receipts changed during transfer')
    require(read(stage/'service.json') == gate['service_owner'], 'actual service generation changed')
    verify_release(gate, complete, release, read(stage/'STARTED.json'), read(stage/'cleanup.json'),
                   sha(stage/'PAIR_RUNTIME_GATE.json'), cfg)
    verify_job(stage, gate, cfg)
    require(sha(stage/'spatial.mp4') == gate['runs']['forced']['video']['sha256'], 'R111 media hash differs')
    for role, item in cfg['historical_media'].items():
        require(sha(item['file']) == item['sha256'], 'historical media changed before copy')
        shutil.copy2(item['file'], stage/(role+'.mp4'))
    for name, item in cfg['historical_evidence'].items():
        shutil.copy2(item['file'], stage/(name+'.json'))
    require(remote_json(cfg, gate_rel) == gate, 'actual paired gate changed after transfer')
    save(stage/'COLLECTION.json', {'passed': True, 'attempt': attempt,
        'consumer_freeze_sha256': sha(ROOT/'CONSUMER_FREEZE.json'),
        'files': {p.name: sha(p) for p in stage.iterdir() if p.is_file()},
        'roles': ['source', 'native', 'fixed', 'spatial'], 'valid_frames': 145, 'fps': 24,
        'crop_xywh': [16, 8, 1280, 720], 'official_MF': 'PENDING_ACTUAL_SCORING',
        'visual_review': 'PENDING_FULL145_REVIEW', 'created_unix': time.time()})
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage.rename(dest)
    verify_collection(dest)
    return dest


def main():
    import json
    from media import render, prepare_mf
    from review import template
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        cfg = verify_static()
        gate = remote_json(cfg, 'analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json')
        complete = remote_json(cfg, 'audit/'+args.attempt+'/COMPLETE.json')
        if gate is not None:
            verify_gate(gate, cfg)
        print(json.dumps({'gate_present': gate is not None, 'complete_present': complete is not None}))
        return
    incoming = collect(args.attempt)
    if incoming is None:
        print(json.dumps({'state': 'PENDING_ACTUAL_COMPLETED_RELEASED_R111'}))
        return
    show = ROOT/'showcase/long_0174'
    if not show.exists():
        render(incoming, show)
    else:
        receipt = read(show/'PRESENTATION.json')
        require(sha(show/'four_columns.mp4') == receipt['video']['sha256'], 'presentation changed')
    prepared = ROOT/'prepared/long_0174'
    if not prepared.exists():
        prepare_mf(incoming, prepared)
    else:
        manifest = read(prepared/'MF_INPUTS.json')
        require(manifest['pair_gate']['sha256'] == sha(incoming/'PAIR_RUNTIME_GATE.json'),
                'existing MF input belongs to another gate')
        for row in manifest['roles'].values():
            require(sha(row['score_video']['file']) == row['score_video']['sha256'], 'MF media changed')
    review = template(incoming, show)
    print(json.dumps({'state': 'ACTUAL_COMPARISON_AND_MF_INPUTS_READY',
        'presentation': bound(show/'PRESENTATION.json'), 'MF_inputs': bound(prepared/'MF_INPUTS.json'),
        'full_frame_ledger': bound(show/'FRAME_LEDGER.json'), 'review_template': bound(review),
        'official_MF': 'PENDING_ACTUAL_SCORING'},
        ensure_ascii=False))


if __name__ == '__main__':
    main()
