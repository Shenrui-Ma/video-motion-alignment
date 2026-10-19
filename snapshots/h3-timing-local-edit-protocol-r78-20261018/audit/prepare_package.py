from pathlib import Path
import copy, hashlib, json, shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
OLD=BASE/'h3-timing-ivebench-prompt-pair-r71-20261018'
R69=BASE/'h3-timing-ivebench-remaining-r69-20261018'
R73=BASE/'h3-timing-ivebench-expanded-r73-20261018'
REMOTE='/data3/researcher/h3_runs/timing_local_edit_protocol_r78_20261018'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def read(p):return json.loads(p.read_text())

for folder in ['scripts','extensions','tests','analysis/postrun']:
 shutil.copytree(OLD/folder,ROOT/folder,ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=False)
for p in list(ROOT.rglob('*.py')):
 if p==Path(__file__):continue
 s=p.read_text().replace('r71','r78').replace('R71','R78').replace('short_0210','short_0370')
 p.write_text(s)
(ROOT/'scripts/r71_contract.py').rename(ROOT/'scripts/r78_contract.py')
for folder in ['configs/parent_graphs','configs/ancestors','configs/prompts','configs/graphs','inputs','design','audit/consumer']:(ROOT/folder).mkdir(parents=True,exist_ok=True)
for name in ['expected_checkpoint_hashes.json','runtime_kernel_hashes.json','parent_core_hashes.json']:
 shutil.copyfile(OLD/'configs'/name,ROOT/'configs'/name)

source=next(c for c in read(R69/'configs/scientific_contract.json')['cases'] if c['source_id']=='short_0370' and c['arm']=='native')
parent=R69/'configs/graphs'/f"{source['run_id']}.json"
shutil.copyfile(parent,ROOT/'configs/parent_graphs'/parent.name)
for name in ['short_0370_video.mp4','short_0370_original.mp4','short_0370_provenance.json','short_0370_prompt.txt']:
 shutil.copyfile(R69/'inputs'/name,ROOT/'inputs'/name)
save(ROOT/'configs/input_hashes.json',{p.name:sha(p) for p in (ROOT/'inputs').iterdir()})
template=(R73/'design/P1_TEMPLATE.txt').read_text()
template=template.replace('body pose, camera framing and movement, and unedited scene content.','body pose, camera framing and movement, and unedited scene content.\nPreserve the same man, the original room and wooden furniture, the small cup,\nand the complete sipping action. Change only the clothes from blue to white.')
(ROOT/'design/P1_TEMPLATE.txt').write_text(template)
shutil.copyfile(R73/'design/P1_TEMPLATE.txt',ROOT/'design/R73_PARENT_TEMPLATE.txt')
row=dict(source['original_task']);row['pair_id']='short_0370'
save(ROOT/'design/LOCAL_EDIT_METADATA.json',{'pairs':[row]})
prompts={'p0':row['edit_prompt'],'p1':template.format(**row)}
ancestry={}
for arm in ['p0','p1']:
 p=ROOT/'configs/prompts'/f'{arm}.txt';p.write_text(prompts[arm])
 ancestor=read(parent);ancestor['5']['inputs']['prompt']=prompts[arm]
 f=ROOT/'configs/ancestors'/f'{arm}_prompt_contract.json';save(f,ancestor)
 ancestry[arm]={'file':str(f.relative_to(ROOT)),'sha256':sha(f),'prompt_sha256':sha(p)}
for k,name in [('template','P1_TEMPLATE.txt'),('metadata','LOCAL_EDIT_METADATA.json')]:
 f=ROOT/'design'/name;ancestry[k]={'file':str(f.relative_to(ROOT)),'sha256':sha(f)}
save(ROOT/'configs/prompt_ancestry.json',ancestry)
save(ROOT/'design/TEMPLATE_ADAPTATION.json',{'base_file':'design/R73_PARENT_TEMPLATE.txt','base_sha256':sha(ROOT/'design/R73_PARENT_TEMPLATE.txt'),'change':'Add explicit same-man/original-room/furniture/cup/sipping preservation and clothes-only color edit. All official source/edit/target descriptions preserved verbatim.','claim':'Combined prompt adaptation; not isolated formatting effect.'})

