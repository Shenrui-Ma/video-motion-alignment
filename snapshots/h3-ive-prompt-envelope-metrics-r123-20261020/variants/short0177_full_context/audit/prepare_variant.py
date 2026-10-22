from pathlib import Path
import json,hashlib,os,ast
R=Path(__file__).resolve().parents[1];OLD=R.parent/'long0122_full_context';P=Path('/Users/researcher/DevProjects/h3-timing-ive-tiger-lion-r131-20261020')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def link(p,q):q.parent.mkdir(parents=True,exist_ok=True);os.link(p,q)
assert not (R/'CONSUMER_FREEZE.json').exists()
sci=read(P/'configs/scientific_contract.json');n=next(x for x in sci['cases']if x['arm']=='native');f=next(x for x in sci['cases']if x['arm']=='forced')
for p in (OLD/'scripts').glob('*.py'):
 q=R/'scripts'/p.name;q.parent.mkdir(parents=True,exist_ok=True);s=p.read_text().replace('long_0122','short_0177')
 if p.name=='consume_native.py':s=s.replace('鸟类替换完整官方格式','虎替换狮子完整官方格式')
 if p.name=='common.py':s=s.replace('9f7959cf42047e8999e33e702943af8a19599aa075cd9d716eee601866d636b3',n['prompt_sha256'])+"\nSOURCES=('short_0177',)\n"
 ast.parse(s);q.write_text(s)
for x in [n['video'],n['provenance'],n['original_source']]:link(P/'inputs'/x,R/'inputs'/x)
link(OLD/'configs/SHARED_CONSUMER_CODE.json',R/'configs/SHARED_CONSUMER_CODE.json')
c=read(OLD/'configs/contract.json');c.update(producer_local=str(P),producer_remote='/data4/researcher/h3_runs/timing_ive_tiger_lion_r131_20261020',producer_seal_sha256=sha(P/'deploy_manifest.json'),producer_contract_sha256=sha(P/'configs/scientific_contract.json'),producer_runtime_sha256=sha(P/'configs/runtime.json'),source_order=['short_0177'])
p=c['sources'][0];p['geometry']=sci['geometry'];p.update(source_id='short_0177',run_id=n['run_id'],forced_run_id=f['run_id'],prompt=n['prompt'],prompt_version=n['prompt_version'],original_task=n['original_task'],valid_frames=n['valid_frame_count'],task_scope=n['task_scope'],evaluation_scope=n['evaluation_scope'],clip=n['clip'])
for key,file in [('source',n['video']),('provenance',n['provenance'])]:p[key]={'file':'inputs/'+file,'sha256':sha(R/'inputs'/file),'bytes':(R/'inputs'/file).stat().st_size}
p['original_media']={'file':str(R/'inputs'/n['original_source']),'sha256':sha(R/'inputs'/n['original_source'])}
for mode,reg,field in [('native',n,'graph_sha256'),('forced',f,'forced_graph_sha256')]:
 src=P/'configs/graphs'/(reg['run_id']+'.json');link(src,R/'configs/graphs'/src.name);p[field]=sha(src)
for src,dest in [('configs/scientific_contract.json','configs/producer_scientific_contract.json'),('configs/runtime.json','configs/producer_runtime.json'),('design/PREREGISTERED_EVENTS.json','configs/PREREGISTERED_EVENTS.json')]:link(P/src,R/dest)
e=read(P/'design/PREREGISTERED_EVENTS.json');save(R/'configs/SOURCE_EVENT_REVIEW_CUES.json',dict(schema='r123-source-only-event-cues-v1',items=[dict(source_id='short_0177',prepared_frame_brackets={x['id']:x['reference_prepared_frame_interval']for x in e['events']},evidence={'file':str(P/'design/PREREGISTERED_EVENTS.json'),'sha256':sha(P/'design/PREREGISTERED_EVENTS.json')},scope='Source-only frozen before output; no inference window input')]))
save(R/'configs/contract.json',c)
files={str(p.relative_to(R)):sha(p)for d in ['scripts','configs','inputs']for p in (R/d).rglob('*')if p.is_file()and '__pycache__'not in p.parts};save(R/'CONSUMER_FREEZE.json',dict(schema='r123-new-source-full-context-consumer-binding-v1',files=files,code_reuse='SHA-bound original R123 helpers; source/graph/ContextIR prompt binding updated, no numerical code'))
print(sha(R/'CONSUMER_FREEZE.json'))
