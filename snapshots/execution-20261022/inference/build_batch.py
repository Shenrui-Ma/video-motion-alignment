"""Prepare isolated six-setting replication using the frozen R150 router."""
import copy,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'inference/package'
REMOTE='/data4/research-user/h3_runs/benchmark_schedule_20261022'
TEMPLATE=Path('/workspace/research-user/DevProjects/h3-guidance-schedule-r150-20261021/final_global_host41/cases/long_0039')
def write(p,d):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
for d in ['input','output','logs','temp','user','graphs','custom_nodes/H3Study','scripts','audit/timing','audit/router']:(OUT/d).mkdir(parents=True,exist_ok=True)
for name in ['core.py','layout.py','schedule.py']:
 shutil.copy2(TEMPLATE/'extensions/H3TemporalRouter'/name,OUT/'custom_nodes/H3Study'/name)
p=OUT/'custom_nodes/H3Study/schedule.py';s=p.read_text();s=s.replace('SCHEDULES = {','SCHEDULES = {"fixed": tuple(range(6, 15)), "native": (), ');p.write_text(s)
for name in ['compatibility_bootstrap.py','int8_row_chunking.py','backend_dispatch_audit.py']:
 shutil.copy2(TEMPLATE/'scripts'/name,OUT/'scripts'/name)
shutil.copy2(ROOT/'inference/study_nodes.py',OUT/'custom_nodes/H3Study/__init__.py')
tasks=json.loads((ROOT/'task_catalog.json').read_text())['tasks']
# Short doctor first provides a production-shape throughput measurement.
tasks.sort(key=lambda t:t['geometry']['frames'])
jobs=[]
for t in tasks:
 tid=t['task_id'];g=json.loads(Path(t['graph_template']).read_text())
 for role, key in [('reference_video','video'),('reference_image','image')]:
  if t.get(role):shutil.copy2(t[role],OUT/'input'/t['graph_input_names'][key])
 old=g['5']['inputs'];old={k:v for k,v in old.items() if k in ['clip','vae','ref_video','ref_image','width','height','length']}
 old['prompt']=t['recommended_prompt'];g['5']={'class_type':'H3StudyReference','inputs':old}
 for k in ['51','52']:g.pop(k,None)
 g['6']={'class_type':'RandomNoise','inputs':{'noise_seed':t['seed']}}
 g['7']['inputs'].update(model=['52',0],conditioning=['5',0]);g['10']['inputs']['latent_image']=['5',1]
 for method in ['native','fixed','early','late','split','global_weak']:
  a=copy.deepcopy(g);jid=f'new_{tid}_{method}'
  p=a['50']['inputs'];p.update(model=['41',0],positive=['5',0],mode='native' if method=='native' else 'mass_preserve',alpha=.25 if method=='global_weak' else 1.,radius=0,time_offset=0,start_frame=0,end_frame=t['valid_frames']-1,block_start=0,block_end=50,step_start=0,step_end=20,run_id='{attempt_id}',audit_dir=REMOTE+'/audit/router',schedule=method)
  a['50']['class_type']='H3StudySchedule'
  a['52']={'class_type':'H3StudyTiming','inputs':{'model':['50',0],'run_id':'{attempt_id}','output_dir':REMOTE+'/audit/timing'}}
  a['14']['inputs']['filename_prefix']=jid+'/{attempt_id}'
  write(OUT/'graphs'/f'{jid}.json',a)
  meta={**t,'method':method,'timing_file':REMOTE+'/audit/timing/{attempt_id}.json','steps':20,'prompt':t['recommended_prompt'],'source_video':REMOTE+'/input/'+t['graph_input_names']['video'],'reference_image_remote':REMOTE+'/input/'+t['graph_input_names']['image'] if t.get('reference_image') else None}
  jobs.append({'id':jid,'graph':'graphs/'+jid+'.json','expected_output_prefix':jid+'/','metadata':meta})
write(OUT/'jobs.json',{'schema':'h3-benchmark-six-settings-v1','jobs':jobs,'planned_count':len(jobs),'notes':['20 step Euler; same seed/prompt/geometry for every setting.','Frozen R150 core and layout; phase0; no RGB observer.','New cases route all valid video bins consistently.','Timing wrapper records synchronized sampler call and each callback; no intermediate x0 storage.']})
write(OUT/'provenance.json',{'parent':str(TEMPLATE),'original_core_sha256':hashlib.sha256((TEMPLATE/'extensions/H3TemporalRouter/core.py').read_bytes()).hexdigest(),'copied_core_sha256':hashlib.sha256((OUT/'custom_nodes/H3Study/core.py').read_bytes()).hexdigest(),'jobs':len(jobs)})
print(json.dumps({'package':str(OUT),'jobs':len(jobs),'input_bytes':sum(x.stat().st_size for x in (OUT/'input').iterdir())}))
