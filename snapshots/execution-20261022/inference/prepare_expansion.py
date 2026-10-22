import json,copy,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];P=R/'inference/package';tasks=json.loads((R/'expanded_catalog.json').read_text())['tasks']
base=json.loads((P/'jobs.json').read_text());base['jobs']=[j for j in base['jobs'] if not j['id'].startswith('expand_')]
lanes={'host41':base,'host9a':{'jobs':[]},'host9b':{'jobs':[]}}
for i,t in enumerate(tasks):
 lane='host41' if i%2==0 else ('host9a' if i%4==1 else 'host9b')
 remote='/data4/researcher/h3_runs/benchmark_schedule_20261022' if lane=='host41' else '/home/researcher/h3_runs/benchmark_schedule_20261022_'+lane
 g=json.loads(Path(t['graph_template']).read_text())
 old={k:v for k,v in g['5']['inputs'].items() if k in ['clip','vae','ref_video','ref_image','width','height','length']};old['prompt']=t['recommended_prompt'];g['5']={'class_type':'H3StudyReference','inputs':old}
 for k in ['51','52']:g.pop(k,None)
 g['6']={'class_type':'RandomNoise','inputs':{'noise_seed':t['seed']}}
 g['7']['inputs'].update(model=['52',0],conditioning=['5',0]);g['10']['inputs']['latent_image']=['5',1]
 for method in ['native','global_weak']:
  a=copy.deepcopy(g);jid=f'expand_{t["task_id"]}_{method}';p=a['50']['inputs'];p.update(model=['41',0],positive=['5',0],mode='native' if method=='native' else 'mass_preserve',alpha=.25 if method=='global_weak' else 1.,radius=0,time_offset=0,start_frame=0,end_frame=t['valid_frames']-1,block_start=0,block_end=50,step_start=0,step_end=20,run_id='{attempt_id}',audit_dir=remote+'/audit/router',schedule=method);a['50']['class_type']='H3StudySchedule'
  a['52']={'class_type':'H3StudyTiming','inputs':{'model':['50',0],'run_id':'{attempt_id}','output_dir':remote+'/audit/timing'}};a['14']['inputs']['filename_prefix']=jid+'/{attempt_id}'
  target=P if lane=='host41' else R/'inference'/lane
  (target/'graphs').mkdir(parents=True,exist_ok=True);(target/'input').mkdir(exist_ok=True)
  (target/'graphs'/f'{jid}.json').write_text(json.dumps(a,ensure_ascii=False,indent=2))
  dest=target/'input'/t['graph_input_names']['video']
  if not dest.exists():shutil.copy2(t['reference_video'],dest)
  lanes[lane]['jobs'].append({'id':jid,'graph':f'graphs/{jid}.json','expected_output_prefix':jid+'/','progress_file':remote+'/logs/comfy.log','metadata':{**t,'method':method,'timing_file':remote+'/audit/timing/{attempt_id}.json','source_video':remote+'/input/'+t['graph_input_names']['video'],'host':'H3_SERVER_B' if lane=='host41' else 'H3_SERVER_A','remote_root':remote,'steps':20}})
for lane,manifest in lanes.items():
 target=P if lane=='host41' else R/'inference'/lane
 tmp=target/'jobs.json.tmp';tmp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));tmp.replace(target/'jobs.json');print(lane,len(manifest['jobs']))
