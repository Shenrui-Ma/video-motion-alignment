from pathlib import Path
import json,hashlib,os,time
B=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];P=B/'h3-timing-ive-full-context-r124-20261020';BASE=B/'h3-ive-official-prompt-metrics-r120-20261019';OLD=B/'h3-ive-generic-retention-metrics-r122-20261020'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def link(p,q):q.parent.mkdir(parents=True,exist_ok=True);os.link(p,q);assert sha(p)==sha(q)
assert not(R/'CONSUMER_FREEZE.json').exists();science=read(P/'configs/scientific_contract.json');rows=science['cases'];native=next(x for x in rows if x['arm']=='native');forced=next(x for x in rows if x['arm']=='forced');sid=native['source_id'];assert sid=='long_0163' and native['valid_frame_count']==144 and native['geometry']['frames']==158
helpers=[]
for p in (BASE/'scripts').glob('*.py'):
 h=sha(p);helpers.append({'file':str(p),'sha256':h});code=f'''"""Reuse the verified R120 consumer in the R124 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path({str(p)!r})
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=={h!r}
_code=_shared_bytes.decode().replace('r120','r124').replace('R120','R124')
'''
 if p.name=='preflight.py':code+='''assert _code.count("len(science['cases'])==6")==1
_code=_code.replace("len(science['cases'])==6","len(science['cases'])==2")
'''
 if p.name in ['render_native.py','render_pair.py']:
  old='R124固定3个来源：红酱替换、添加手帕、上衣改黑；1条完整原片、2条六秒片段。全部只输入参考视频。';new='R124将浅蓝色西装改为黑色，使用原片2.08–8.08秒，只输入参考视频。提示词用完整Context-IR组织官方原始描述、编辑要求和目标描述。'
  code+=f'_code=_code.replace({old!r},{new!r})\n'
 code+="exec(compile(_code,str(_shared),'exec'),globals())\n"
 if p.name=='common.py':
  code+=f'''\nSOURCES=('long_0163',)
EXPECTED_PROMPT_SHA={native['prompt_sha256']!r}
def verify_official_prompt(p,graph=None):
 require(p['prompt_version']=='IVEBench-official-fields-full-Context-IR-v1','prompt format label differs')
 require(_hashlib.sha256(p['prompt'].encode()).hexdigest()==EXPECTED_PROMPT_SHA,'full Context-IR prompt changed')
 for field in ('source_prompt','edit_prompt','target_prompt'):
  require(p['original_task'][field] in p['prompt'],'official benchmark field missing: '+field)
 if graph is not None:require(graph['5']['inputs']['prompt']==p['prompt'],'actual graph prompt differs')
'''
 q=R/'scripts'/p.name;q.parent.mkdir(exist_ok=True);q.write_text(code)
c=read(OLD/'configs/contract.json');p=c['sources'][0];p.update(source_id=sid,run_id=native['run_id'],forced_run_id=forced['run_id'],geometry=native['geometry'],prompt_version=native['prompt_version'],prompt=native['prompt'],original_task=native['original_task'],clip=native['clip'],task_scope=native['task_scope'],evaluation_scope=native['evaluation_scope'],valid_frames=144,crop_xywh=native['evaluation_crop_xywh'])
for name,src in [('producer_runtime.json',P/'configs/runtime.json'),('producer_scientific_contract.json',P/'configs/scientific_contract.json')]:link(src,R/'configs'/name)
for key,srcname in [('source',native['video']),('provenance',native['provenance'])]:
 src=P/'inputs'/srcname;dst=R/'inputs'/srcname;link(src,dst);p[key]={'file':str(dst.relative_to(R)),'sha256':sha(dst),'bytes':dst.stat().st_size}
src=P/'inputs'/native['original_source'];dst=R/'inputs'/src.name;link(src,dst);p['original_media']={'file':str(dst),'sha256':sha(dst)}
for arm,row in [('native',native),('forced',forced)]:
 src=P/'configs/graphs'/f"{row['run_id']}.json";dst=R/'configs/graphs'/src.name;link(src,dst);p['graph_sha256' if arm=='native' else 'forced_graph_sha256']=sha(dst)
c.update(schema='r124-native-paired-media-consumer-v1',producer_local=str(P),producer_remote=read(P/'configs/runtime.json')['remote_root'],producer_seal_sha256=sha(P/'deploy_manifest.json'),producer_contract_sha256=sha(P/'configs/scientific_contract.json'),producer_runtime_sha256=sha(P/'configs/runtime.json'),source_order=[sid]);c['sources']=[p];save(R/'configs/contract.json',c)
link(P/'design/REFERENCE_EVENT_REVIEW_PLAN.json',R/'configs/SOURCE_EVENT_REVIEW_CUES.json')
refined=B/'h3-ive-short-source-selection-20261020/source_events_long0163/SOURCE_EVENTS_BEFORE_OUTPUT.json';link(refined,R/'configs/SOURCE_EVENTS_BEFORE_OUTPUT.json')
save(R/'configs/SHARED_CODE.json',{'helpers':helpers,'base_freeze_sha256':sha(BASE/'CONSUMER_FREEZE.json'),'adaptations':['r120 namespace to r124','one source and2-arm contract','exact full Context-IR prompt with three official fields'],'source_media_hardlinked':True,'no_GPU_entry':True})
save(R/'audit/METADATA_ERRATUM.json',{'producer_seal_sha256':sha(P/'deploy_manifest.json'),'field':'acceleration_axes.postprocessing','inherited_text':science['acceleration_axes']['postprocessing'],'actual_case_domain':{'valid_frames':144,'total_frames':158,'fps':24,'crop_xywh':[16,8,1280,720]},'basis':'case geometry, source PTS/provenance and actual gate are authoritative; producer preserved.'})
files={str(q.relative_to(R)):sha(q) for sub in ['scripts','configs','inputs'] for q in (R/sub).rglob('*') if q.is_file()}
save(R/'CONSUMER_FREEZE.json',{'schema':'r124-consumer-input-binding-v1','files':files,'producer_seal_sha256':sha(P/'deploy_manifest.json'),'GPU_entry':False,'created_unix':time.time()})
print(json.dumps({'consumer':str(R),'freeze_sha256':sha(R/'CONSUMER_FREEZE.json'),'files':len(files)}))
