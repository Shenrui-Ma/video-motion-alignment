"""Bounded completed-case CPU proof and score export; batch denominator stays5."""
import argparse,os,shutil,subprocess,sys
from pathlib import Path
from contract import *
import remote_consume as consumer
P=consumer.P;ROOT=consumer.ROOT

def case_for(run):
 plan=read(HERE.parents[1]/'configs/recovery/execution_plan.json')
 require(run in plan['new_runs'],'case is external or outside the four new executions')
 rows=[c for c in P['cases'] if c['run_id']==run]
 require(len(rows)==1,'run outside fixed five cases');return rows[0]

def validate_partial_gate(value,run):
 require(value.get('status')=='pass' and value.get('partial_batch') is True and value.get('planned_denominator')==5 and value.get('verified_runs')==[run],'single-case runtime proof differs')
 require(len(value.get('cases',[]))==1 and value['cases'][0]['run']==run,'single-case runtime denominator differs')

def completed(arc,case):
 ready=read(arc/'CASE_READY.json');require(ready['partial_batch'] is True and ready['planned_denominator']==5 and ready['run_id']==case['run_id'],'partial result identity')
 require(sha(arc/'FILE_INVENTORY.json')==ready['file_inventory_sha256'] and sha(arc/'CASE_RUNTIME_GATE.json')==ready['runtime_gate_sha256'],'partial proof changed')
 validate_partial_gate(read(arc/'CASE_RUNTIME_GATE.json'),case['run_id'])
 final=arc/'final'/case['run_id'];files=read(final/'CASE_FILES.json');require(sha(final/'CASE_FILES.json')==ready['case_files_sha256'],'partial case inventory changed')
 for rel,digest in files.items():require(sha(safe(final,rel))==digest,'partial case output changed')
 check_case_summary(read(final/'SUMMARY.json'),case)
 return ready

def snapshot(case):
 consumer.bound();arc=HERE/'completed_cases'/case['run_id']
 if (arc/'CASE_READY.json').exists():return {'status':'complete','result':completed(arc,case)}
 require(not arc.exists(),'partial case directory requires inspection')
 hp=ROOT/'logs'/f'{case["run_id"]}_history.json';jp=ROOT/'logs'/f'{case["run_id"]}_job.json'
 h=read(hp) if hp.exists() else {};j=read(jp) if jp.exists() else {}
 if h.get('status',{}).get('status_str')=='error' or j.get('status') in ('error','unknown_missing','submission_uncertain'):return {'status':'failed','run':case['run_id']}
 if not (h.get('status',{}).get('completed') is True and h['status']['status_str']=='success' and j.get('status')=='success'):return {'status':'pending','run':case['run_id']}
 files=consumer.inventory([case]);token=canonical_sha([{'rel':relative(ROOT,p),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'json_sha':sha(p) if p.suffix=='.json' else None} for p in files])
 return {'status':'success_files_present','token':token,'run':case['run_id']}

def release(case,token):
 with consumer.locked():
  owner=consumer.bound();require(snapshot(case)['token']==token,'single-case completion changed');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
  arc=HERE/'completed_cases'/case['run_id'];require(not arc.exists(),'partial case directory requires inspection')
  files=consumer.inventory([case]);inv={relative(ROOT,p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in files};arc.mkdir(parents=True)
  for p in files:
   dest=safe(arc,relative(ROOT,p));dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);require(sha(dest)==sha(p)==inv[relative(ROOT,p)]['sha256'],'case input changed during copy')
  save(arc/'FILE_INVENTORY.json',inv)
  with (arc/'verify_case.log').open('x') as log:
   command=[sys.executable,str(ROOT/'scripts/verify_completed.py'),'--root',str(ROOT),'--allow-resident','--run',case['run_id'],'--output',str(arc/'CASE_RUNTIME_GATE.json')]
   r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),timeout=600)
  require(r.returncode==0,'single-case runtime verifier failed');validate_partial_gate(read(arc/'CASE_RUNTIME_GATE.json'),case['run_id'])
  summary=consumer.evaluate_case(case,arc=arc,runtime_gate_name='CASE_RUNTIME_GATE.json');dest=arc/'final'/case['run_id']
  save(dest/'CASE_FILES.json',{str(x.relative_to(dest)):sha(x) for x in dest.rglob('*') if x.is_file() and x.name!='CASE_FILES.json'})
  # Recheck every copied input against its producer after independent replay/export.
  verify_phase_dependencies(ROOT,arc,inv)
  ready={'status':'case_ready','partial_batch':True,'planned_denominator':5,'run_id':case['run_id'],'owner':owner,'file_inventory_sha256':sha(arc/'FILE_INVENTORY.json'),'runtime_gate_sha256':sha(arc/'CASE_RUNTIME_GATE.json'),'case_files_sha256':sha(dest/'CASE_FILES.json'),'metric_inputs':str(dest/'METRIC_INPUTS.json'),'metric_inputs_sha256':sha(dest/'METRIC_INPUTS.json'),'root_release_allowed':False,'batch_complete':False,'summary':summary}
  save(arc/'CASE_READY.json',ready)
  save(arc/'DERIVED_FILES.json',{str(x.relative_to(arc)):sha(x) for x in arc.rglob('*') if x.is_file() and str(x.relative_to(arc)) not in inv and x.name not in ('FILE_INVENTORY.json','DERIVED_FILES.json')})
  completed(arc,case);return ready

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['snapshot','release']);ap.add_argument('--run',required=True);ap.add_argument('--token');a=ap.parse_args()
 for rel,digest in read(HERE/'FREEZE.json')['files'].items():require(sha(HERE/rel)==digest,'consumer code changed')
 case=case_for(a.run);result=snapshot(case) if a.mode=='snapshot' else release(case,a.token)
 print(json.dumps(result,allow_nan=False))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
