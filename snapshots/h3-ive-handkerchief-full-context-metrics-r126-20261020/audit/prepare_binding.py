from pathlib import Path
import json,hashlib,os,time,ast
B=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];P=B/'h3-timing-ive-handkerchief-full-context-r126-20261020';OLD=B/'h3-ive-full-context-metrics-r124-20261020'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def link(p,q):q.parent.mkdir(parents=True,exist_ok=True);os.link(p,q);assert sha(p)==sha(q)
assert not(R/'CONSUMER_FREEZE.json').exists();science=read(P/'configs/scientific_contract.json');n=next(c for c in science['cases']if c['arm']=='native');f=next(c for c in science['cases']if c['arm']=='forced');assert n['source_id']=='long_0059' and n['valid_frame_count']==144 and n['geometry']['frames']==158
old=read(OLD/'configs/contract.json');oldprompt=hashlib.sha256(old['sources'][0]['prompt'].encode()).hexdigest();helpers=[]
for p in (OLD/'scripts').glob('*.py'):
 s=p.read_text().replace('r124','r126').replace('R124','R126').replace('long_0163','long_0059').replace(oldprompt,n['prompt_sha256'])
 s=s.replace('将浅蓝色西装改为黑色，使用原片2.08–8.08秒','在男子手中添加白手帕，使用原片7–13秒')
 ast.parse(s);q=R/'scripts'/p.name;q.parent.mkdir(exist_ok=True);q.write_text(s);helpers.append({'file':str(p),'sha256':sha(p)})
c=old;p=c['sources'][0];p.update(source_id=n['source_id'],run_id=n['run_id'],forced_run_id=f['run_id'],geometry=n['geometry'],prompt_version=n['prompt_version'],prompt=n['prompt'],original_task=n['original_task'],clip=n['clip'],task_scope=n['task_scope'],evaluation_scope=n['evaluation_scope'],valid_frames=144,crop_xywh=n['evaluation_crop_xywh'])
for name,src in [('producer_runtime.json',P/'configs/runtime.json'),('producer_scientific_contract.json',P/'configs/scientific_contract.json')]:link(src,R/'configs'/name)
for key,name in [('source',n['video']),('provenance',n['provenance'])]:
 src=P/'inputs'/name;dst=R/'inputs'/name;link(src,dst);p[key]={'file':str(dst.relative_to(R)),'sha256':sha(dst),'bytes':dst.stat().st_size}
src=P/'inputs/long_0059_original.mp4';dst=R/'inputs'/src.name;link(src,dst);assert sha(dst)==n['original_source']['sha256'];p['original_media']={'file':str(dst),'sha256':sha(dst)}
for arm,row in [('native',n),('forced',f)]:
 src=P/'configs/graphs'/(row['run_id']+'.json');dst=R/'configs/graphs'/src.name;link(src,dst);p['graph_sha256'if arm=='native'else'forced_graph_sha256']=sha(dst)
c.update(schema='r126-native-paired-media-consumer-v1',producer_local=str(P),producer_remote=read(P/'configs/runtime.json')['remote_root'],producer_seal_sha256=sha(P/'deploy_manifest.json'),producer_contract_sha256=sha(P/'configs/scientific_contract.json'),producer_runtime_sha256=sha(P/'configs/runtime.json'),source_order=['long_0059'],fixed_source_denominator=1);save(R/'configs/contract.json',c)
link(P/'design/REFERENCE_EVENT_REVIEW_PLAN.json',R/'configs/SOURCE_EVENT_REVIEW_CUES.json');link(P/'audit/PREVIOUS_SOURCE_EVENT_REVIEW_PLAN.json',R/'configs/PREVIOUS_SOURCE_EVENT_REVIEW_PLAN.json');save(R/'configs/SHARED_CODE.json',{'helpers':helpers,'base_freeze_sha256':sha(OLD/'CONSUMER_FREEZE.json'),'adaptations':['R124 namespace to R126','source and exact full Context-IR prompt binding','144 valid of158 total source frames'],'no_GPU_entry':True})
save(R/'audit/METADATA_BINDING.json',{'producer_seal_sha256':sha(P/'deploy_manifest.json'),'actual_case_domain':{'valid_frames':144,'total_frames':158,'fps':24,'crop_xywh':[16,8,1280,720]},'source_events_are_source_only':True,'reference_image':False})
files={str(q.relative_to(R)):sha(q)for sub in ['scripts','configs','inputs']for q in (R/sub).rglob('*')if q.is_file()and'__pycache__'not in q.parts};save(R/'CONSUMER_FREEZE.json',{'schema':'r126-consumer-input-binding-v1','files':files,'producer_seal_sha256':sha(P/'deploy_manifest.json'),'GPU_entry':False,'created_unix':time.time()});print(json.dumps({'freeze_sha256':sha(R/'CONSUMER_FREEZE.json'),'files':len(files)}))
