#!/usr/bin/env python3
"""Collect one immutable local snapshot of each completed short_0177 v2 arm."""
import argparse
import base64
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys
import tempfile
import time

HOST = 'H3_HOST_CONFIGURE_LOCALLY'
REMOTE_ROOT = '/data4/research-user/h3_runs/interval_short0177_20261024_v3'
COHORT = 'interval_short0177_20261024'
BOOT = '67231bde-c973-4243-9ca1-df676a3d855c'
SOURCE_SHA = 'd5da95935608029e1c458def4cb1c09a3ce42ea7e6d60cc9a44c9c6575f801f2'
ARMS = {'native': 7, 'early': 5, 'fixed': 5, 'late': 6, 'split': 6, 'global_weak': 7}
STEPS = {'native': [], 'early': list(range(9)), 'fixed': list(range(6, 15)),
         'late': list(range(11, 20)), 'split': list(range(4)) + list(range(15, 20)),
         'global_weak': list(range(20))}
FILES = {'verified': 'verified.json', 'result': 'result.json', 'router': 'router.json',
         'timing': 'timing.json', 'backend': 'backend.json', 'backend_contract': 'backend_contract.json',
         'config': 'config.json', 'manifest': 'manifest.json'}
SSH = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', HOST]

# This program reads bounded JSON files only. It performs no remote mutation or CUDA call.
REMOTE_SNAPSHOT = r'''
import base64,json,pathlib,time,sys
root=pathlib.Path(sys.argv[1]); arms=json.loads(sys.argv[2]); output={}
def read(p):
 if p.stat().st_size>2*1024*1024: raise ValueError('JSON exceeds 2 MiB: '+str(p))
 raw=p.read_bytes(); return raw,json.loads(raw)
for arm,gpu in arms.items():
 lane=root/('gpu'+str(gpu)); verified=lane/(arm+'_VERIFIED.json')
 try:
  if not verified.exists():
   output[arm]={'status':'pending','reason':'VERIFIED receipt absent'};continue
  vr,v=read(verified)
  if v.get('passed') is not True:
   output[arm]={'status':'unverified','reason':'VERIFIED receipt not passed'};continue
  job='interval_short_0177_'+arm;attempt=job+'__a1'
  if v.get('job_id')!=job or v.get('attempt_id')!=attempt: raise ValueError('VERIFIED identity mismatch')
  paths={'verified':verified,'result':lane/'queue_state/results'/(job+'.json'),
   'router':lane/'audit/router'/(attempt+'.json'),'timing':lane/'audit/timing'/(attempt+'.json'),
   'backend':lane/'logs/backend_dispatch_audit.json','backend_contract':lane/'BACKEND_CONTRACT.json',
   'config':lane/'CONFIG.json','manifest':lane/'manifests'/(arm+'.json')}
  raws={}; values={}
  for key,path in paths.items():
   raw,value=(vr,v) if key=='verified' else read(path)
   raws[key]={'remote_path':str(path),'base64':base64.b64encode(raw).decode()};values[key]=value
  result=values['result']
  if len(result.get('files',[]))!=1: raise ValueError('Expected one raw output')
  video=pathlib.Path(result['files'][0]['path']); resolved=video.resolve(strict=True)
  resolved.relative_to((lane/'output').resolve(strict=True))
  if video.suffix.lower()!='.mp4': raise ValueError('Expected raw MP4')
  output[arm]={'status':'ready','captured_unix':time.time(),'json':raws,
    'video_remote_path':str(video),'video_resolved_path':str(resolved),'video_bytes':video.stat().st_size}
 except Exception as error:
  output[arm]={'status':'error','error':type(error).__name__+': '+str(error)}
print(json.dumps({'snapshot_unix':time.time(),'root':str(root),'arms':output}))
'''
REMOTE_VIDEO = r'''
import pathlib,shutil,sys
video=pathlib.Path(sys.argv[1]).resolve(strict=True)
video.relative_to(pathlib.Path(sys.argv[2]).resolve(strict=True))
if video.stat().st_size!=int(sys.argv[3]): raise ValueError('Video size changed')
with video.open('rb') as source: shutil.copyfileobj(source,sys.stdout.buffer,1024*1024)
'''


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def decode_bundle(bundle):
    return {key: base64.b64decode(bundle['json'][key]['base64'], validate=True) for key in FILES}


