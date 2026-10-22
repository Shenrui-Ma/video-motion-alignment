"""Rebind the validated R127 executor to one new short source; CPU only."""
from pathlib import Path
import ast,copy,hashlib,json,os,re,shutil,sys,time
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-ive-full-context-long0122-r127-20261020'
S='short_0177';OLD='long_0122';REMOTE='/data4/researcher/h3_runs/timing_ive_tiger_lion_r131_20261020'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert not(R/'deploy_manifest.json').exists()
parent=read(P/'deploy_manifest.json')
skip=('configs/graphs/','configs/parent_graphs/','configs/prompts/','design/')
for rel,v in parent['files'].items():
 assert sha(P/rel)==v['sha256'],rel
 if rel.startswith(skip):continue
 q=R/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/rel,q)
for name in ['processes','logs','input','output','temp','user','custom_nodes','tests','configs/graphs','configs/parent_graphs','configs/prompts','audit/router','audit/x0']:(R/name).mkdir(parents=True,exist_ok=True)
plan=read(R/'design/INPUT_PLAN.json');task=plan['official_task'];prov=read(R/'inputs'/f'{S}_provenance.json')
prompt=(P/'configs/prompts'/f'{OLD}.txt').read_text().replace('A vibrant scarlet macaw perched on a tree branch, grooming itself.',task['source_prompt']).replace('A vibrant toucan perched on a tree branch, grooming itself.',task['target_prompt']).replace('Replace the scarlet macaw with a toucan',task['edit_prompt']).replace('scarlet macaw','tiger').replace('tree branch','rock')
for k in ['source_prompt','edit_prompt','target_prompt']:assert task[k] in prompt
(R/'configs/prompts'/f'{S}.txt').write_text(prompt)
put(R/'design/PROMPT_SOURCE_MAPPING.json',{'official_task':task,'official_metadata':plan['metadata_evidence'],'verbatim_fields':['source_prompt','edit_prompt','target_prompt'],'added_text_scope':'The same R127 input/subject relations, preservation requirements and audio/music declarations; no event positions or manually expanded action chain.','source_visual_check':'All60 valid source frames show one tiger on rock in woodland, yawning then closing its mouth. Captions agree.','prompt_sha256':sha(R/'configs/prompts'/f'{S}.txt')})
g=read(P/'configs/parent_graphs'/f'{OLD}_native.json');g['22']['inputs']['file']=f'{S}_video.mp4';g['5']['inputs'].update(prompt=task['edit_prompt'],length=73);g['52']['inputs']['length']=73;g['50']['inputs']['end_frame']=59
put(R/'configs/parent_graphs'/f'{S}_native.json',g)
d=copy.deepcopy(read(P/'design/SOURCE_DEFINITIONS.json')[OLD]);d.update(source_id=S,source_selection_file=str(R/'design/INPUT_PLAN.json'),source_selection_sha256=sha(R/'design/INPUT_PLAN.json'),prepared_source_provenance_sha256=sha(R/'inputs'/f'{S}_provenance.json'),original_task=task,parent_graph=f'configs/parent_graphs/{S}_native.json',parent_graph_sha256=sha(R/'configs/parent_graphs'/f'{S}_native.json'),parent_graph_scope='R127 graph template adapted to the already used73-frame geometry; fresh source/text conditions.',valid_frame_count=60,video=f'{S}_video.mp4',video_sha256=sha(R/'inputs'/f'{S}_video.mp4'),provenance=f'{S}_provenance.json',provenance_sha256=sha(R/'inputs'/f'{S}_provenance.json'),original_source=f'{S}_original.mp4',original_source_sha256=sha(R/'inputs'/f'{S}_original.mp4'),clip=plan['clip'])
put(R/'design/SOURCE_DEFINITIONS.json',{S:d});put(R/'configs/parent_bindings.json',{'sources':{S:d}});put(R/'PREPARED_INPUTS_MANIFEST.json',{'schema':'r123-byte-reused-inputs-v1','sources':{S:d}})
runtime=read(P/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8591,profile='host41_gpu2_r131_short0177_full_context',profile_scope='New IVE tiger-to-lion full short source; Native first, then registered fixed guidance when justified.');put(R/'configs/runtime.json',runtime)
science=read(P/'configs/scientific_contract.json');science.update(geometry={'width':1312,'height':736,'frames':73,'fps':24},source_ids=[S],pair_keys=[S],case_order=[],cases=[],scope_note='R131 new IVE tiger-to-lion whole short source,60valid24fps/73total; source-only yawn stages pre-registered. Same fixed operator, no human pose observer.',source_definitions_sha256=sha(R/'design/SOURCE_DEFINITIONS.json'))
for old in read(P/'configs/scientific_contract.json')['cases']:
 c=copy.deepcopy(old);arm=c['arm'];c.update({k:d[k] for k in ['source_id','parent_graph','parent_graph_sha256','video','video_sha256','provenance','provenance_sha256','original_source','original_source_sha256','original_task','valid_frame_count','clip']});c.update(run_id=f'r123_{S}_seed2026101701_{arm}',prompt=prompt,prompt_sha256=sha(R/'configs/prompts'/f'{S}.txt'),geometry=science['geometry'],evaluation_indices=list(range(60)),evaluation_scope='New IVE whole2.48-second source,60valid24fpsframes.',parent_semantics='R127 numerical executor; source/text computed fresh. Only shape-compatible seed1701 actual AV noise from R128 is reused.');science['cases'].append(c);science['case_order'].append(c['run_id'])
