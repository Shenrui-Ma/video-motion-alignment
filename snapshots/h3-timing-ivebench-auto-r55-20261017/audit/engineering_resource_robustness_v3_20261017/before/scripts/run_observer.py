"""One immutable observation; waits for GPU without holding the CPU lock."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from observer_import import t,ROOT

def own_gpus():
 raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=10)
 result=[]
 for line in raw.splitlines():
  gpu,pid=[p.strip() for p in line.split(',')];result.append({'gpu_uuid':gpu,'pid':int(pid)})
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--request',required=True);a=p.parse_args();r=t.request(a.request);d=Path(a.request).parent
 t.install_lifetime_guard(r['parent']);b=t.bindings(external=True);own=t.identity(os.getpid());start=time.monotonic();record={'status':'running','request_sha256':t.sha(a.request)}
 try:
  while True:
   t.require(t.alive(r['parent']),'sampler exited waiting decoder admission')
   try:
    record['decoder_admission']=t.separate_decoder_admission(r['parent']);break
   except ValueError as error:
    if str(error)!='decoder GPU lacks idle headroom':raise
    if time.monotonic()-start>600:raise TimeoutError('decoder memory headroom unavailable')
    time.sleep(1)
  admission=t.admission_document(approved=True)
  record['admission_sha256']=t.sha(ROOT/'configs/admission.json')
  record['admission_record']=admission
  record['owned_GPU_cards']=t.validate_owned_gpu_limit(own_gpus(),admission['permitted_compute_processes'])
  record['gpu_wait_seconds']=time.monotonic()-start
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=t.DECODER_UUID,OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
  args=[sys.executable,str(ROOT/'scripts/decode_live_child.py'),r['endpoint_file'],'--request',a.request,'--parent-json',json.dumps(own),'--core',b['comfy'],'--runtime-deps',b['runtime_deps'],'--vae',b['vae'],'--expected-vae-sha256',b['vae_sha256'],'--gpu-uuid',t.DECODER_UUID,'--output',str(d/'native.mp4')]
  record['decoder']=t.run_child(args,env,d,'decoder',180,own)
  # A new unrelated process after our exit is never killed. Verify our child identity is gone.
  t.require(not t.alive(record['decoder']['process']),'decoder still live before pose')
  record['decoder_released_before_pose']=True
  from gpu_release_gate import wait_after_child
  record['after_decoder_admission']=wait_after_child(t.DECODER_UUID,record['decoder'],lambda uuid:t.separate_decoder_admission(r['parent'],uuid),t.identity)
  env['CUDA_VISIBLE_DEVICES']=''
  record['pose_process']=t.run_child([sys.executable,str(ROOT/'scripts/pose_live_child.py'),'--request',a.request,'--parent-json',json.dumps(own)],env,d,'pose',840,own)
  for key,path in {'decode':d/'native.json','pose':d/'pose/native.pose.json','observer':d/'observer.json'}.items():record[key]={'file':str(path),'sha256':t.sha(path)}
  record.update(condition_sha256=r['condition_sha256'],reference_sha256=r['reference_sha256'],seed=r['seed'],sigma=r['sigma'])
  record.update(status='complete',request_id=r['request_id'],physical_index=r['physical_index'],nfe_index=r['nfe_index'],endpoint_file_sha256=r['endpoint_file_sha256'],wall_seconds=time.monotonic()-start)
  t.write_new(d/'response.json',record)
 except BaseException as error:
  t.write_new(d/'failure.json',dict(record,status='failed',error=type(error).__name__+': '+str(error),wall_seconds=time.monotonic()-start));raise
if __name__=='__main__':main()