def validate_bundle(arm, bundle):
    raw = decode_bundle(bundle)
    values = {key: json.loads(data) for key, data in raw.items()}
    job = 'interval_short_0177_' + arm
    attempt = job + '__a1'
    lane = f'{REMOTE_ROOT}/gpu{ARMS[arm]}'
    v, r, a, t, cfg = (values[k] for k in ('verified', 'result', 'router', 'timing', 'config'))
    require(v.get('passed') is True, 'Verification did not pass')
    for name, item in [('verified', v), ('result', r)]:
        require(item.get('job_id') == job and item.get('attempt_id') == attempt, name + ' identity mismatch')
    require(cfg['root'] == lane and cfg['allowed_root'] == REMOTE_ROOT and cfg['boot_id'] == BOOT,
            'Config root/boot mismatch')
    require(cfg['uid'] == 1004 and cfg['gpu_index'] == ARMS[arm] and arm in cfg['arms'], 'Config owner/lane mismatch')
    m = r['metadata']
    require(m['cohort'] == COHORT and m['task_id'] == 'short_0177' and m['method'] == arm, 'Result cohort/task/method mismatch')
    require(m['benchmark'] == 'IVEBench' and m['source_sha256'] == SOURCE_SHA, 'Result benchmark/source mismatch')
    require(m['seed'] == 2026101701 and m['steps'] == 20 and m['fps'] == 24 and m['valid_frames'] == 60, 'Frozen metadata mismatch')
    require(m['prompt'] == 'Replace the tiger with a lion', 'Official prompt mismatch')
    require(m['geometry'] == {'width': 1312, 'height': 736, 'frames': 73, 'fps': 24}, 'Geometry metadata mismatch')
    manifest = values['manifest']['jobs']
    require(len(manifest) == 1 and manifest[0]['id'] == job, 'Manifest job mismatch')
    expected_meta = json.loads(json.dumps(manifest[0]['metadata']).replace('{attempt_id}', attempt))
    require(m == expected_meta, 'Result metadata differs from its manifest')
    require(m['route_audit'] == f'{lane}/audit/router/{attempt}.json' and m['timing_file'] == f'{lane}/audit/timing/{attempt}.json', 'Audit binding mismatch')
    require(a['run_id'] == attempt and a['schedule'] == arm and a['step_set_zero_based'] == STEPS[arm], 'Router identity/schedule mismatch')
    require(a['completed_forward_calls'] == 20 and a['completed_calls'] == 1000 and a['calls_by_forward'] == [50] * 20, 'Incomplete router')
    require(a['routed_calls'] == len(STEPS[arm]) * 50 and a['routed_by_forward'] == [50 if i in STEPS[arm] else 0 for i in range(20)], 'Routing count mismatch')
    require(a['alpha'] == m['alpha'] == (0.25 if arm == 'global_weak' else 1.0), 'Alpha mismatch')
    require(t['status'] == 'complete' and t['passed'] is True and len(t['per_step_seconds']) == 20, 'Incomplete timing')
    require(all(math.isfinite(x) and x > 0 for x in t['per_step_seconds']), 'Invalid step timing')
    require(v['sampling_seconds'] == t['sampler_wall_seconds'] and v['complete_forwards'] == 20 and v['completed_blocks'] == 1000, 'Verification/timing mismatch')
    require(len(r['files']) == 1 and r['files'][0] == v['video'], 'Result and verification video differ')
    f = r['files'][0]
    require(f['path'] == bundle['video_remote_path'] and f['bytes'] == bundle['video_bytes'], 'Raw-video path/size mismatch')
    PurePosixPath(f['path']).relative_to(PurePosixPath(lane) / 'output')
    stream = next(s for s in f['probe']['streams'] if s.get('codec_type', 'video') == 'video')
    require((stream['width'], stream['height'], int(stream['nb_frames'])) == (1312, 736, 73), 'Raw-video geometry mismatch')
    contract = values['backend_contract']
    backend = contract['backend']
    require(contract['boot_id'] == BOOT and backend in ('cuda', 'triton'), 'Backend contract mismatch')
    counts = v['dispatch_process_cumulative_successful_calls']
    require(counts[backend] > 0 and all(counts.get(k, 0) == 0 for k in ('cuda', 'triton', 'eager') if k != backend), 'Verified backend mismatch')
    require(values['backend']['schema'] == 'h3-backend-dispatch-audit-v1', 'Backend snapshot schema mismatch')
    return raw, values


def inspect_existing(directory, arm):
    item = json.loads((directory / 'COLLECTION.json').read_text())
    require(item['arm'] == arm and item['cohort'] == COHORT and item['remote_root'] == REMOTE_ROOT, 'Existing collection identity mismatch')
    require(item['job_id'] == 'interval_short_0177_' + arm and item['attempt_id'] == item['job_id'] + '__a1', 'Existing collection attempt mismatch')
    for entry in item['artifacts'].values():
        path = Path(entry['path'])
        require(path.parent == directory and path.is_file(), 'Existing artifact path mismatch')
        require(path.stat().st_size == entry['bytes'] and sha_file(path) == entry['sha256'], 'Existing local artifact changed: ' + str(path))
    return item