put(R/'configs/scientific_contract.json',science);put(R/'configs/queue.json',{'jobs':science['case_order'],'finalize':True})
p=R/'scripts/r123_contract.py';t=p.read_text().replace(OLD,S).replace("(107, 106)","(73, 60)")
t=re.sub(r'^PROMPTS = .*$',lambda _:f'PROMPTS = {repr({S:prompt})}',t,flags=re.M)
t=t.replace("'frames':107","'frames':73").replace('(1,24,32,46,82)','(1,24,22,46,82)').replace('(1,32,2,178)','(1,32,2,122)').replace('range(32)','range(22)').replace("'total_latent_bins':32","'total_latent_bins':22").replace('range(stop,32)','range(stop,22)');p.write_text(t)
p=R/'scripts/verify_input_timeline.py';t=p.read_text().replace("('long_0122',204,106)","('short_0177',62,60)").replace('range(valid,107)','range(valid,73)').replace('len(mapping)==107','len(mapping)==73').replace('Fraction(i,30)','Fraction(i,25)').replace('inspect(original,count,30)','inspect(original,count,25)').replace('inspect(prepared,107,24','inspect(prepared,73,24').replace("'valid_frames':[106]","'valid_frames':[60]");p.write_text(t)
noise=R/'noise_origin/r128_short_0362_seed2026101701_noise.pt';manifest=R/'noise_origin/r128_short_0362_seed2026101701_native_noise.json';n=read(manifest)
for a,b in [(noise,R/'inputs/initial_AV_noise_r128.pt'),(manifest,R/'inputs/initial_AV_noise_r128.json')]:
 if not b.exists():os.link(a,b)
 assert sha(a)==sha(b)
put(R/'configs/parent_noise.json',{'source_file':REMOTE+'/inputs/initial_AV_noise_r128.pt','source_sha256':sha(noise),'source_noise_manifest':REMOTE+'/inputs/initial_AV_noise_r128.json','source_noise_manifest_sha256':sha(manifest),'destination_filename':f'r123_{S}_seed2026101701_noise.pt','actual_noise_streams':n['actual_noise_streams'],'signature':n['signature'],'origin_scope':'R128 actual73-frame same-seed noise only; original source or conditioning not reused.'})
for rel in ['scripts/preflight.py','scripts/parent_noise.py','analysis/postrun/verify_pair.py']:
 p=R/rel;p.write_text(p.read_text().replace('R121','registered parent').replace('_r121_initial_noise_equal','_registered_initial_noise_equal'))
pred=read(P/'configs/predecessor.json');pred['required']=[{'key':'R127','remote_root':read(P/'configs/runtime.json')['remote_root'],'producer_seal_sha256':sha(P/'deploy_manifest.json'),'runtime_sha256':sha(P/'configs/runtime.json'),'kind':'screen','required_sources':[OLD]}];put(R/'configs/predecessor.json',pred)
sys.path.insert(0,str(R/'scripts'));import r123_contract as contract
for c in science['cases']:put(R/'configs/graphs'/(c['run_id']+'.json'),contract.expected_graph(R,c))
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
kernel=read(P/'configs/runtime_kernel_hashes.json')
for rel,v in kernel.items():assert sha(R/rel)==sha(P/rel)==v['current_sha256'];v.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=True)
put(R/'configs/runtime_kernel_hashes.json',kernel)
inherited=[]
for rel in parent['files']:
 q=R/rel
 if q.exists() and q.suffix=='.py':inherited.append({'file':rel,'source':str(P/rel),'source_sha256':sha(P/rel),'sha256':sha(q),'byte_equal':sha(q)==sha(P/rel)})
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'source_root':str(P),'source_seal_sha256':sha(P/'deploy_manifest.json'),'bindings':inherited})
put(R/'audit/SOURCE_ADAPTATION_DIFF.json',{'parent':str(P),'changed_code':[x['file'] for x in inherited if not x['byte_equal']],'unchanged_code_count':sum(x['byte_equal'] for x in inherited),'scientific_changes':['New source/prompt: tiger-to-lion','73total/60valid frames; padding excluded','shape-compatible original AV noise fromR128, seed1701','same Euler20/CFG1/sigma/router6..14/all50/alpha1'],'administrative':['root namespace R131; runtime schema/run_id prefix r123 retained','GPU2 port8591; predecessor R127 full release'],'GPU_started':False})
for p in R.rglob('*.py'):ast.parse(p.read_text())
print(json.dumps({'passed':True,'unchanged_code':sum(x['byte_equal'] for x in inherited),'changed_code':[x['file'] for x in inherited if not x['byte_equal']],'prompt_sha256':sha(R/'configs/prompts'/f'{S}.txt')}))
