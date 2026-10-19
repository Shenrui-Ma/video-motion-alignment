"""Copy a sealed MF package and validate it on .41 without importing torch."""
import hashlib
import json
import shlex
import subprocess
import sys
import tarfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
seal = json.loads((root / 'SEAL.json').read_text())
cfg = json.loads((root / 'configs/RUNTIME.json').read_text())
remote = cfg['remote_root']
assert remote.startswith('/data4/researcher/h3_runs/ive_')
for rel, digest in seal['files'].items():
    assert sha(root / rel) == digest, rel
runtime = json.loads((root / 'configs/RUNTIME_INHERITANCE.json').read_text())['files']
extra = {'runtime/' + rel: digest for rel, digest in runtime.items()
         if 'runtime/' + rel not in seal['files']}
for rel, digest in extra.items():
    assert sha(root / rel) == digest, rel
archive = root.parent / (root.name + '_passive.tar.gz')
with tarfile.open(archive, 'w:gz') as out:
    for rel in [*seal['files'], *extra, 'SEAL.json']:
        out.add(root / rel, arcname=rel)
host = 'H3_SERVER_B'
remote_archive = remote + '.sealed.tar.gz'
subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                str(archive), host + ':' + remote_archive], check=True)
code = ('REMOTE=' + repr(remote) + '\nARCHIVE=' + repr(remote_archive)
        + '\nSEAL=' + repr(sha(root / 'SEAL.json')) + '\nPYTHON=' + repr(cfg['python']) + '\n') + '''
import hashlib,json,os,subprocess,tarfile,time
from pathlib import Path
r=Path(REMOTE)
resumed=r.exists()
if resumed:
 assert hashlib.sha256((r/'SEAL.json').read_bytes()).hexdigest()==SEAL
 for rel,digest in json.loads((r/'SEAL.json').read_text())['files'].items():
  assert hashlib.sha256((r/rel).read_bytes()).hexdigest()==digest
 assert not list((r/'audit').glob('actual_*'))
else:r.mkdir()
with tarfile.open(ARCHIVE) as t:t.extractall(r,filter='data')
assert hashlib.sha256((r/'SEAL.json').read_bytes()).hexdigest()==SEAL
p=subprocess.run([PYTHON,str(r/'audit/check_package.py'),str(r)],check=True,
    capture_output=True,text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'))
d=json.loads(p.stdout);assert d['passed'] and d['CUDA_started'] is False
d.update(seal_sha256=SEAL,unix=time.time(),GPU_started=False,resumed_matching_passive=resumed)
(r/'audit/PASSIVE_DEPLOYMENT.json').write_text(json.dumps(d,indent=2)+'\\n')
print(json.dumps(d))
'''
result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host,
                         'python3 -c ' + shlex.quote(code)], capture_output=True, text=True)
if result.returncode:
    (root / 'audit/PASSIVE_DEPLOY_ERROR.txt').write_text(result.stdout + result.stderr)
    raise RuntimeError('Inspect audit/PASSIVE_DEPLOY_ERROR.txt; passive deployment failed.')
receipt = json.loads(result.stdout)
(root / 'audit/TARGET_CPU_CHECK.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
