"""Collect all four actual R113 runs after the producer's aggregate and release gates."""
from pathlib import Path
import argparse, json, shlex, shutil, subprocess, time
from common import ROOT, ARMS, SEEDS, read, save, sha, bound, relative, require
from common import verify_static, verify_aggregate, verify_release, verify_collection

def remote_json(cfg, name):
    file = Path(cfg['producer_remote'])/relative(name)
    code = 'from pathlib import Path;p=Path('+repr(str(file))+');print(p.read_text() if p.exists() else "null")'
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', cfg['host'],
        'python3 -c '+shlex.quote(code)], capture_output=True, text=True, check=True, timeout=60)
    return json.loads(result.stdout)

def fetch(cfg, name, destination):
    file = Path(cfg['producer_remote'])/relative(name)
    subprocess.run(['rsync', '-az', '-e', 'ssh -o BatchMode=yes -o ConnectTimeout=12',
                    cfg['host']+':'+str(file), str(destination)], check=True, timeout=300)

def valid_attempt(attempt):
    return attempt.startswith(('root_', 'host41_')) and attempt.replace('_', '').isalnum()

def collect(attempt):
    cfg = verify_static()
    require(valid_attempt(attempt), 'invalid actual attempt')
    target = ROOT/'incoming/actual'
    if target.exists():
        require(verify_collection(target)['attempt'] == attempt, 'existing intake belongs to another attempt')
        return target
    aggregate_name = 'analysis/postrun/PAIR_RUNTIME_GATE.json'
    aggregate = remote_json(cfg, aggregate_name)
    complete = remote_json(cfg, 'audit/'+attempt+'/COMPLETE.json')
    release = remote_json(cfg, 'audit/'+attempt+'/ROOT_EXIT_RECEIPT.json')
    if any(value is None for value in (aggregate, complete, release)):
        return None
    pairs = {str(seed): remote_json(cfg, f'analysis/postrun/seed{seed}/PAIR_RUNTIME_GATE.json') for seed in SEEDS}
    require(all(pairs.values()), 'both actual pair gates required')
    verify_aggregate(aggregate, pairs, cfg)
    stage = ROOT/'audit'/('intake_'+str(time.time_ns()))
    stage.mkdir()
    files = {'AGGREGATE_GATE.json': aggregate_name, 'COMPLETE.json': f'audit/{attempt}/COMPLETE.json',
             'ROOT_EXIT_RECEIPT.json': f'audit/{attempt}/ROOT_EXIT_RECEIPT.json', 'STARTED.json': f'audit/{attempt}/STARTED.json',
             'cleanup.json': 'processes/cleanup.json', 'service.json': 'processes/service.json',
             'deploy_manifest.json': 'deploy_manifest.json'}
    for seed in SEEDS:
        files[f'seed{seed}_PAIR_GATE.json'] = f'analysis/postrun/seed{seed}/PAIR_RUNTIME_GATE.json'
        for arm in ARMS:
            run = cfg['runs'][str(seed)][arm]
            files.update({run+'_graph.json': f'configs/graphs/{run}.json', run+'_job.json': f'logs/{run}_job.json',
                          run+'_history.json': f'logs/{run}_history.json', run+'_router.json': f'audit/router/{run}.json',
                          run+'_conditioning.json': f'audit/{run}_conditioning.json', run+'_noise.json': f'audit/{run}_noise.json',
                          run+'.mp4': str(Path(pairs[str(seed)]['runs'][arm]['video']['file']).relative_to(cfg['producer_remote']))})
    # Explicit small files and videos only. Full condition/noise/x0 tensors remain on the producer.
    for name, remote in files.items():
        fetch(cfg, remote, stage/name)
    require(read(stage/'AGGREGATE_GATE.json') == aggregate and read(stage/'COMPLETE.json') == complete
            and read(stage/'ROOT_EXIT_RECEIPT.json') == release, 'producer receipts changed during collection')
    verify_release(aggregate, complete, release, read(stage/'STARTED.json'), read(stage/'cleanup.json'), sha(stage/'AGGREGATE_GATE.json'), cfg)
    shutil.copy2(cfg['source']['file'], stage/'source.mp4')
    require(remote_json(cfg, aggregate_name) == aggregate, 'aggregate gate changed after transfer')
    save(stage/'COLLECTION.json', {'passed': True, 'attempt': attempt, 'all_four_retained': True,
         'consumer_freeze_sha256': sha(ROOT/'CONSUMER_FREEZE.json'),
         'files': {path.name: sha(path) for path in stage.iterdir() if path.is_file()},
         'valid_frames': 98, 'fps': 24, 'seeds': list(SEEDS), 'source_plus_generated_count': 5,
         'quality_review': 'PENDING_ALL_FOUR_TASK_AND_EVENT_REVIEW', 'created_unix': time.time()})
    verify_collection(stage)
    stage.rename(target)
    verify_collection(target)
    return target

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        cfg = verify_static()
        print(json.dumps({'aggregate_present': remote_json(cfg, 'analysis/postrun/PAIR_RUNTIME_GATE.json') is not None,
                          'complete_present': remote_json(cfg, 'audit/'+args.attempt+'/COMPLETE.json') is not None,
                          'GPU_started': False}))
        return
    incoming = collect(args.attempt)
    if incoming is None:
        print(json.dumps({'state': 'WAIT_ACTUAL_ALL_FOUR_COMPLETE_AND_RELEASED', 'GPU_started': False}))
        return
    from media import render, prepare_mf, combined_index
    from review import template
    outputs = []
    for seed in SEEDS:
        show = ROOT/'showcase'/str(seed)
        if not show.exists():
            render(incoming, show, seed)
        prepared = ROOT/'prepared'/str(seed)
        if not prepared.exists():
            prepare_mf(incoming, prepared, seed)
        outputs.append({'seed': seed, 'presentation': bound(show/'PRESENTATION.json'),
                        'MF_inputs': bound(prepared/'MF_INPUTS.json'), 'review': bound(template(incoming, show, seed))})
    if not (ROOT/'showcase/COMBINED_PRESENTATION.json').exists():
        combined_index()
    print(json.dumps({'state': 'TWO_ACTUAL_PAIRS_READY_FOR_REVIEW', 'outputs': outputs, 'GPU_started': False}, ensure_ascii=False))

if __name__ == '__main__':
    main()
