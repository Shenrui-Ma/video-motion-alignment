"""Stage and validate a frozen .9 package; this script has no GPU launch action."""
from pathlib import Path
import argparse, hashlib, json, shlex, subprocess, tarfile

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main(root):
    root = Path(root).resolve()
    package = root / 'host9_package'
    freeze = json.loads((package / 'CONSUMER_FREEZE.json').read_text())
    runtime = json.loads((package / 'configs/RUNTIME.json').read_text())
    assert runtime['GPU_started'] is False and runtime['GPU_launch_entrypoint_created'] is False
    assert all(sha(package / name) == value for name, value in freeze['files'].items())
    checkpoint = 'runtime/official_metric/weights/cotracker_stride_4_wind_8.pth'
    archive = root / 'host9_cpu_package.tar.gz'
    assert not archive.exists(), 'preserve previous deployment'
    with tarfile.open(archive, 'w:gz') as tar:
        for name in [*(name for name in freeze['files'] if name != checkpoint), 'CONSUMER_FREEZE.json']:
            tar.add(package / name, arcname=name)
    remote = runtime['remote_root']
    subprocess.run(['rsync', '-az', '--inplace', '-e', 'ssh -o BatchMode=yes -o ConnectTimeout=12',
                    str(archive), 'H3_SERVER_A:' + remote + '.cpu.tar.gz'], check=True, timeout=600)
    values = {'remote': remote, 'archive_sha256': sha(archive), 'freeze_sha256': sha(package / 'CONSUMER_FREEZE.json'),
              'python': runtime['python'], 'checkpoint': checkpoint, 'checkpoint_sha256': freeze['files'][checkpoint],
              'resident': '/data5/researcher/h3_runs/flexiact_official_metric_20261017/weights/cotracker_stride_4_wind_8.pth'}
    code = 'v=' + repr(values) + '\n' + '''
from pathlib import Path
import hashlib,importlib.metadata,json,os,shutil,subprocess,tarfile,time
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=Path(v['remote']);assert not r.exists()
archive=Path(v['remote']+'.cpu.tar.gz');assert sha(archive)==v['archive_sha256']
assert sha(v['resident'])==v['checkpoint_sha256']
r.mkdir()
with tarfile.open(archive) as tar:tar.extractall(r,filter='data')
target=r/v['checkpoint'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(v['resident'],target)
assert sha(r/'CONSUMER_FREEZE.json')==v['freeze_sha256']
q=subprocess.run([v['python'],str(r/'audit/check_package.py'),str(r)],capture_output=True,text=True,check=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'))
d=json.loads(q.stdout);d.update(remote=str(r),freeze_sha256=v['freeze_sha256'],checkpoint_sha256=sha(target),versions={k:importlib.metadata.version(k) for k in ['torch','numpy','scipy','opencv-python']},unix=time.time(),GPU_started=False)
(r/'audit/HOST9_CPU_READY.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
'''
    response = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', 'H3_SERVER_A',
        runtime['python'] + ' -c ' + shlex.quote(code)], capture_output=True, text=True)
    receipt = {'returncode': response.returncode, 'stdout': response.stdout, 'stderr': response.stderr,
               'GPU_started': False, 'archive_bytes': archive.stat().st_size}
    (root / 'audit/HOST9_CPU_DEPLOY_RESPONSE.json').write_text(json.dumps(receipt, indent=2))
    print(response.stdout)
    print(response.stderr)
    assert response.returncode == 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pair_root')
    main(parser.parse_args().pair_root)
