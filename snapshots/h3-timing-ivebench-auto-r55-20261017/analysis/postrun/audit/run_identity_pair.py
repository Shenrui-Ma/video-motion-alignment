"""CPU-only paired media proof using released inputs and existing locks."""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import remote_consume as consumer
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def main():
 p=argparse.ArgumentParser();p.add_argument('--pair',required=True);a=p.parse_args()
 case=next(c for c in consumer.P['cases'] if c['source_id']==a.pair)
 auto=HERE.parent/'completed_cases'/case['run_id'];native=Path(case['parent_root'])/'analysis/postrun/captured/batch'
 am=auto/'final'/case['run_id']/'METRIC_INPUTS.json';nm=native/'final'/case['parent_run']/'METRIC_INPUTS.json'
 out=HERE/'media_identity'/a.pair
 with consumer.locked():
  av=read(am);nv=read(nm);ready=read(auto/'CASE_READY.json')
  assert ready['metric_inputs_sha256']==sha(am) and ready['summary']['passed']
  for key in ('source_original','source_prepared_video','source_score_video','source_preparation_record'):
   assert av[key]['sha256']==nv[key]['sha256']
   for value in (av[key],nv[key]):assert sha(value['file'])==value['sha256']
  assert av['score_frame_indices']==nv['score_frame_indices'] and av['input_to_original_frame']==nv['input_to_original_frame']
  runtime=Path('/data3/researcher/h3_runs/ivebench_official_metric_20261017');freeze=runtime/'RUNTIME_FREEZE_HOST41.json'
  for domain,n in [('full_video',90),('score_video',case['valid_frame_count'])]:
   target=out/(domain+'.json')
   if target.exists():
    old=read(target);assert old['left']==nv['edited']['native'][domain] and old['right']==av['edited']['auto'][domain]
    continue
   command=[sys.executable,str(HERE/'prove_media_identity.py'),'--benchmark','ivebench','--runtime',str(runtime),'--freeze',str(freeze),'--freeze-sha256','d46b5c807c56aeb39e219e71271c7e5f050873ee74c5fe342988a3c1cb63dd45','--frames',str(n),'--fps','24','--output',str(target)]
   for which,value in [('left',nv['edited']['native'][domain]),('right',av['edited']['auto'][domain])]:command+=['--'+which,value['file'],'--'+which+'-sha256',value['sha256']]
   subprocess.run(command,check=True,timeout=120)
  ac=read(auto/'audit/x0'/case['run_id']/'manifest.json')['final_sampler_result'];nc=read(native/'audit/x0'/case['parent_run']/'manifest.json')['final_sampler_result']
  result={'schema':'released-auto-native-media-comparison-v1','pair_id':a.pair,'partial_batch':True,'planned_denominator':5,'auto_metric_inputs':{'file':str(am),'sha256':sha(am)},'native_metric_inputs':{'file':str(nm),'sha256':sha(nm)},'case_ready':{'file':str(auto/'CASE_READY.json'),'sha256':sha(auto/'CASE_READY.json')},'all_off':ready['summary']['active_denoising_indices']==[],'final_latent_signatures':{'auto':ac,'native':nc},'proofs':{k:{'file':str(out/(k+'.json')),'sha256':sha(out/(k+'.json')),'exact':read(out/(k+'.json'))['comparison']['exact']} for k in ('full_video','score_video')},'score_reused':False}
  path=out/'SUMMARY.json'
  if path.exists():assert read(path)==result
  else:path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
  print(json.dumps({'summary':str(path),'sha256':sha(path),'proofs':result['proofs']}))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('ONLINE_PRIORITY_OR_CPU_LOCK');raise SystemExit(75)
