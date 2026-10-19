"""Create a separate execution for R100's unsubmitted fireplace task."""
from pathlib import Path
import copy, hashlib, json, shutil, sys

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'h3-timing-ive-task-repair-r100-20261019'
REMOTE = '/data5/researcher/h3_runs/timing_ive_fireplace_recovery_r108_20261019'
SOURCE = 'short_0392'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n')
def cp(a,b):
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(a,b)

assert not (ROOT/'deploy_manifest.json').exists(), 'frozen package already exists'
sealed = read(PARENT/'deploy_manifest.json')
numerical = read(PARENT/'configs/runtime_kernel_hashes.json')
for rel, item in sealed['files'].items():
    assert sha(PARENT/rel) == item['sha256'], rel
    if not rel.startswith(('scripts/', 'extensions/', 'tests/', 'source_snapshot/', 'analysis/postrun/')) and rel != 'audit/root_run_batch.py':
        continue
    if rel == 'tests/test_task_repair_contract.py': continue
    target = ROOT/rel.replace('r100_contract.py','r108_contract.py')
    cp(PARENT/rel,target)
    if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in numerical:
        target.write_text(target.read_text().replace('r100','r108').replace('R100','R108'))

for directory in ['inputs','input','output','temp','user','custom_nodes','processes','logs','configs/graphs','configs/prompts','audit/router','audit/x0']:
    (ROOT/directory).mkdir(parents=True,exist_ok=True)
for rel in ['configs/parent_core_hashes.json','configs/expected_checkpoint_hashes.json','configs/storage_policy.json','configs/R54_evidence/short_0210/captures.json','configs/parent_graphs/r63_template_native.json','design/OFFICIAL_REF_EN.txt']:
    cp(PARENT/rel,ROOT/rel)
for p in (PARENT/'inputs').glob(SOURCE+'_*'): cp(p,ROOT/'inputs'/p.name)
for rel in [f'configs/prompts/{SOURCE}.txt',f'design/{SOURCE}_P1_candidate.txt']:
    cp(PARENT/rel,ROOT/rel)
for rel in ['deploy_manifest.json','configs/runtime.json','configs/scientific_contract.json',f'configs/prompts/{SOURCE}.txt']+[f'configs/graphs/r100_{SOURCE}_seed2026101701_{a}.json' for a in ['native','forced']]:
    cp(PARENT/rel,ROOT/'source_snapshot/r100_parent'/rel)

for name in ['INPUT_PLAN.json','EXECUTION_INPUT_PLAN.json']:
    v=read(PARENT/'design'/name);v['schema']=v.get('schema','').replace('r100','r108')
    v['pairs']=[p for p in v['pairs'] if p['pair_id']==SOURCE]
    if 'source_order' in v: v['source_order']=[SOURCE]
    put(ROOT/'design'/name,v)
v=read(PARENT/'design/PROPOSAL.json');v['items']=[p for p in v['items'] if p['source_id']==SOURCE]
v['recovery_reason']='Original R100 service released after basketball pair review timeout; fireplace was never submitted. New execution preserves original source, P1 and scientific settings.'
put(ROOT/'design/PROPOSAL.json',v)
v=read(PARENT/'configs/source_selection/SELECTED_2_MANIFEST.json');v['schema']='r108-fireplace-recovery-selection-v1';v['pairs']=[p for p in v['pairs'] if p['pair_id']==SOURCE]
put(ROOT/'configs/source_selection/SELECTED_1_MANIFEST.json',v)
v=read(PARENT/'configs/source_selection/OFFICIAL_SOURCE_ORIGIN.json');v['sources']=[p for p in v['sources'] if p['pair_id']==SOURCE]
put(ROOT/'configs/source_selection/OFFICIAL_SOURCE_ORIGIN.json',v)
put(ROOT/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (ROOT/'configs/source_selection').iterdir()})
v=read(PARENT/'PREPARED_INPUTS_MANIFEST.json');v.update(schema='r108-byte-reused-inputs-v1',input_plan_sha256=sha(ROOT/'design/INPUT_PLAN.json'));v['pairs']=[p for p in v['pairs'] if p['pair_id']==SOURCE]
put(ROOT/'PREPARED_INPUTS_MANIFEST.json',v)
put(ROOT/'configs/input_hashes.json',{p.name:sha(p) for p in (ROOT/'inputs').iterdir()})

