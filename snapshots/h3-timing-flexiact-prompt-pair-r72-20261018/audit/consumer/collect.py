"""Bind actual completed output files and their producer evidence, CPU only."""
import os
from pathlib import Path
import shutil
import time
from common import *

def verify_collection(folder, pair, root=ROOT):
    record = read(folder / 'COLLECTION.json')
    require(record['source_id'] == pair and record['schema'] == 'r72-actual-prompt-collection-v1', 'wrong intake')
    for name, entry in record['files'].items():
        require(Path(name).name == name and sha(folder / name) == entry['sha256'], 'intake changed: ' + name)
    gate = validate_gate(read(folder / 'PAIR_RUNTIME_GATE.json'), pair)
    require(sha(folder / 'scientific_contract.json') == sha(root / 'configs/scientific_contract.json'), 'science changed after intake')
    require(sha(folder / 'runtime.json') == gate['runtime_profile_sha256'] == sha(root / 'configs/runtime.json'), 'runtime changed after intake')
    for arm in ARMS:
        row = gate['runs'][arm]
        require(sha(folder / (arm + '.mp4')) == row['video']['sha256'], 'video differs from actual gate')
        for suffix, key in (('_history.json', 'history_sha256'), ('_job.json', 'job_sha256'), ('_router.json', 'router_file_sha256')):
            require(sha(folder / (arm + suffix)) == row[key], 'actual evidence binding differs')
    cases(root, pair)
    return gate

def collect(pair, root=ROOT):
    root = Path(root)
    require(readiness(root, pair) == 'PASSED', 'actual history/gate not ready')
    here = root / 'audit/consumer'
    out = here / 'incoming' / pair
    if out.exists():
        verify_collection(out, pair, root)
        return out
    receipt = root / 'analysis/postrun' / pair / 'PAIR_RUNTIME_GATE.json'
    gate = validate_gate(read(receipt), pair)
    rows = cases(root, pair)
    seal = read(root / 'deploy_manifest.json')
    require(all(sha(root / p) == b['sha256'] for p, b in seal['files'].items()), 'producer seal changed')
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(pair + f'.collecting.{os.getpid()}')
    require(not temp.exists(), 'retain previous failed intake')
    temp.mkdir()
    started = time.monotonic()
    shutil.copy2(receipt, temp / 'PAIR_RUNTIME_GATE.json')
    for arm in ARMS:
        row = gate['runs'][arm]
        video = Path(row['video']['file'])
        require(video.resolve().is_relative_to(root / 'output') and not video.is_symlink() and sha(video) == row['video']['sha256'], 'unsafe or changed output')
        shutil.copy2(video, temp / (arm + '.mp4'))
        run = row['run_id']
        for relative, name, key in ((f'logs/{run}_history.json', arm + '_history.json', 'history_sha256'), (f'logs/{run}_job.json', arm + '_job.json', 'job_sha256'), (f'audit/router/{run}.json', arm + '_router.json', 'router_file_sha256')):
            source = root / relative
            require(sha(source) == row[key], 'producer evidence changed: ' + relative)
            shutil.copy2(source, temp / name)
        for relative, name in ((f'configs/graphs/{run}.json', arm + '_graph.json'), (f'audit/{run}_conditioning.json', arm + '_conditioning.json'), (f'audit/{run}_noise.json', arm + '_noise.json')):
            shutil.copy2(root / relative, temp / name)
    for relative in ('configs/scientific_contract.json', 'configs/runtime.json', 'deploy_manifest.json', 'design/PAIR_DEFINITIONS.json'):
        shutil.copy2(root / relative, temp / Path(relative).name)
    record = {'schema': 'r72-actual-prompt-collection-v1', 'source_id': pair, 'producer': str(root), 'receipt': bound(receipt), 'created_unix': time.time(), 'source_video': bound(root / 'inputs' / rows[0]['video']), 'target_portrait': bound(root / 'inputs' / rows[0]['portrait']), 'files': {p.name: bound(p) for p in temp.iterdir() if p.is_file()}, 'collection_wall_seconds': time.monotonic() - started, 'gpu_started': False}
    save(temp / 'COLLECTION.json', record)
    verify_collection(temp, pair, root)
    os.replace(temp, out)
    return out

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--pair', choices=PAIRS, required=True)
    a = p.parse_args()
    print(collect(a.pair))
