"""Root-only live admission and exact-generation launch of the sealed R54 batch."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT=Path('/data3/researcher/h3_runs/timing_ivebench_native_r54_20261017')
sys.path.insert(0,str(ROOT/'scripts'))
import service
import preflight

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())

def main(phase):
    assert os.getuid()==1004
    assert sha(ROOT/'deploy_manifest.json')=='159247ee989ea98a4f73efa8aeb0be8c95263aeee79872e65ab8a1dd2a72d9f6'
    manifest=read(ROOT/'deploy_manifest.json')
    for rel,row in manifest['files'].items(): assert sha(ROOT/rel)==row['sha256'],rel
    if phase=='admit_start':
        assert not (ROOT/'processes/service.json').exists()
        hardware=service.gpu_readiness(); processes=service.compute_processes()
        admission=read(ROOT/'configs/admission.json')
        assert admission['permitted_compute_processes']==[]
        service.check_admission(admission,processes,{'queue_running':[],'queue_pending':[]})
        admission['ready_for_launch']=True
        admission['reviewed_unix']=time.time()
        admission['user_max_owned_cards']=2
        service.write_json(ROOT/'audit/root_live_admission.json',dict(hardware=hardware,processes=processes,admission=admission))
        service.write_json(ROOT/'configs/admission.json',admission)
        preflight.check(ROOT,live=True)
        subprocess.run(['python3',str(ROOT/'scripts/launch_remote.py'),'--service-only'],check=True,cwd=ROOT/'scripts',timeout=60)
    elif phase=='go':
        owner=read(ROOT/'processes/service.json'); gate=read(ROOT/'processes/cuda_gate_ready.json')
        service.assert_owned(owner)
        assert gate['pid']==owner['pid'] and gate['identity']==service.external_identity(owner['pid'])
        assert not (ROOT/'processes/cuda_gate_go.json').exists()
        service.gpu_readiness()
        service.check_admission(read(ROOT/'configs/admission.json'),service.compute_processes(),{'queue_running':[],'queue_pending':[]})
        service.write_json(ROOT/'processes/cuda_gate_go.json',gate)
        service.write_json(ROOT/'audit/root_launch_owner.json',dict(service=owner,gate=gate,unix=time.time()))
        print(json.dumps({'pid':owner['pid'],'identity':gate['identity'],'go':True}))
    elif phase=='controller':
        owner=read(ROOT/'processes/service.json');service.assert_owned(owner)
        with urllib.request.urlopen('http://127.0.0.1:8515/object_info/H3TemporalRouter',timeout=10) as response:
            assert 'H3TemporalRouter' in json.load(response)
        subprocess.run(['python3',str(ROOT/'scripts/start_controller.py'),'--pid',str(owner['pid']),'--start-ticks',owner['identity']['start_ticks']],check=True,cwd=ROOT/'scripts',timeout=30)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['admit_start','go','controller']);main(p.parse_args().phase)
