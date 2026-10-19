import argparse,json,os,sys
from pathlib import Path
import supervision as s
ROOT=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--run-name',required=True);p.add_argument('--admission',type=Path,required=True);p.add_argument('--root-admitted',action='store_true');a=p.parse_args();s.require(a.root_admitted and a.run_name and all(c.isalnum() or c in '_-' for c in a.run_name),'explicit safe root launch required')
 directory=ROOT/'runs'/a.run_name;directory.mkdir(parents=True,exist_ok=False);(ROOT/'temp').mkdir(exist_ok=True);parent=s.identity(os.getpid());s.require(parent is not None,'supervisor identity absent')
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',TMPDIR=str(ROOT/'temp'),TMP=str(ROOT/'temp'),TEMP=str(ROOT/'temp'))
 s.write_new(directory/'SUPERVISOR.json',{'identity':parent,'admission_sha256':s.sha(a.admission),'manifest_sha256':s.sha(ROOT/'MANIFEST.json')})
 child=s.run_child([sys.executable,str(ROOT/'final_worker.py'),'--directory',str(directory),'--parent-json',json.dumps(parent),'--admission',str(a.admission.resolve())],env,directory,'final_worker',1200,parent)
 import frozen_decode as d
 from gpu_release_gate import wait_after_child
 release=wait_after_child(s.read_json(a.admission)['gpu_uuid'],child,d.assert_idle_gpu,s.identity)
 s.write_new(directory/'RELEASED.json',{'status':'released','child':child,'release':release,'RECOVERY_FINAL_sha256':s.sha(directory/'RECOVERY_FINAL.json')})
if __name__=='__main__':main()
