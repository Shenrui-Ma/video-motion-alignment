from pathlib import Path
import json,hashlib,os,ast
R=Path(__file__).resolve().parents[1];OLD=R.parent/'generic_retention';P=Path('/Users/researcher/DevProjects/h3-timing-ive-prompt-envelope-full-format-r123-20261020')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def link(p,q):q.parent.mkdir(parents=True,exist_ok=True);os.link(p,q)
assert not (R/'CONSUMER_FREEZE.json').exists()
for p in (OLD/'scripts').glob('*.py'):
 q=R/'scripts'/p.name;q.parent.mkdir(parents=True,exist_ok=True);s=p.read_text()
 if p.name=='consume_native.py':s=s.replace('饮酒通用保留要求','饮酒完整官方格式')
 if p.name=='common.py':
  s=s.split('\nGENERIC_RETENTION =')[0]
  s+='''\nFULL_PROMPT_SHA="5ea69610fb7e51081d4bdc30ba4f6ab27dff99f9bef9f0157c541cb2250acad4"\ndef verify_official_prompt(p,graph=None):\n require(p['prompt_version']=='official_context_ir_with_benchmark_captions_and_subject_binding','prompt format label differs')\n require(hashlib.sha256(p['prompt'].encode()).hexdigest()==FULL_PROMPT_SHA,'full Context-IR prompt changed')\n for field in ('source_prompt','edit_prompt','target_prompt'):\n  require(p['original_task'][field] in p['prompt'],'benchmark caption or edit text missing')\n if graph is not None:require(graph['5']['inputs']['prompt']==p['prompt'],'actual graph prompt differs')\n'''
 ast.parse(s);q.write_text(s)
for p in (OLD/'inputs').glob('*'):link(p,R/'inputs'/p.name)
for n in ['SHARED_CONSUMER_CODE.json','SOURCE_EVENT_REVIEW_CUES.json']:link(OLD/'configs'/n,R/'configs'/n)
science=read(P/'configs/scientific_contract.json');native=next(x for x in science['cases'] if x['arm']=='native');forced=next(x for x in science['cases'] if x['arm']=='forced')
c=read(OLD/'configs/contract.json');c.update(producer_local=str(P),producer_remote='/data4/researcher/h3_runs/timing_ive_prompt_envelope_full_format_r123_20261020',producer_seal_sha256=sha(P/'deploy_manifest.json'),producer_contract_sha256=sha(P/'configs/scientific_contract.json'),producer_runtime_sha256=sha(P/'configs/runtime.json'))
p=c['sources'][0];p.update(prompt_version=native['prompt_version'],prompt=native['prompt']);p['original_media']['file']=str(R/'inputs/short_0358_original.mp4')
for arm,registry,field in [('native',native,'graph_sha256'),('forced',forced,'forced_graph_sha256')]:
 src=P/'configs/graphs'/(registry['run_id']+'.json');link(src,R/'configs/graphs'/src.name);p[field]=sha(src)
save(R/'configs/contract.json',c);link(P/'configs/scientific_contract.json',R/'configs/producer_scientific_contract.json');link(P/'configs/runtime.json',R/'configs/producer_runtime.json')
files={str(p.relative_to(R)):sha(p) for d in ['scripts','configs','inputs'] for p in (R/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
save(R/'CONSUMER_FREEZE.json',dict(schema='r123-full-context-consumer-input-binding-v1',files=files,code_reuse='SHA-bound original R123 helpers in isolated namespace; input media hardlinked; exact six-section prompt binding'))
print(sha(R/'CONSUMER_FREEZE.json'))