def save_bundle(arm, bundle, destination):
    raw, values = validate_bundle(arm, bundle)
    final = destination / arm
    with tempfile.TemporaryDirectory(prefix='.' + arm + '-', dir=destination) as staging:
        temp = Path(staging)
        for key, data in raw.items():
            (temp / FILES[key]).write_bytes(data)
        video = temp / 'raw.mp4'
        command = shlex.join(['python3', '-c', REMOTE_VIDEO, bundle['video_remote_path'],
                              f'{REMOTE_ROOT}/gpu{ARMS[arm]}/output', str(bundle['video_bytes'])])
        with video.open('wb') as output:
            subprocess.run(SSH + [command], stdin=subprocess.DEVNULL, stdout=output,
                           stderr=subprocess.PIPE, check=True, timeout=180)
        f = values['result']['files'][0]
        require(video.stat().st_size == f['bytes'] and sha_file(video) == f['sha256'], 'Downloaded video SHA/size mismatch')
        artifacts = {}
        for key, filename in {**FILES, 'video': 'raw.mp4'}.items():
            path = temp / filename
            artifacts[key] = {'path': str(final / filename), 'sha256': sha_file(path), 'bytes': path.stat().st_size,
                              'remote_path': bundle['video_remote_path'] if key == 'video' else bundle['json'][key]['remote_path']}
        item = {'arm': arm, 'status': 'collected', 'cohort': COHORT, 'job_id': values['result']['job_id'],
                'attempt_id': values['result']['attempt_id'], 'remote_host': HOST, 'remote_root': REMOTE_ROOT,
                'remote_lane': f'{REMOTE_ROOT}/gpu{ARMS[arm]}', 'snapshot_unix': bundle['captured_unix'],
                'collected_unix': time.time(), 'video_sha256': f['sha256'], 'artifacts': artifacts,
                'backend_scope': 'backend.json is the service-cumulative snapshot at collection time. verified.json freezes the successful backend counts at this arm verification; later arms may have added calls to the live snapshot.',
                'raw_json_preserved': True, 'remote_mutations': False}
        (temp / 'COLLECTION.json').write_text(json.dumps(item, ensure_ascii=False, indent=2) + '\n')
        require(not final.exists(), 'Collection directory already exists')
        os.rename(temp, final)
    return inspect_existing(final, arm)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arms', nargs='+', choices=list(ARMS), default=list(ARMS))
    args = parser.parse_args()
    destination = Path(__file__).resolve().parent / 'collection'
    destination.mkdir(exist_ok=True)
    lock = (destination / '.collector.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    selected = list(dict.fromkeys(args.arms))
    items, errors, pending = {}, {}, {}
    remaining = {}
    for arm in ARMS:
        directory = destination / arm
        if directory.exists():
            try:
                items[arm] = inspect_existing(directory, arm)
            except Exception as error:
                errors[arm] = type(error).__name__ + ': ' + str(error)
        elif arm in selected:
            remaining[arm] = ARMS[arm]
        else:
            pending[arm] = 'Not selected this invocation'
    if remaining:
        try:
            command = shlex.join(['python3', '-', REMOTE_ROOT, json.dumps(remaining)])
            result = subprocess.run(SSH + [command], input=REMOTE_SNAPSHOT, capture_output=True,
                                    text=True, check=True, timeout=40)
            snapshot = json.loads(result.stdout)
            require(snapshot['root'] == REMOTE_ROOT, 'Unexpected remote root')
            for arm in remaining:
                bundle = snapshot['arms'][arm]
                if bundle['status'] in ('pending', 'unverified'):
                    pending[arm] = bundle['reason']
                elif bundle['status'] == 'error':
                    errors[arm] = bundle['error']
                else:
                    try:
                        items[arm] = save_bundle(arm, bundle, destination)
                    except Exception as error:
                        errors[arm] = type(error).__name__ + ': ' + str(error)
        except Exception as error:
            errors['remote_snapshot'] = type(error).__name__ + ': ' + str(error)
    arm_index = {}
    for arm in ARMS:
        if arm in items:
            item = items[arm]
            arm_index[arm] = {'status': 'completed', 'sha256': item['video_sha256'],
                              **{key: item[key] for key in ('cohort', 'job_id', 'attempt_id', 'artifacts')},
                              **{key: value['path'] for key, value in item['artifacts'].items()}}
        elif arm in errors:
            arm_index[arm] = {'status': 'error', 'reason': errors[arm]}
        else:
            arm_index[arm] = {'status': 'pending', 'reason': pending.get(arm, 'Remote snapshot unavailable')}
    index = {'arms': arm_index, 'schema': 'interval-short0177-local-collection-v1', 'cohort': COHORT,
             'remote_root': REMOTE_ROOT, 'checked_unix': time.time(), 'single_pass': True,
             'collected': items, 'pending': pending, 'errors': errors, 'all_six_collected': len(items) == 6 and not errors}
    path = destination / 'LOCAL_COLLECTION.json'
    temp = path.with_suffix('.tmp.' + str(os.getpid()))
    temp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)
    print(json.dumps({'manifest': str(path), 'collected': list(items), 'pending': pending, 'errors': errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
