"""One-time, pre-seal addition requested by root; no service or CUDA actions."""
import copy, hashlib, json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'h3-timing-flexiact-prompt-pair-r72-20261018'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def cp(a,b):Path(b).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
assert not (ROOT/'deploy_manifest.json').exists()
key='one_leg__movie_man_9'
old=next(c for c in read(OLD/'configs/scientific_contract.json')['cases'] if c['pair_key']==key and c['arm']=='p0')
olddef=next(p for p in read(OLD/'design/PAIR_DEFINITIONS.json')['pairs'] if p['pair_key']==key)
defs=read(ROOT/'design/PAIR_DEFINITIONS.json');assert key not in [p['pair_key'] for p in defs['pairs']]
for k in ['video','portrait','provenance']:
 assert sha(OLD/'inputs'/old[k])==old[k+'_sha256'];cp(OLD/'inputs'/old[k],ROOT/'inputs'/old[k])
original=ROOT/'inputs/source_one_leg_original.mp4';cp(olddef['source_asset']['path'],original);assert sha(original)==olddef['source_asset']['sha256']
meta=ROOT.parent/'h3-flexiact-expanded-selection-20261018/metadata'
for suffix in ['crop.csv','val_image.csv']:
 name='flexiact_hf__benchmark__captions__human__one_leg__'+suffix;cp(meta/name,ROOT/'design/official_metadata'/name)
snapshot=ROOT/'design/R72_P0_ANCESTRY';snapshot.mkdir()
cp(OLD/old['prompt_file'],snapshot/'p0.txt')
cp(OLD/'configs/graphs'/(old['run_id']+'.json'),snapshot/'actual_graph.json')
put(snapshot/'CASE.json',old)
assert sha(snapshot/'p0.txt')==old['prompt_sha256']
assert read(snapshot/'actual_graph.json')['5']['inputs']['prompt']==old['prompt']
promptfile='configs/prompts/'+key+'_p0.txt';cp(snapshot/'p0.txt',ROOT/promptfile)
d=copy.deepcopy(olddef)
d.update(candidate_id=key,original_pair_id=key,group='official_csv_identity_generalization',portrait=old['portrait'],portrait_sha256=old['portrait_sha256'],prompt=old['prompt'],prompt_file=promptfile,prompt_sha256=old['prompt_sha256'],prompt_version='P0',target_pair_previously_generated_at_selection=True,original_metadata_flag=None,
 caption_review=['Root prioritizes an independently repeated known delayed case. Exact successful R72 P0 is retained. New Native and forced are both generated on host9; old host41 outputs are historical evidence.'],
 source={k:old[k] for k in ['video','video_sha256','provenance','provenance_sha256']},
 p0_ancestry={'root':str(OLD),'run_id':old['run_id'],'prompt_file':'design/R72_P0_ANCESTRY/p0.txt','prompt_sha256':old['prompt_sha256'],'graph_file':'design/R72_P0_ANCESTRY/actual_graph.json','graph_sha256':sha(snapshot/'actual_graph.json'),'case_file':'design/R72_P0_ANCESTRY/CASE.json','case_sha256':sha(snapshot/'CASE.json')})
d['source'].update(original=original.name,original_sha256=sha(original))
for p in defs['pairs']:p['prompt_version']='P1'
defs['pairs'].insert(0,d);defs['schema']='r85-three-official-flex-pairs-v1';defs['prompt_policy']='one_leg exact successful R72 P0; crouch and rotate structured P1. Identical prompt and fresh same-host shared conditioning/noise within each Native/forced pair.'
selection=read(ROOT/'design/SELECTED_PAIRS.json');selection['schema']='r85-three-fixed-official-pairs-v1';selection['pairs'].insert(0,{'source':'one_leg','target':olddef['identity'],'pair_key':key});selection['decision']='Root prioritizes known one_leg delayed case, then crouch and rotate. All six new outputs retained. Prior R72/R49 results informed this pilot selection; this is not a randomly sampled benchmark mean.';selection['historical_output_informed_priority']=True
put(ROOT/'design/SELECTED_PAIRS.json',selection);defs['selection_sha256']=sha(ROOT/'design/SELECTED_PAIRS.json');put(ROOT/'design/PAIR_DEFINITIONS.json',defs)
put(ROOT/'design/EXPECTED_SHAPES.json',{p['pair_key']:p['reference_image_expected'] for p in defs['pairs']})
a=read(ROOT/'configs/prompt_ancestry.json');a['parent']='one_leg exact R72 P0; crouch R74 P1; rotate R74 P1 with declared target descriptor';a['pair_definitions_sha256']=sha(ROOT/'design/PAIR_DEFINITIONS.json');put(ROOT/'configs/prompt_ancestry.json',a)
s=read(ROOT/'configs/scientific_contract.json');cases=[]
for arm in ['native','forced']:
 c=copy.deepcopy(s['cases'][0]);c.update({k:d[k] for k in ['pair_key','motion_source_id','original_pair_id','group','identity','portrait','portrait_sha256','prompt','prompt_file','prompt_sha256','reference_image_expected','prompt_version']});c.update(d['source']);c.pop('original',None);c.pop('original_sha256',None);c.update(source_id=key,arm=arm,run_id='r85_'+key+'_seed2026101701_'+arm);cases.append(c)
