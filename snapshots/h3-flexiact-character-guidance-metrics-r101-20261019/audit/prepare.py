from pathlib import Path
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1];P=ROOT.parent/'h3-timing-flexiact-character-guidance-r101-20261019';OLD=ROOT.parent/'h3-flexiact-character-repair-metrics-r98-20261019'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
assert not (ROOT/'CONSUMER_FREEZE.json').exists()
expected='c72172b4139a955b37ba0a55e56675a05322a81d66a5c83fe11e9f961e5eca5e';assert sha(P/'deploy_manifest.json')==expected
for rel,row in read(P/'deploy_manifest.json')['files'].items():assert sha(P/rel)==row['sha256'],rel
for x in ['scripts','tests','configs','audit']: (ROOT/x).mkdir(exist_ok=True)
for x in ['common.py','collect.py','remote.py','render.py','consume.py']:
 text=(OLD/'scripts'/x).read_text().replace('r98-','r101-').replace('R98','R101')
 (ROOT/'scripts'/x).write_text(text)
src='human2animal_1__game_man_4';b=read(P/'configs/parent_bindings.json')[src];sc=read(P/'configs/scientific_contract.json');case=sc['cases'][0];run=case['run_id'];old=read(OLD/'configs/contract.json')
for name,rel in [('producer_seal.json','deploy_manifest.json'),('producer_runtime.json','configs/runtime.json'),('producer_scientific_contract.json','configs/scientific_contract.json'),('parent_bindings.json','configs/parent_bindings.json'),('producer_graph.json','configs/graphs/'+run+'.json')]:shutil.copyfile(P/rel,ROOT/'configs'/name)
for name,digest in b['local_snapshot_hashes'].items():
 f=P/'design'/src/name;assert sha(f)==digest;dest=ROOT/'configs/parent'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(f,dest)
media={'source':old['media']['source'],'native':{'file':str(OLD/'incoming/native.mp4'),'sha256':b['native_video']['sha256']},'target':old['media']['target']}
for x in media.values():assert sha(Path(x['file']))==x['sha256']
assert sha(ROOT/'configs/parent/PARENT_ACTUAL_GATE.json')==b['gate']['sha256']
c={'schema':'r101-one-shot-paired-consumer-v1','producer_local':str(P),'producer_remote':read(P/'configs/runtime.json')['remote_root'],'producer_seal_sha256':expected,'producer_runtime_sha256':sha(P/'configs/runtime.json'),'producer_contract_sha256':sha(P/'configs/scientific_contract.json'),'graph_sha256':sha(P/'configs/graphs'/f'{run}.json'),'source_id':src,'run_id':run,'parent_run_id':b['run_id'],'expected_attempt':'root_character_guidance_attempt1','media':media,'columns':['参考视频','普通编辑','时序引导'],'prompt':case['prompt'],'valid_frames':147,'total_frames':158,'fps':24,'original_motion_frames':49,'evaluation_indices':list(range(0,147,3)),'original_pair_id':case['original_pair_id'],'group':case['group'],'default_output':'/Users/researcher/Downloads/H3_R101_俯卧支撑_普通编辑与时序引导_20261019.html','method':'固定时序引导；去噪步骤6–14，α=1，全50个DiT block','scope':'FlexiAct官方素材的自建动作/目标组合；复用同.9 R98实际新版Native，真实配对门后展示。'}
save(ROOT/'configs/contract.json',c)
save(ROOT/'audit/ORIGIN.json',{'producer':str(P),'producer_seal':expected,'consumer_reused_from':str(OLD),'new_consumer':str(ROOT),'scope':'Only new consumer files; no producer edits or execution'})
