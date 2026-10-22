"""Upload only this new sealed package; run CPU tests and actual node import."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
sid = sys.argv[1]
case = HERE / "cases" / sid
runtime = json.loads((case / "configs/runtime.json").read_text())
remote = runtime["remote_root"]
seal = json.loads((case / "deploy_manifest.json").read_text())
archive = HERE / (sid + "_package.tar.gz")
with tarfile.open(archive, "w:gz") as t:
    for name in list(seal["files"]) + ["deploy_manifest.json"]:
        t.add(case / name, arcname=name, recursive=False)
ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
       "-o", "ProxyCommand=none", "H3_SERVER_A"]
with archive.open("rb") as stream:
    subprocess.run(ssh + ["umask 077; mkdir -p " + shlex.quote(remote) +
                         "; tar -xzf - -C " + shlex.quote(remote)], stdin=stream, check=True)
script = "ROOT=" + repr(remote) + "\nRUNTIME=" + repr(runtime) + "\n" + r'''
from pathlib import Path
import os,subprocess,json,hashlib
p=Path(ROOT)
for name in ['input','output','temp','user','logs','processes','custom_nodes']:
 (p/name).mkdir(exist_ok=True)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONPATH=RUNTIME['dependencies'],
 PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
for label,argv in [('CPU_TESTS',[RUNTIME['python'],'-m','unittest','discover','-s',str(p/'tests'),'-v']),
                   ('CPU_VALIDATE',[RUNTIME['python'],str(p/'scripts/remote_cpu_validate.py')])]:
 r=subprocess.run(argv,cwd=p,env=env,text=True,capture_output=True)
 (p/'audit'/('TARGET_'+label+'.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(label+': '+(r.stdout+r.stderr)[-5000:])
print(json.dumps({'passed':True,'root':ROOT,'GPU_started':False,
 'seal_sha256':hashlib.sha256((p/'deploy_manifest.json').read_bytes()).hexdigest()}))
'''
result = subprocess.run(ssh + ["python3 -"], input=script, text=True, capture_output=True)
(case / "audit/DEPLOY_CPU.log").write_text(result.stdout + result.stderr)
print(result.stdout)
if result.returncode:
    print(result.stderr[-6000:])
    raise SystemExit(result.returncode)
for name in ("TARGET_CPU_TESTS.log", "RUNTIME_IMPORT_SMOKE.json", "TARGET_CPU_VALIDATION.json"):
    subprocess.run(["scp", "-o", "ProxyCommand=none", "H3_SERVER_A:" + remote + "/audit/" + name,
                    str(case / "audit" / name)], check=True)