cases+=s['cases'];pairs=[p['pair_key'] for p in defs['pairs']]
s.update(schema='r85-flexiact-three-fixed-route-v1',cases=cases,case_order=[c['run_id'] for c in cases],source_ids=pairs,pair_keys=pairs,motion_source_ids=['one_leg','crouch','rotate'],prompt_version='per_pair',scope_note='Three official identity pairs over three previously used motions. one_leg P0 is an independent host9 repetition of a known delayed case; crouch/rotate use P1. Six new outputs retained.',selection_scope={'official_csv_pairs':3,'total_pairs':3,'distinct_motion_sources':3,'source_event_selection':False,'historical_output_informed_priority':True,'current_generated_output_selection':False})
put(ROOT/'configs/scientific_contract.json',s);put(ROOT/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
r=read(ROOT/'configs/runtime.json');r['profile_scope']='Three fixed official Flex pairs: one_leg R72 P0 first, crouch/rotate P1. Fresh host9 Native then fixed route. Require40GiB free and exact release of predecessor R73; foreign users allowed, own cap2.';put(ROOT/'configs/runtime.json',r)
b=read(ROOT/'configs/storage_policy.json');b.update(prior_observation='R74 planning estimate scaled from12 to6 jobs',registered_frames_total=948,estimated_output_bytes=8808189983);put(ROOT/'configs/storage_policy.json',b)
# Definitions now support two explicitly frozen prompt protocols; numerical graph builder is unchanged.
p=ROOT/'scripts/r85_contract.py';t=p.read_text().replace('Two fixed official Flex pairs; identical P1 Native/forced per actual cache.','Three official Flex pairs; each Native/forced pair has identical prompt and actual caches.').replace("PAIR_KEYS=('crouch__movie_man_5','rotate__game_girl_1')","PAIR_KEYS=('one_leg__movie_man_9','crouch__movie_man_5','rotate__game_girl_1')").replace('fixed two','fixed three').replace("len(s['cases'])==4","len(s['cases'])==6").replace("case['prompt_version']=='P1'","case['prompt_version']==p['prompt_version']")
t=t.replace("require(value==p['prompt'] and (root/'design/P1_TEMPLATE.txt').read_text().format(**p['p1_fields'])==value,'P1 fields differ');return value", "require(value==p['prompt'],'prompt value differs')\n if p['prompt_version']=='P1':require((root/'design/P1_TEMPLATE.txt').read_text().format(**p['p1_fields'])==value,'P1 fields differ')\n else:\n  require(p['prompt_version']=='P0' and pair=='one_leg__movie_man_9','unsupported prompt protocol');a=p['p0_ancestry']\n  require(sha(root/a['prompt_file'])==a['prompt_sha256']==p['prompt_sha256'] and sha(root/a['graph_file'])==a['graph_sha256'] and sha(root/a['case_file'])==a['case_sha256'],'R72 P0 ancestry changed')\n  require((root/a['prompt_file']).read_text()==value==read(root/a['graph_file'])['5']['inputs']['prompt']==read(root/a['case_file'])['prompt'],'exact R72 P0 differs')\n return value")
p.write_text(t)
p=ROOT/'analysis/postrun/verify_pair.py';t=p.read_text().replace("'prompt_version':'P1'","'prompt_version':jobs[pair[0]]['case']['prompt_version']");p.write_text(t)
p=ROOT/'scripts/preflight.py';p.write_text(p.read_text().replace("'pairs':2,'distinct_motion_sources':2","'pairs':3,'distinct_motion_sources':3"))
p=ROOT/'audit/root_run_batch.py';p.write_text(p.read_text().replace('two pairs','three pairs').replace('two-pair','three-pair'))
sys.path.insert(0,str(ROOT/'scripts'));import r85_contract as c
for case in cases:put(ROOT/'configs/graphs'/(case['run_id']+'.json'),c.expected_graph(ROOT,case))
put(ROOT/'configs/input_hashes.json',{p.name:sha(p) for p in sorted((ROOT/'inputs').iterdir()) if p.is_file()})
put(ROOT/'configs/source_selection_hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'design').rglob('*')) if p.is_file()})
put(ROOT/'audit/PRIORITY_REVISION.json',{'pairs':pairs,'prior_package_unsealed':True,'historical_p0_prompt_exact':True,'fresh_same_host_pairs':True,'GPU_started':False,'graphs':{case['run_id']:sha(ROOT/'configs/graphs'/(case['run_id']+'.json')) for case in cases}})
print('Three-pair priority revision complete; no service started')
