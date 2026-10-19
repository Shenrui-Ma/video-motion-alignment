"""Administrative continuation of four preselected R63 tasks; no execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

DEST = Path(__file__).resolve().parents[1]
PARENT = DEST.parent / 'h3-timing-ivebench-forced-r63-20261018'
REMOTE = '/data3/researcher/h3_runs/timing_ivebench_remaining_r69_20261018'
SOURCES = ('short_0230','short_0263','short_0352','short_0370')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')

def main():
    assert not (DEST/'deploy_manifest.json').exists()
    assert not (DEST/'processes/service.json').exists()
    for folder in ('scripts','extensions','configs/parent_graphs','configs/R54_evidence','source_snapshot','tests'):
        shutil.copytree(PARENT/folder, DEST/folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('verify_pair.py','capture_checks.py'):
        target=DEST/'analysis/postrun'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(PARENT/'analysis/postrun'/name,target)
    # Restrict changes to experiment bindings; numerical kernels are copied verbatim.
    for folder in ('scripts','extensions','tests','analysis/postrun'):
        for path in (DEST/folder).rglob('*.py'):
            original=path.read_text()
            changed=original.replace('r63_contract','r69_contract').replace("'r63_","'r69_").replace('"r63_','"r69_').replace('r63-','r69-')
            if path.name in ('execution_gate.py','test_first_pair.py','test_pair_verifier.py'):
                changed=changed.replace('short_0210','short_0230')
            if path.name=='r63_contract.py':
                changed=changed.replace("SOURCES=('short_0210','short_0230','short_0263','short_0352','short_0370')", "SOURCES=('short_0230','short_0263','short_0352','short_0370')")
                changed=changed.replace("len(s['cases'])==10", "len(s['cases'])==8").replace('fixed five paired','fixed remaining four paired').replace('Five P0 tasks','Four remaining P0 tasks')
            if path.name=='preflight.py':changed=changed.replace("'sources':5", "'sources':4")
            if path.name=='execution_gate.py':
                changed=changed.replace("'configs/R54_evidence')", "'configs/R54_evidence','configs/R63_reference_graphs','analysis/postrun')")
                changed=changed.replace("'runtime_kernel_hashes.json','parent_core_hashes.json')", "'runtime_kernel_hashes.json','parent_core_hashes.json','fixed_five_scope.json')")
            if changed!=original:path.write_text(changed)
    (DEST/'scripts/r63_contract.py').rename(DEST/'scripts/r69_contract.py')
    science=read(PARENT/'configs/scientific_contract.json')
    science['schema']='r69-fixed-time-route-r63-remaining-four-paired-v1'
    science['cases']=[copy.deepcopy(x) for x in science['cases'] if x['source_id'] in SOURCES]
    for row in science['cases']:row['run_id']=row['run_id'].replace('r63_','r69_')
    science['source_ids']=list(SOURCES)
    science['case_order']=[x['run_id'] for x in science['cases']]
    science['first_pair']=' then '.join(science['case_order'][:2])
    science['purpose']='Continue four already selected R63 tasks; original five-source denominator retained in configs/fixed_five_scope.json'
    science['acceleration_axes']['runtime']='Host41 inherited core and runtime_deps; exact active versions recorded at actual launch'
    science['acceleration_axes']['cache']='default Comfy model/node cache across eight sequential jobs'
    write(DEST/'configs/scientific_contract.json',science)
    write(DEST/'configs/queue.json',{'jobs':science['case_order'],'finalize':False})
    profile=read(PARENT/'configs/profiles/host41_normal_reserve8.json')
    profile.update(remote_root=REMOTE,port=8538,gpu_uuid='GPU-REDACTED',expected_gpu_index=7,profile='host41_gpu7_normal_reserve8',profile_scope='R63 numerical continuation on Host41 GPU7. Current live resources and full trajectory capacity require root admission.')
    write(DEST/'configs/runtime.json',profile)
    write(DEST/'configs/profiles/host41_gpu7_normal_reserve8.json',profile)
    write(DEST/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
    write(DEST/'configs/main_memory_profile.json',{'status':'PENDING_ACTUAL_CAPACITY'})
    for name in ('parent_core_hashes.json','model_hashes_host41.json','host41_provenance.json'):
        shutil.copy2(PARENT/'configs'/name,DEST/'configs'/name)
    inputs={}
    for name,digest in read(PARENT/'configs/input_hashes.json').items():
        if any(name.startswith(source+'_') for source in SOURCES):
            target=DEST/'inputs'/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(PARENT/'inputs'/name,target)
            assert sha(target)==digest
            inputs[name]=digest
    write(DEST/'configs/input_hashes.json',inputs)
    kernels={}
    for name in read(PARENT/'configs/runtime_kernel_hashes.json'):
        assert sha(DEST/name)==sha(PARENT/name),name
        kernels[name]={'parent_file':str(PARENT/name),'parent_sha256':sha(PARENT/name),'current_sha256':sha(DEST/name),'byte_equal':True}
    write(DEST/'configs/runtime_kernel_hashes.json',kernels)
    write(DEST/'configs/fixed_five_scope.json',{
        'original_source_ids':['short_0210',*SOURCES],
        'original_selected_source_count':5,'new_run_source_ids':list(SOURCES),
        'retained_prior_source':{'source_id':'short_0210','host':'.9','producer':str(PARENT),
                                 'status':'previous Native/ON pair retained; parent reported quality failure',
                                 'include_in_final_five_source_outcomes':True},
        'source_selection_changed':False,'reason':'Finish original remaining four; all outcomes retained'})
    sys.path.insert(0,str(DEST/'scripts'))
    import r69_contract
    for case in science['cases']:
        write(DEST/'configs/graphs'/(case['run_id']+'.json'),r69_contract.expected_graph(DEST,case))
        old=case['run_id'].replace('r69_','r63_')+'.json'
        target=DEST/'configs/R63_reference_graphs'/old
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(PARENT/'configs/graphs'/old,target)
    write(DEST/'audit/INHERITANCE.json',{'parent':str(PARENT),'parent_contract_sha256':sha(PARENT/'configs/scientific_contract.json'),'source_count':4,'jobs':8,'original_denominator':5,'kernel_bytes_equal':kernels})
    print(json.dumps({'root':str(DEST),'jobs':8,'source_count':4,'inputs':len(inputs),'launch_admitted':False}))

if __name__=='__main__':main()