runtime=read(R69/'configs/runtime.json')
runtime.update(status='CPU_PREPARED_ROOT_LAUNCH_PENDING',remote_root=REMOTE,gpu_uuid='GPU-REDACTED',port=8546,expected_gpu_index=6,profile='host41_gpu6_normal_reserve8',profile_scope='R78 fresh P0/P1 Native pair, local clothes-color edit; all original R69 numerical settings and input bytes retained. Root live admission required.')
save(ROOT/'configs/runtime.json',runtime)
save(ROOT/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
science=read(OLD/'configs/scientific_contract.json')
science['schema']='r78-preregistered-local-edit-prompt-pair-v1';science['source_ids']=['short_0370'];science['cases']=[]
science['router'].update(steps=[6,15],physical_frames=[0,88])
science['purpose']='Same-scene local clothing-color editing: R69 source/seed/geometry/sampling; P0 vs R73-derived P1. Known development source.'
science['acceleration_axes']['runtime']='Same Host41 runtime/core paths and four checkpoint expectations as R69; actual provenance captured at launch.'
science['acceleration_axes']['postprocessing']='Original prepared24fps mapping retained, 90 total/89 valid frames; crop16/8 spatial padding only.'
science['review_after_pair']='Two runs only; exact service release then root task-fidelity review. No further case is registered.'
science['task_fidelity']={'edited':'blue clothes become white','preserved':['same man','original room','wooden furniture','small cup','sipping sequence and physical timing','camera framing and movement'],'assessment_order':['edit success','scene/object retention','action content retention','timing if corresponding action remains measurable']}
order=[]
for arm in ['p0','p1']:
 case=copy.deepcopy(source);run=f'r78_short_0370_seed2026101701_{arm}';order.append(run)
 case.update(run_id=run,arm=arm,prompt_version=arm.upper(),prompt=prompts[arm],parent_graph='configs/parent_graphs/'+parent.name,parent_graph_sha256=sha(parent),prompt_file=f'configs/prompts/{arm}.txt',prompt_sha256=sha(ROOT/'configs/prompts'/f'{arm}.txt'),reference_cache_id=f'r78_short_0370_{arm}_shared',historical_native_run=source['run_id'])
 case.pop('parent_semantics',None);science['cases'].append(case)
 graph=read(parent)
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:graph[node]['inputs'][key]=REMOTE+'/'+suffix
 graph['5']['inputs'].update(run_id=case['reference_cache_id'],prompt=case['prompt']);graph['51']['inputs']['source_run_id']=case['reference_cache_id']
 for node in ['6','50','51','52']:graph[node]['inputs']['run_id']=run
 graph['6']['inputs']['pair_id']='r78_short_0370_seed2026101701';graph['14']['inputs']['filename_prefix']=run
 save(ROOT/'configs/graphs'/f'{run}.json',graph)
science['case_order']=order
save(ROOT/'configs/scientific_contract.json',science);save(ROOT/'configs/queue.json',{'jobs':order,'finalize':True})

# Fixed prompt-pair administrative bindings; numerical kernels remain byte-identical.
p=ROOT/'scripts/r78_contract.py';s=p.read_text().replace('original R57','R73-adapted local editing').replace('R57 preregistration','local-edit preregistration')
s=s.replace('==87','==89').replace('end_frame=89','end_frame=88').replace('step_start=0,step_end=20','step_start=6,step_end=15').replace("('native',1.,0,0,0,89,0,50,0,20)","('native',1.,0,0,0,88,0,50,6,15)")
p.write_text(s)
p=ROOT/'scripts/preflight.py';p.write_text(p.read_text().replace("'steps':[0,20],'physical_frames':[0,89]","'steps':[6,15],'physical_frames':[0,88]"))
p=ROOT/'analysis/postrun/verify_pair.py';s=p.read_text().replace("[6,15] if forced else [0,20]","[6,15]").replace("'pixel_interval_inclusive':[0,89]","'pixel_interval_inclusive':[0,88]");p.write_text(s)
p=ROOT/'tests/test_prompt_pair.py';s=p.read_text().replace('configs/ancestors/r57_short_0370_seed2026101701_native.json','configs/ancestors/p1_prompt_contract.json');p.write_text(s)
p=ROOT/'tests/test_pair_verifier.py';s=p.read_text().replace("'valid_frame_count':87","'valid_frame_count':89").replace("['valid_frames'],87","['valid_frames'],89").replace("[6,15] if full else [0,20]","[6,15]").replace("'pixel_interval_inclusive':[0,89]","'pixel_interval_inclusive':[0,88]").replace("x['step_interval_half_open']=[6,15]","x['step_interval_half_open']=[0,20]");p.write_text(s)

# CPU consumer, no metrics/trackers or GPU scheduling.
p=ROOT/'audit/consumer/postrun.py';s=(OLD/'audit/consumer/postrun.py').read_text().replace('r71','r78').replace('R71','R78').replace('short_0210','short_0370').replace('VALID=87','VALID=89').replace('full87','full89').replace('end_frame=87','end_frame=89').replace("'87'","'89'").replace("'24/1',87","'24/1',89").replace('角色替换','局部颜色编辑');p.write_text(s)
save(ROOT/'audit/PREPARATION_ANCESTRY.json',{'producer_parent':str(OLD),'numerical_parent':str(R69),'prompt_template_parent':str(R73/'design/P1_TEMPLATE.txt'),'parent_native_graph':str(parent),'parent_native_graph_sha256':sha(parent),'inputs_bytes':sum(p.stat().st_size for p in (ROOT/'inputs').iterdir()),'GPU_started':False})
print(ROOT)