runtime=read(PARENT/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8571,profile='host9_gpu0_r108_normal_reserve8',profile_scope='Previously unsubmitted fireplace task, fresh Native followed by reviewed matched fixed guidance')
put(ROOT/'configs/runtime.json',runtime)
put(ROOT/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','permitted_compute_processes':[],'existing_comfy_port':None})
contract=ROOT/'scripts/r108_contract.py';text=contract.read_text()
text=text.replace("SOURCES=('short_0114', 'short_0392')", "SOURCES=('short_0392',)").replace("SOURCE_LENGTHS={'short_0114': (107, 105), 'short_0392': (73, 57)}", "SOURCE_LENGTHS={'short_0392': (73, 57)}")
text=text.replace("len(s['cases'])==4","len(s['cases'])==2").replace('fixed two paired registry','fixed fireplace paired registry').replace('SELECTED_2_MANIFEST','SELECTED_1_MANIFEST')
contract.write_text(text)
p=ROOT/'scripts/input_contract.py';p.write_text(p.read_text().replace("SOURCES=('short_0114','short_0392')","SOURCES=('short_0392',)").replace('LENGTHS=((107,105),(73,57))','LENGTHS=((73,57),)'))
p=ROOT/'scripts/preflight.py';p.write_text(p.read_text().replace("'sources':2","'sources':1"))

s=read(PARENT/'configs/scientific_contract.json')
s.update(schema='r108-fireplace-recovery-v1',source_ids=[SOURCE],case_order=[],cases=[c for c in s['cases'] if c['source_id']==SOURCE],purpose='Finish the unsubmitted original fireplace repair with unchanged P1 and sampling; new independent process, preserve R100 timeout and results.')
for c in s['cases']:
    c['run_id']=c['run_id'].replace('r100_','r108_');s['case_order'].append(c['run_id'])
s['prompt_sha256']={SOURCE:sha(ROOT/'configs/prompts'/f'{SOURCE}.txt')}
for key,rel in [('input_plan_sha256','design/EXECUTION_INPUT_PLAN.json'),('root_input_plan_sha256','design/INPUT_PLAN.json'),('root_proposal_sha256','design/PROPOSAL.json'),('prepared_input_manifest_sha256','PREPARED_INPUTS_MANIFEST.json'),('source_selection_sha256','configs/source_selection/SELECTED_1_MANIFEST.json')]: s[key]=sha(ROOT/rel)
s['screening'].update(schema='r108-native-screen-policy-v1',fixed_source_denominator=1)
s['evaluation']['fixed_case_denominator']=1
cp(PARENT/'design/NEXT_EVALUATION_RULES.txt',ROOT/'design/NEXT_EVALUATION_RULES.txt')
(ROOT/'design/NEXT_EVALUATION_RULES.txt').write_text('验收完整雕花壁炉的去除，并保留白套装女子、房间其余部分和手势顺序。基础编辑成功后再决定同条件固定时序引导。全57有效帧评估，保留失败和无收益结果。\n')
s['evaluation']['rules_sha256']=sha(ROOT/'design/NEXT_EVALUATION_RULES.txt')
put(ROOT/'configs/scientific_contract.json',s);put(ROOT/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
sys.path.insert(0,str(ROOT/'scripts'));import r108_contract as c
for case in s['cases']: put(ROOT/'configs/graphs'/f"{case['run_id']}.json",c.expected_graph(ROOT,case))
for rel,row in numerical.items():
    assert sha(ROOT/rel)==sha(PARENT/rel)
    row.update(parent_file=str(PARENT/rel),parent_sha256=sha(PARENT/rel),current_sha256=sha(ROOT/rel),byte_equal=True)
put(ROOT/'configs/runtime_kernel_hashes.json',numerical)
put(ROOT/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_seal_sha256':sha(PARENT/'deploy_manifest.json'),'numerical':numerical,'inputs':read(ROOT/'configs/input_hashes.json'),'P1_exact':sha(ROOT/'configs/prompts'/f'{SOURCE}.txt')==sha(PARENT/'configs/prompts'/f'{SOURCE}.txt')})
cp(PARENT/'audit/remote_cpu_validate.py',ROOT/'audit/remote_cpu_validate.py')
print(c.registry()[1])
