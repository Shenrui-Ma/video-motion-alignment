"""CPU validation and a new deployment seal; never deploys or starts a GPU."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]

def main():
    require_absent=ROOT/'processes/service.json'
    if require_absent.exists():raise RuntimeError('service record exists; preparation sealed before execution only')
    python_files=list(ROOT.rglob('*.py'))
    for path in python_files:ast.parse(path.read_text(),filename=str(path))
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='')
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (ROOT/'audit/DEPLOYMENT_CPU_TESTS.log').write_text(result.stdout)
    if result.returncode:raise SystemExit(result.returncode)
    from preflight import check
    from execution_gate import seal,verify_seal
    contract=check(ROOT);value=seal(ROOT);verify_seal(ROOT)
    receipt={'schema':'r112-deployment-preparation-result-v1','passed':True,'syntax_files':len(python_files),
             'tests_log_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),
             'source_cpu_seal_sha256':value['source_cpu_seal_sha256'],
             'deployment_seal_sha256':hashlib.sha256((ROOT/'deploy_manifest.json').read_bytes()).hexdigest(),
             'sealed_files':len(value['files']),'contract':contract,'GPU_started':False,'deployed':False,
             'root_review_required':True,'created_unix':time.time()}
    (ROOT/'audit/DEPLOYMENT_PREPARATION_RESULT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
