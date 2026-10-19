"""Deploy an unchanged frozen package while copying a verified resident checkpoint."""
from pathlib import Path
import argparse, hashlib, json, shlex, subprocess, tarfile, time

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main(root, resume=False):
    root = Path(root).resolve()
    package = root / 'host41_package'
    config = json.loads((package / 'configs/RUNTIME.json').read_text())
    freeze = json.loads((package / 'CONSUMER_FREEZE.json').read_text())
    assert all(digest(package / name) == value for name, value in freeze['files'].items())
    weights = 'runtime/official_metric/weights/cotracker_stride_4_wind_8.pth'
    expected = 'dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3'
    assert freeze['files'][weights] == expected
    archive = root / 'host41_package_cached.tar.gz'
    names = [*(name for name in freeze['files'] if name != weights), 'CONSUMER_FREEZE.json']
    if resume:
        with tarfile.open(archive) as tar:
            assert set(tar.getnames()) == set(names)
            assert all(hashlib.sha256(tar.extractfile(name).read()).hexdigest() == digest(package / name)
                       for name in names)
    else:
        assert not archive.exists(), 'preserve previous deployment attempt'
        with tarfile.open(archive, 'w:gz') as tar:
            for name in names:
                tar.add(package / name, arcname=name)
    remote = config['remote_root']
    target_archive = remote + '.cached.tar.gz'
    transfer = (['rsync', '-az', '--inplace', '-e', 'ssh -o BatchMode=yes -o ConnectTimeout=12', str(archive),
                 'H3_SERVER_B:' + target_archive] if resume else
                ['scp', '-q', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', str(archive),
                 'H3_SERVER_B:' + target_archive])
    subprocess.run(transfer, check=True, timeout=600)
    values = {'remote': remote, 'archive': target_archive, 'archive_sha': digest(archive),
              'freeze_sha': digest(package / 'CONSUMER_FREEZE.json'), 'weights': weights,
              'weight_sha': expected, 'python': config['python'],
              'resident': '/data4/researcher/h3_runs/flexiact_prompt_control_mf_r90_20261019/' + weights}
    code = 'v=' + repr(values) + '\n' + '''
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tarfile,time
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path(v['remote']);assert not root.exists()
assert sha(v['archive'])==v['archive_sha']
assert sha(v['resident'])==v['weight_sha']
root.mkdir()
with tarfile.open(v['archive']) as tar:tar.extractall(root,filter='data')
target=root/v['weights'];target.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(v['resident'],target)
assert sha(root/'CONSUMER_FREEZE.json')==v['freeze_sha']
assert sha(target)==v['weight_sha']
checked=subprocess.run([v['python'],str(root/'audit/check_package.py'),str(root)],check=True,capture_output=True,text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'))
data=json.loads(checked.stdout)
data.update(freeze_sha256=v['freeze_sha'],unix=time.time(),checkpoint_reused_from=v['resident'],checkpoint_sha256=v['weight_sha'],archive_sha256=v['archive_sha'],GPU_started=False)
(root/'audit/PASSIVE_DEPLOYMENT.json').write_text(json.dumps(data,indent=2))
print(json.dumps(data))
'''
    response = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12',
        'H3_SERVER_B', 'python3 -c ' + shlex.quote(code)], capture_output=True, text=True)
    receipt = {'returncode': response.returncode, 'stdout': response.stdout, 'stderr': response.stderr,
               'archive_bytes': archive.stat().st_size, 'unix': time.time(), 'GPU_started': False}
    (root / 'audit/HOST41_CACHED_DEPLOY_RESPONSE.json').write_text(json.dumps(receipt, indent=2))
    print(response.stdout)
    print(response.stderr)
    assert response.returncode == 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pair_root')
    parser.add_argument('--resume-transfer', action='store_true')
    args = parser.parse_args()
    main(args.pair_root, args.resume_transfer)
