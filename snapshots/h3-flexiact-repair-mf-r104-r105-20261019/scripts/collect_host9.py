"""Collect completed .9 MF pairs and verify exact release, tracks, inputs, and scores."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shlex
import subprocess
import tarfile


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path, value): Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main(pair, attempt):
    pair = Path(pair).resolve(); package = pair / 'host9_package'
    runtime = read(package / 'configs/RUNTIME.json'); remote = runtime['remote_root']
    assert attempt.replace('_', '').replace('-', '').isalnum()
    code = 'D=' + repr(remote) + '\nATTEMPT=' + repr(attempt) + '\n' + '''
from pathlib import Path
import hashlib,json,subprocess,tarfile,time
r=Path(D);a=r/'audit'/ATTEMPT
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
done=read(a/'COMPLETE.json');assert done['passed'] and done['all_trackers_released']
nv={int(x.strip()) for x in subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).splitlines() if x.strip()}
released=[]
for method in ('reference','native','guided'):
 p=a/method/'RELEASED.json';v=read(p)
 assert v['passed'] and v['returncode']==0 and v['process_absent'] and v['own_cuda_absent'] and v['peer_registrations_removed']
 assert not Path('/proc',str(v['pid'])).exists() and v['pid'] not in nv
 released.append({'file':str(p),'sha256':sha(p),'pid':v['pid'],'identity':v['identity']})
start=read(a/'STARTED.json');assert not Path('/proc',str(start['pid'])).exists() and start['pid'] not in nv
receipt={'passed':True,'wrapper':start,'wrapper_absent':True,'trackers':released,'own_cuda_absent':True,'unix':time.time()}
receipt_path=a/'SLOT_RELEASE_RECEIPT.json';receipt_path.write_text(json.dumps(receipt,indent=2)+'\\n')
files=[]
for folder in (a,r/'controls',r/'tracks',r/'scores',r/'prepared'):
 files.extend(p for p in folder.rglob('*') if p.is_file() and p.suffix!='.mp4')
files.extend([r/'runtime/official_metric/SOURCE_INPUTS.json',r/'CONSUMER_FREEZE.json'])
manifest={str(p.relative_to(r)):sha(p) for p in sorted(set(files))}
(a/'RETURN_SHA.json').write_text(json.dumps(manifest,indent=2)+'\\n')
with tarfile.open(a/'RESULTS.tar.gz','w:gz') as archive:
 for name in manifest:archive.add(r/name,arcname=name)
 archive.add(a/'RETURN_SHA.json',arcname=str((a/'RETURN_SHA.json').relative_to(r)))
print(json.dumps({'passed':True,'release':receipt,'files':len(manifest)}))
'''
    response = subprocess.run(['ssh', '-o', 'BatchMode=yes', 'H3_SERVER_A', 'python3 -c ' + shlex.quote(code)],
                              capture_output=True, text=True)
    save(pair / 'audit/HOST9_COLLECT_RESPONSE.json', {'returncode': response.returncode,
                                                   'stdout': response.stdout, 'stderr': response.stderr})
    assert response.returncode == 0, response.stderr
    archive = pair / 'HOST9_RESULTS.tar.gz'
    subprocess.run(['scp', '-q', 'H3_SERVER_A:' + remote + '/audit/' + attempt + '/RESULTS.tar.gz', str(archive)], check=True)
    out = pair / 'actual_host9'; out.mkdir(exist_ok=False)
    with tarfile.open(archive) as bundle: bundle.extractall(out, filter='data')
    for name, digest in read(out / 'audit' / attempt / 'RETURN_SHA.json').items():
        assert sha(out / name) == digest, name
    assert sha(out / 'CONSUMER_FREEZE.json') == sha(package / 'CONSUMER_FREEZE.json')
    scores = {key: read(out / 'scores' / key / 'SCORE.json') for key in ('native', 'guided')}
    reports = {key: read(out / 'tracks' / key / 'REPORT.json') for key in ('reference', 'native', 'guided')}
    for key in ('checkpoint_sha256', 'metric_functions_sha256', 'vendor_manifest_sha256',
                'grid_size', 'mask', 'tracks_dtype', 'torch_version', 'cuda_version'):
        assert all(value[key] == reports['reference'][key] for value in reports.values()), key
    inputs = read(pair / 'prepared/MF_INPUTS.json')
    assert reports['reference']['case']['sha256'] == inputs['source_original']['sha256']
    for key, report in reports.items():
        assert report['passed'] and report['tracks_shape'] == [3025, 49, 2]
        assert report['tracks_sha256'] == sha(out / 'tracks' / key / 'tracks.pt')
        assert report['nonfinite_track_values'] == 0
        assert report['grid_size'] == 55 and report['mask'] is None
        assert report['checkpoint_sha256'] == inputs['checkpoint_required_sha256']
        if key != 'reference': assert report['case']['sha256'] == inputs['targets'][key]['sha256']
    for key, score in scores.items():
        assert score['reference_report']['sha256'] == sha(out / 'tracks/reference/REPORT.json')
        assert score['edited_report']['sha256'] == sha(out / 'tracks' / key / 'REPORT.json')
        assert score['actual_generated_video_sha256'] == inputs['targets'][key]['full_sha256']
        assert math.isfinite(score['score'])
        assert score['metric_inputs']['sha256'] == sha(out / 'prepared' / key / 'METRIC_INPUTS.json')
        assert score['evaluation_frames'] == 49 and score['evaluation_fps'] == 8 and not score['cuda_initialized']
    release = out / 'audit' / attempt / 'SLOT_RELEASE_RECEIPT.json'
    summary = {'benchmark': 'FlexiAct', 'case': inputs['case'], 'canonical_motion_id': inputs['canonical_motion_id'],
        'comparison_kind': 'actual_paired_guidance', 'guidance_used': True,
        'score': {key: value['score'] for key, value in scores.items()},
        'evaluation_frames': 49, 'evaluation_fps': 8, 'full_video_valid_frames': 147,
        'source_original_sha256': inputs['source_original']['sha256'],
        'scores': {key: {'file': str(out / 'scores' / key / 'SCORE.json'),
                        'sha256': sha(out / 'scores' / key / 'SCORE.json')} for key in scores},
        'release': {'file': str(release), 'sha256': sha(release)},
        'scope': 'Official author-code MF at 49 original physical timestamps. Task acceptance and visible event timing are reported separately.'}
    save(pair / 'RESULT_VERIFIED.json', summary); print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('pair'); parser.add_argument('--attempt', default='actual_host9_capacity1')
    args = parser.parse_args(); main(args.pair, args.attempt)
