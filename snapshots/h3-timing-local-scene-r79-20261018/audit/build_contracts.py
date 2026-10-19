from pathlib import Path
import hashlib,json,sys,copy
R=Path(__file__).resolve().parents[1];O=Path('/Users/researcher/DevProjects/h3-timing-ivebench-body-r76-20261018');sys.path.insert(0,str(R/'scripts'))
from input_contract import SOURCES,LENGTHS,latent_shape
from r79_contract import expected_graph
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
rows=[]
for sid,(T,N) in zip(SOURCES,LENGTHS):
 files={}
 for kind,suffix in [('video','video.mp4'),('original','original.mp4'),('provenance','provenance.json'),('prompt','prompt.txt')]:
  p=R/'inputs'/f'{sid}_{suffix}';files[kind]=dict(file=str(p.relative_to(R)),sha256=sha(p),bytes=p.stat().st_size)
 rows.append(dict(pair_id=sid,files=files,h3_frames=T,valid_frames=N,prepared_streams=read(R/'design'/f'{sid}_input_probe.json')['streams'],latent_shape=latent_shape(T)))
put(R/'PREPARED_INPUTS_MANIFEST.json',dict(schema='r79-prepared-full-official-inputs-v1',input_plan_sha256=sha(R/'design/INPUT_PLAN.json'),pairs=rows))
put(R/'configs/input_hashes.json',{Path(f['file']).name:f['sha256'] for x in rows for f in x['files'].values()})
s=read(O/'configs/scientific_contract.json');s['schema']='r79-fixed-time-route-two-paired-v1';s['source_ids']=list(SOURCES);s['cases']=[];s['case_order']=read(R/'configs/queue.json')['jobs'];s['purpose']='Two official original-scene local edits: background screen replacement and dog-to-cat. Each Native is reviewed before corresponding forced submission.'
s['evaluation'].update(adaptation='Two source-selected complete official clips with exact mapping to24fps; retain both cases and all failures. Report task fidelity on both, then timing on eligible retained-action pairs.',groups={'background_object':['short_0144'],'animal_subject':['short_0166']},visibility_policy='0144 keep all four people and their motions; larger billboard may legitimately occlude local pixels. 0166 retain both women/orchard actions; cat shape and animal behavior are edited. Hands/branches may occlude joints. UNKNOWN remains unobservable.',rules_sha256=sha(R/'design/NEXT_EVALUATION_RULES.txt'),fixed_case_denominator=2)
s['continuous'].update(idle_hold_seconds=1800,manual_submissions=True,controller_enabled=False)
s['first_pair']='Individual Native then root visual review then corresponding forced';s['acceleration_axes']['cache']='Default Comfy model/node cache across individually approved jobs';s['acceleration_axes']['runtime']='Host41 frozen R76 runtime, unchanged six numerical modules; per-job exact admission.'
s['input_plan_sha256']=sha(R/'design/INPUT_PLAN.json');s['prepared_input_manifest_sha256']=sha(R/'PREPARED_INPUTS_MANIFEST.json');s['source_selection_sha256']=sha(R/'configs/source_selection/SELECTED_2_MANIFEST.json');s['prompt_template_sha256']=sha(R/'design/P1_TEMPLATE.txt');s['prompt_version']='P1-local-v1'
selected={x['source_id']:x for x in read(R/'configs/source_selection/SELECTED_2_MANIFEST.json')['pairs']}
for sid,row,(T,N) in zip(SOURCES,rows,LENGTHS):
 task=selected[sid]['official_task'];prompt=(R/'design/P1_TEMPLATE.txt').read_text().format(**task)
 (R/'configs/prompts').mkdir(exist_ok=True)
 for suffix in ['.txt','_DRAFT.txt']:(R/'configs/prompts'/f'{sid}{suffix}').write_text(prompt)
 for arm in ['native','forced']:
  c=copy.deepcopy(read(O/'configs/scientific_contract.json')['cases'][0]);c.update(run_id=f'r79_{sid}_seed2026101701_{arm}',source_id=sid,prompt=prompt,video=f'{sid}_video.mp4',provenance=f'{sid}_provenance.json',valid_frame_count=N,original_task=task,video_sha256=row['files']['video']['sha256'],provenance_sha256=row['files']['provenance']['sha256'],geometry=dict(width=1312,height=736,frames=T,fps=24),original_source=f'{sid}_original.mp4',arm=arm,prompt_version='P1-local-v1',parent_semantics='Exact frozen R73/R76 mathematical graph and metadata P1 template; root individually submits Native, then reviews before forced. Paired prompt/condition/noise unchanged.')
  s['cases'].append(c);put(R/'configs/graphs'/f'{c["run_id"]}.json',expected_graph(R,c))
put(R/'configs/scientific_contract.json',s)
# Adapt only tests exercising new registry/administrative interface; preserve numerical and byte-equality tests.
p=R/'tests/test_inputs.py';p.write_text(p.read_text().replace('SELECTED_5_MANIFEST','SELECTED_2_MANIFEST').replace('selected_five','selected_two'))
p=R/'tests/test_registered_pairs.py';p.write_text(p.read_text().replace('exact_ten','exact_four').replace('len(order),10','len(order),4').replace('short_0131','short_0144'))
p=R/'tests/test_pair_verifier.py';p.write_text(p.read_text().replace('short_0178','short_0166').replace('valid_frame_count\':121','valid_frame_count\':123').replace('[0,120]','[0,122]').replace("valid_frames'],121","valid_frames'],123"))
p=R/'tests/test_spawn_identity.py';p.write_text(p.read_text().split('class ControllerRegistration')[0])
print('4 graphs,2 paired sources ready')
