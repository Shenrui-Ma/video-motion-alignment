"""Stage completed actual videos for the reused MF runtime; no model invocation."""
from pathlib import Path
import json,hashlib,os,sys
B=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];PREP=B/'h3-ive-prompt-envelope-metrics-r123-20261020/audit/pending_mf_inputs/READY.json';CACHE=B/'h3-ive-prompt-checks-mf-host9-20261020/cases/short_0358'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def link(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists():os.link(p,q)
 assert sha(p)==sha(q)
assert not(R/'SEAL.json').exists();ready=read(PREP);assert ready['passed']
roles={'r123_generic_retention':('short_0358','retention_native'),'r123_full_context':('short_0358','full_native'),'r122_long0039':('long_0039','native')}
cases={}
for x in ready['records']:
 key,role=roles[x['key']];c=R/'cases'/key;src=x['roles']['source'];target=x['roles']['native']
 for row in [src['full'],src['score'],target['full'],target['score']]:assert sha(Path(row['file']))==row['sha256']
 link(Path(src['full']['file']),c/'source_full.mp4');link(Path(src['score']['file']),c/'source_score.mp4');link(Path(target['full']['file']),c/role/'full.mp4');link(Path(target['score']['file']),c/role/'score.mp4')
 if key not in cases:
  m=dict(schema='existing-official-mf-input-manifest-v1',benchmark='IVEBench',canonical_id=key,valid_frames=x['valid_frames'],evaluation_frames=x['valid_frames'],evaluation_fps=24,crop_xywh=x['crop_xywh'],source_full_sha256=src['full']['sha256'],source_score_sha256=src['score']['sha256'],source_frame_md5=src['decoded_frame_md5'],source_cache=None,selection_sha256=x['consumer_input']['sha256'],targets=[])
  if key=='short_0358':
   report=read(CACHE/'tracks/source/REPORT.json');assert report['passed'] and report['source_prepared_sha256']==m['source_full_sha256'] and report['source_score_sha256']==m['source_score_sha256'];assert report['effective_frame_count']==105 and report['score_frame_indices']==list(range(105)) and report['decoded_frame_md5']==m['source_frame_md5'];assert report['checkpoint_sha256']=='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df';assert report['tracker']=={'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60}
   for f in ['REPORT.json','tracks.npz']:link(CACHE/'tracks/source'/f,c/'tracks/source'/f)
   assert report['tracks_sha256']==sha(c/'tracks/source/tracks.npz');m['source_cache']={'report_sha256':sha(c/'tracks/source/REPORT.json'),'tracks_sha256':report['tracks_sha256']};m['selection_sha256']=report['selection_sha256']
  cases[key]=m
 else:assert cases[key]['source_frame_md5']==src['decoded_frame_md5']
 cases[key]['targets'].append({'role':role,'full_file':role+'/full.mp4','full_sha256':target['full']['sha256'],'score_file':role+'/score.mp4','score_sha256':target['score']['sha256'],'score_frame_md5':target['decoded_frame_md5'],'inventory_bindings':[{'id':x['inventory_id'],'field':'native'}],'actual_consumer_input':x['consumer_input'],'evaluation_indices':list(range(x['valid_frames']))})
for key,m in cases.items():save(R/'cases'/key/'INPUTS.json',m)
job=[]
for key,m in cases.items():
 if m['source_cache'] is None:job.append({'case':key,'role':'source'})
 job.extend({'case':key,'role':x['role']} for x in m['targets'])
save(R/'configs/PLAN.json',{'groups':list(cases),'jobs':job,'unique_targets':sum(len(m['targets']) for m in cases.values()),'status':'UNSEALED_WAITING_ACTUAL_GUIDED_OUTPUTS'})
save(R/'audit/STAGED_INPUTS.json',{'passed':True,'prepared_input_receipt':{'file':str(PREP),'sha256':sha(PREP)},'case_count':len(cases),'completed_generated_targets':3,'source_cache_reused':['short_0358'],'new_source_tracker_required':['long_0039'],'input_manifests':{k:sha(R/'cases'/k/'INPUTS.json') for k in cases},'GPU_started':False,'sealed':False})
print('Staged three actual Native outputs and two source domains; no GPU invocation.')
