"""Seal the prepared CPU candidate; this module never starts a remote job."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]

def main():
    if (ROOT/'CPU_PREPARATION_SEAL.json').exists():
        raise RuntimeError('Original CPU seal is frozen; use prepare_deployment_seal.py for the deployment package')
    for file in ROOT.rglob('*.py'):
        if '__pycache__' not in file.parts:ast.parse(file.read_text(),filename=str(file))
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (ROOT/'audit/CPU_TESTS.log').write_text(result.stdout)
    if result.returncode:raise SystemExit(result.returncode)
    from r112_contract import registry,validate_job
    jobs,order=registry()
    for run in order:validate_job(run)
    files={}
    for folder in ('scripts','extensions','configs','design','source_snapshot','tests','inputs'):
        for file in sorted((ROOT/folder).rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts:
                files[str(file.relative_to(ROOT))]={'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'bytes':file.stat().st_size}
    seal={'schema':'r112-cpu-preparation-seal-v1','root_review_required_before_GPU':True,'GPU_started':False,
          'registered_runs':order,'files':files,'created_unix':time.time(),
          'runtime_scope':'Operator, nodes, graphs and paired-bank checks prepared. Host launch/release lifecycle to be bound after root GPU review.'}
    path=ROOT/'CPU_PREPARATION_SEAL.json';path.write_text(json.dumps(seal,indent=2)+'\n')
    receipt={'passed':True,'syntax_files':len(list(ROOT.rglob('*.py'))),'tests_log_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),
             'seal_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sealed_files':len(files),'CUDA_started':False,'deployed':False}
    (ROOT/'audit/CPU_PREPARATION_RESULT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
