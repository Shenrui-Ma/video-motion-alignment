"""Run the production decoder's CPU validation on the actual failed-gate endpoint."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path('/data3/researcher/h3_runs/timing_ivebench_auto_r55_20261017')
sys.path.insert(0,str(ROOT/'scripts'))
from observer_import import t

def main():
 t.require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','validation requires explicitly hidden CUDA')
 archived=ROOT/'audit/failed_gates/known_endpoint_90_attempt001'
 archived.mkdir(parents=True,exist_ok=False)
 paths=['audit/known_endpoint_90_gate.json','audit/observations/known_endpoint_90','audit/counterfactual/known_endpoint_90']
 inventory={}
 for rel in paths:
  source=ROOT/rel
  t.require(source.exists(),'missing failed evidence: '+rel)
  files=[source] if source.is_file() else sorted(p for p in source.rglob('*') if p.is_file())
  for p in files:inventory[str(p.relative_to(ROOT))]={'sha256':t.sha(p),'bytes':p.stat().st_size}
  destination=archived/rel;destination.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(source),str(destination))
 for rel,row in inventory.items():t.require(t.sha(archived/rel)==row['sha256'],'preserved failure bytes differ')
 t.write_new(archived/'FILE_INVENTORY.json',{'status':'PRESERVED_FAILED_BEFORE_CUDA','original_root':str(ROOT),'files':inventory})
 old=t.read_json(archived/'audit/observations/known_endpoint_90/request.json')
 directory=ROOT/'audit/observations/known_endpoint_cpu_validation';directory.mkdir(exist_ok=False)
 endpoint=ROOT/'audit/counterfactual/known_endpoint_cpu_validation/native019.pt';endpoint.parent.mkdir(exist_ok=False)
 shutil.copyfile(archived/'audit/counterfactual/known_endpoint_90/native019.pt',endpoint)
 owner=t.identity(os.getpid()); t.require(owner is not None,'validation owner unavailable')
 r=dict(old,request_id=directory.name,parent=owner,bindings_sha256=t.sha(ROOT/'configs/observer_bindings.json'),endpoint_file=str(endpoint),endpoint_file_sha256=t.sha(endpoint),created_unix=time.time())
 path=directory/'request.json';t.write_new(path,r)
 b=t.bindings(external=True)
 command=[sys.executable,str(ROOT/'scripts/decode_live_child.py'),str(endpoint),'--request',str(path),'--parent-json',json.dumps(owner,separators=(',',':')),'--validate-only','--core',b['comfy'],'--runtime-deps',b['runtime_deps'],'--vae',b['vae'],'--expected-vae-sha256',b['vae_sha256'],'--gpu-uuid',t.DECODER_UUID,'--output',str(directory/'native.mp4')]
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',TMPDIR=str(ROOT/'temp'))
 with (directory/'validation.log').open('xb') as log:
  child=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,timeout=120)
 t.require(child.returncode==0,'actual decoder --validate-only failed; inspect validation.log')
 result=t.read_json(directory/'validation.log')
 t.require(result['valid'] is True and result['cuda_initialized'] is False,'CPU decoder validation result differs')
 report={'status':'PASS','production_decoder_sha256':t.sha(ROOT/'scripts/decode_live_child.py'),'protocol_sha256':t.PROTOCOL_SHA,'bindings_sha256':t.sha(ROOT/'configs/observer_bindings.json'),'actual_endpoint_sha256':t.sha(endpoint),'request_sha256':t.sha(path),'failed_attempt_inventory_sha256':t.sha(archived/'FILE_INVENTORY.json'),'validation':result,'validation_log_sha256':t.sha(directory/'validation.log'),'model_forward_calls':0,'vae_forward_calls':0}
 t.write_new(ROOT/'audit/CPU_DECODER_VALIDATE_v4c.json',report)
 print(json.dumps({k:v for k,v in report.items() if k!='validation'},indent=2))
if __name__=='__main__':main()
