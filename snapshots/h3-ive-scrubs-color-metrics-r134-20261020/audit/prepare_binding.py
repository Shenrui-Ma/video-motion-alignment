from pathlib import Path
import json,hashlib,os,time,ast
B=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];P=B/'h3-timing-ive-scrubs-color-r134-20261020';OLD=B/'h3-ive-book-color-metrics-r128-20261020'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def link(p,q):q.parent.mkdir(parents=True,exist_ok=True);os.link(p,q);assert sha(p)==sha(q)
assert not(R/'CONSUMER_FREEZE.json').exists();science=read(P/'configs/scientific_contract.json');n=next(c for c in science['cases']if c['arm']=='native');f=next(c for c in science['cases']if c['arm']=='forced');assert n['source_id']=='short_0353' and n['valid_frame_count']==50 and n['geometry']['frames']==56
old=read(OLD/'configs/contract.json');oldprompt=hashlib.sha256(old['sources'][0]['prompt'].encode()).hexdigest();helpers=[]
for p in (OLD/'scripts').glob('*.py'):
 s=p.read_text().replace('r128','r134').replace('R128','R134').replace('short_0362','short_0353').replace(oldprompt,n['prompt_sha256'])
 s=s.replace('将蓝色书封面改为红色，使用完整2.68秒原片','将蓝色手术服改为绿色，使用完整原片').replace('提示词用完整Context-IR组织官方原始描述、编辑要求和目标描述。','提示词保留官方编辑原句，并加入参考视频绑定与通用保留要求。')
 if p.name=='common.py':
  s=s[:s.index('def verify_official_prompt')]+'''def verify_official_prompt(p,graph=None):
 require(p['prompt_version']=='IVEBench-edit-with-generic-retention-v1','prompt format label differs')
 require(_hashlib.sha256(p['prompt'].encode()).hexdigest()==EXPECTED_PROMPT_SHA,'frozen task/reference/retention prompt changed')
 require(p['original_task']['edit_prompt'] in p['prompt'],'official edit instruction missing')
 if graph is not None:require(graph['5']['inputs']['prompt']==p['prompt'],'actual graph prompt differs')
''' 
 ast.parse(s);q=R/'scripts'/p.name;q.parent.mkdir(exist_ok=True);q.write_text(s);helpers.append({'file':str(p),'sha256':sha(p)})
c=old;p=c['sources'][0];p.update(source_id=n['source_id'],run_id=n['run_id'],forced_run_id=f['run_id'],geometry=n['geometry'],prompt_version=n['prompt_version'],prompt=n['prompt'],original_task=n['original_task'],clip=n['clip'],task_scope=n['task_scope'],evaluation_scope=n['evaluation_scope'],valid_frames=50,crop_xywh=n['evaluation_crop_xywh'])
for name,src in [('producer_runtime.json',P/'configs/runtime.json'),('producer_scientific_contract.json',P/'configs/scientific_contract.json')]:link(src,R/'configs'/name)
for key,name in [('source',n['video']),('provenance',n['provenance'])]:
 src=P/'inputs'/name;dst=R/'inputs'/name;link(src,dst);p[key]={'file':str(dst.relative_to(R)),'sha256':sha(dst),'bytes':dst.stat().st_size}
src=P/'inputs/short_0353_original.mp4';dst=R/'inputs'/src.name;link(src,dst);assert sha(dst)==n['original_source']['sha256'];p['original_media']={'file':str(dst),'sha256':sha(dst)}
for arm,row in [('native',n),('forced',f)]:
 src=P/'configs/graphs'/(row['run_id']+'.json');dst=R/'configs/graphs'/src.name;link(src,dst);p['graph_sha256'if arm=='native'else'forced_graph_sha256']=sha(dst)
c.update(schema='r134-native-paired-media-consumer-v1',producer_local=str(P),producer_remote=read(P/'configs/runtime.json')['remote_root'],producer_seal_sha256=sha(P/'deploy_manifest.json'),producer_contract_sha256=sha(P/'configs/scientific_contract.json'),producer_runtime_sha256=sha(P/'configs/runtime.json'),source_order=['short_0353'],fixed_source_denominator=1);save(R/'configs/contract.json',c)
link(P/'design/REFERENCE_EVENT_REVIEW_PLAN.json',R/'configs/SOURCE_EVENT_REVIEW_CUES.json');link(P/'audit/SOURCE_EVENTS_BEFORE_OUTPUT.json',R/'configs/SOURCE_EVENTS_BEFORE_OUTPUT.json');save(R/'configs/SHARED_CODE.json',{'helpers':helpers,'base_freeze_sha256':sha(OLD/'CONSUMER_FREEZE.json'),'adaptations':['R128 helper to R134 namespace','source and exact official-edit/reference/generic-retention prompt binding','50 valid of56 total source frames; valid49 repeats original48' ],'no_GPU_entry':True})
save(R/'audit/METADATA_BINDING.json',{'producer_seal_sha256':sha(P/'deploy_manifest.json'),'actual_case_domain':{'valid_frames':50,'total_frames':56,'fps':24,'crop_xywh':[16,8,1280,720]},'source_events_are_source_only':True,'reference_image':False})
files={str(q.relative_to(R)):sha(q)for sub in ['scripts','configs','inputs']for q in (R/sub).rglob('*')if q.is_file()and'__pycache__'not in q.parts};save(R/'CONSUMER_FREEZE.json',{'schema':'r134-consumer-input-binding-v1','files':files,'producer_seal_sha256':sha(P/'deploy_manifest.json'),'GPU_entry':False,'created_unix':time.time()});print(json.dumps({'freeze_sha256':sha(R/'CONSUMER_FREEZE.json'),'files':len(files)}))
