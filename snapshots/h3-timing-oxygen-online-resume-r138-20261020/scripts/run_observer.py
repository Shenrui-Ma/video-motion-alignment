"""One immutable observation; bounded memory wait and typed CUDA OOM retries."""
import argparse,json,os,sys,time
from pathlib import Path
from observer_import import t,ROOT

def decode_with_retries(r,request_path,d,b,own,record,*,clock=time.monotonic):
 from gpu_release_gate import wait_own_child_released
 start=clock();resource_deadline=start+t.RESOURCE_WAIT_SECONDS;execution_spent=0.0
 record['decoder_attempts']=[];record['outer_admission_wait_seconds']=0
 admission=t.admission_document(approved=True)
 record['admission_sha256']=t.sha(ROOT/'configs/admission.json');record['admission_record']=admission
 for number in range(1,4):
  t.require(t.sha(request_path)==record['request_sha256'],'request changed before decoder retry')
  t.require(t.request(request_path)==r,'immutable request changed before decoder retry')
  if execution_spent>=780:raise TimeoutError('decoder execution exceeded780seconds')
  wait_start=clock()
  admitted=t.wait_decoder_admission(r['parent'],deadline=resource_deadline,audit_path=d/'observer_admission.jsonl')
  record['outer_admission_wait_seconds']+=clock()-wait_start
  selected_uuid=admitted['uuid']
  label='decoder_attempt%03d'%number;attempt=d/label;attempt.mkdir(exist_ok=False)
  marker=attempt/'decoder_cuda_started.json'
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=selected_uuid,OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',H3_DECODER_RESOURCE_DEADLINE=str(resource_deadline),H3_DECODER_EXECUTION_MARKER=str(marker),H3_DECODER_ATTEMPT_DIRECTORY=str(attempt))
  args=[sys.executable,str(ROOT/'scripts/decode_live_child.py'),r['endpoint_file'],'--request',str(request_path),'--parent-json',json.dumps(own),'--core',b['comfy'],'--runtime-deps',b['runtime_deps'],'--vae',b['vae'],'--expected-vae-sha256',b['vae_sha256'],'--gpu-uuid',selected_uuid,'--output',str(attempt/'native.mp4')]
  row={'attempt':number,'directory':str(attempt),'admission':admitted};record['decoder_attempts'].append(row)
  # Resource waiting is separate from the preserved780s execution budget.
  budget=780-execution_spent
  execution_started=clock()
  try:
   child=t.run_child(args,env,d,label,max(0,resource_deadline-clock())+budget,own,execution_started_path=marker,execution_timeout=budget)
  except t.ChildExitError as error:
   child=error.result;row['child']=child
   marker_row=child.get('execution_start')
   execution_spent+=max(0,clock()-marker_row['started_monotonic']) if marker_row else 0
   if child['returncode']!=t.CUDA_OOM_EXIT:raise
   proof=t.validate_oom_proof(attempt/'decoder_oom.json',child,r,record['request_sha256'])
   row['oom_proof']=proof;row['status']='typed_cuda_oom'
   row['release']=wait_own_child_released(selected_uuid,child,t.identity,audit_path=d/(label+'_release.jsonl'),allow_cuda_oom=True)
   t.record_resource_event(d/'decoder_retry.jsonl',row)
   if execution_spent>780:raise TimeoutError('decoder execution exceeded780seconds')
   if number==3:raise RuntimeError('decoder CUDA OOM after3bounded attempts') from error
   continue
  execution_spent+=max(0,clock()-child['execution_start']['started_monotonic'])
  row['child']=child;row['status']='complete'
  released=wait_own_child_released(selected_uuid,child,t.identity,audit_path=d/(label+'_release.jsonl'));row['release']=released
  if execution_spent>780:raise TimeoutError('decoder execution exceeded780seconds')
  decoded=t.read_json(attempt/'native.json')
  t.require(decoded.get('status')=='complete' and decoded.get('request_sha256')==record['request_sha256'],'successful decoder result binding differs')
  t.require(decoded['snapshot_sha256']==r['endpoint_file_sha256'],'successful decoder endpoint changed')
  for suffix in ('.mp4','.json'):os.link(attempt/('native'+suffix),d/('native'+suffix))
  record.update(decoder=child,decoder_admission=decoded['gpu_admission'],owned_GPU_cards=admitted['owned_GPU_cards'],after_decoder_release=released,decoder_released_before_pose=True,decoder_stage_seconds=clock()-start,decoder_execution_seconds=execution_spent)
  t.record_resource_event(d/'decoder_retry.jsonl',row)
  return
 raise RuntimeError('decoder retry loop exhausted')

def main():
 p=argparse.ArgumentParser();p.add_argument('--request',required=True);a=p.parse_args();r=t.request(a.request);d=Path(a.request).parent
 t.install_lifetime_guard(r['parent']);b=t.bindings(external=True);own=t.identity(os.getpid());start=time.monotonic();record={'status':'running','request_sha256':t.sha(a.request)}
 try:
  decode_with_retries(r,a.request,d,b,own,record)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
  record['pose_process']=t.run_child([sys.executable,str(ROOT/'scripts/pose_live_child.py'),'--request',a.request,'--parent-json',json.dumps(own)],env,d,'pose',840,own)
  for key,path in {'decode':d/'native.json','pose':d/'pose/native.adult.pose.json','observer':d/'observer.json'}.items():record[key]={'file':str(path),'sha256':t.sha(path)}
  record.update(condition_sha256=r['condition_sha256'],reference_sha256=r['reference_sha256'],seed=r['seed'],sigma=r['sigma'])
  record.update(status='complete',request_id=r['request_id'],physical_index=r['physical_index'],nfe_index=r['nfe_index'],endpoint_file_sha256=r['endpoint_file_sha256'],wall_seconds=time.monotonic()-start)
  t.write_new(d/'response.json',record)
 except BaseException as error:
  t.write_new(d/'failure.json',dict(record,status='failed',error=type(error).__name__+': '+str(error),wall_seconds=time.monotonic()-start));raise
if __name__=='__main__':main()
