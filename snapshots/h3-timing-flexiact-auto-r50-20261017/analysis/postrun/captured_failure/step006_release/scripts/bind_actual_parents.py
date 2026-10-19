"""One-time binding of all five completed R49 executions. Missing inputs abort."""
import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path
from intake_parent_metadata import inspect

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'h3-timing-flexiact-native-r49-20261017'
LEGACY = ROOT.parent/'h3-timing-auto-source28289-r45-20261017'
REMOTE = '/data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017'

def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        out.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
def copied(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != source.read_bytes():
            raise ValueError('different existing binding: ' + str(destination))
    else:
        shutil.copyfile(source, destination)
    return str(destination.relative_to(ROOT))

def main(archive):
    archive = Path(archive)
    if read(ROOT/'configs/PARENT_CLOSURE.json')['ready']:
        raise ValueError('actual parents already bound')
    intake = inspect(archive)
    if intake['status'] != 'INTAKE_RECORDED_NOT_BOUND' or any(row['missing_metadata'] for row in intake['cases']):
        raise ValueError('all five parent archives are required before production binding')
    pose_manifest = PARENT/'analysis/source_pose158_sidecar/MANIFEST.json'
    source_intake = read(ROOT/'audit/SOURCE_POSE_ACTUAL_INTAKE_v1.json')
    if sha(pose_manifest) != source_intake['source_manifest_sha256']:
        raise ValueError('actual source pose manifest changed')
    component = read(ROOT/'configs/protocol.json')
    copied(ROOT/'configs/protocol.json', ROOT/'audit/COMPONENT_PROTOCOL_v2.json')
    copied(ROOT/'configs/PARENT_CLOSURE.json', ROOT/'audit/PARENT_CLOSURE_pending_v2.json')
    protocol = copy.deepcopy(read(LEGACY/'configs/protocol.json'))
    protocol.update(schema='r50-flexiact-five-paired-auto-v1',
                    scope='Five predeclared FlexiAct human-to-human official pairs; original delayed-only automatic controller on full158 model geometry, valid147-frame observation domain.',
                    cases=component['cases'], geometry=[1152,768,158,24],
                    preparation_status='ACTUAL_R49_PARENTS_BOUND_ROOT_GPU_GATES_PENDING')
    protocol['observer'].pop('source_pose_sha256', None)
    protocol['observer']['source_pose_binding']='per case source_pose_path/source_pose_sha256'
    protocol['observer']['valid_frame_count']=147
    protocol['observer']['padding']='147..157 excluded before pose feature scale and all statistics; complete158 raw pose retained'
    protocol['resources'].update(main_uuid='GPU-REDACTED', decoder_uuid='GPU-REDACTED')
    protocol['evaluation'].update(main='Official FlexiAct motion fidelity at original49 timestamps; supplementary arm timing with UNKNOWN retained', source_scope='All five paired sources; arms-only automatic observer; no generated-outcome filtering')
    protocol['evaluation']['public_metric_frame_indices']=list(range(0,147,3))
    protocol['inherited_rule']['source_only_pose']='per-case source_pose_path'
    protocol['inherited_rule']['parent']='R45 unchanged policy/operator, R49 actual Native inputs/outputs'
    protocol['prefix'].update(all_OFF='Compare each actual R49 Native final AV; RGB evaluated independently.', availability='All five successful R49 archives with all21 AV endpoints per case.')
    original_contract = read(PARENT/'configs/scientific_contract.json')
    public_cases = {x['source_id']:x for x in original_contract['cases']}
    closure = {'schema':'r50-five-case-parent-closure-v1','ready':True,'status':'READY',
               'final_archive_ready':True,'cases':{},'GPU':'root gates pending'}
    relations = {'parent_graph':'graph','parent_conditioning':'conditioning','parent_noise':'noise','parent_captures':'captures'}
    for case, evidence in zip(protocol['cases'], intake['cases']):
        source = case['source_id']; folder = ROOT/'configs/parents'/source
        required=[]
        for field, key in relations.items():
            target=folder/(key+'.json')
            case[field]=copied(Path(evidence['files'][key]['path']),target); required.append(case[field])
        for key in ('history','job','router','shared'):
            required.append(copied(Path(evidence['files'][key]['path']),folder/(key+'.json')))
        for key in ('RUN_GATE.json','FILE_INVENTORY.json','RUNTIME_GATE.json','deploy_manifest.json'):
            required.append(copied(archive/key,folder/key))
        case['parent_file_inventory']=str((folder/'FILE_INVENTORY.json').relative_to(ROOT))
        pose=source_intake['sources'][source]
        if sha(Path(pose['pose_path']))!=pose['pose_sha256']:
            raise ValueError('actual source pose changed: '+source)
        case['source_pose_path']=copied(Path(pose['pose_path']),folder/'source.pose.json')
        case['source_pose_sha256']=pose['pose_sha256'];required.append(case['source_pose_path'])
        case['identity']=public_cases[source]['identity']
        case['provenance']=public_cases[source]['provenance']
        case['video_sha256']=public_cases[source]['video_sha256']
        case['portrait_sha256']=public_cases[source]['portrait_sha256']
        case['provenance_sha256']=public_cases[source]['provenance_sha256']
        condition=read(ROOT/case['parent_conditioning'])
        closure['cases'][source]={'ready':True,'parent_run':case['parent_run'],
             'required_actual_files':required,'actual_file_sha256':{rel:sha(ROOT/rel) for rel in required},
             'packed_layout':condition['packed_layout'],'source_pose_sha256':case['source_pose_sha256'],
             'tensor_inventory':evidence['tensor_inventory']}
    # Input bytes and original release49 metadata remain those of the Native experiment.
    inputs={}
    for path in sorted((PARENT/'inputs').iterdir()):
        if path.is_file():
            copied(path,ROOT/'inputs'/path.name);inputs[path.name]=sha(path)
    put(ROOT/'configs/input_hashes.json',inputs)
    for name in ('model_hashes_host9.json','parent_core_hashes.json'):
        copied(PARENT/'configs'/name,ROOT/'configs'/name)
    copied(archive/'configs/runtime_provenance.json',ROOT/'configs/parent_runtime_provenance.json')
    for name in ('r27_inheritance.json','kernel_inheritance.json'):
        inherited=read(LEGACY/'configs'/name)
        inherited['exact_numerical_files']={k:v for k,v in inherited['exact_numerical_files'].items() if (ROOT/k).is_file() and sha(ROOT/k)==v}
        inherited['inherited_scope']='Exact unchanged numeric files only. New47-bin/full158 geometry and decoder peak require root execution gates.'
        put(ROOT/'configs'/name,inherited)
    # Replace only the two explicitly pending registry files; original bytes are preserved above.
    (ROOT/'configs/protocol.json').write_text(json.dumps(protocol,indent=2,ensure_ascii=False)+'\n')
    (ROOT/'configs/PARENT_CLOSURE.json').write_text(json.dumps(closure,indent=2)+'\n')
    copied(ROOT/'configs/protocol.json',ROOT/'PROTOCOL.json')
    protocol_sha=sha(ROOT/'configs/protocol.json')
    tpath=ROOT/'extensions/H3AutomaticWindowRouter/transport.py'
    text=tpath.read_text();old="PROTOCOL_SHA='UNSEALED_R50_PARENT_PENDING'"
    if old not in text: raise ValueError('protocol placeholder changed')
    tpath.write_text(text.replace(old,'PROTOCOL_SHA='+repr(protocol_sha)))
    put(ROOT/'configs/queue.json',{'jobs':[c['run_id'] for c in protocol['cases']],'finalize':False})
    adm=read(LEGACY/'configs/admission_template.json')
    adm['fixed_fields']['existing_comfy_port']=None
    put(ROOT/'configs/admission_template.json',adm)
    put(ROOT/'configs/admission.json',dict(adm['fixed_fields'],permitted_compute_processes=[],root_live_review_required=True))
    science=copy.deepcopy(original_contract)
    science.update(schema='r50-flexiact-five-official-pair-auto-v1',arms=['auto'],cases=protocol['cases'],
                   case_order=[c['run_id'] for c in protocol['cases']],NFE_per_job='20+K',blocks_per_job='50*(20+K)',routed_blocks_per_job='50*K')
    science['router']=protocol['actuator']
    put(ROOT/'configs/scientific_contract.json',science)
    copied(PARENT/'scripts/release49.py',ROOT/'scripts/release49.py')
    put(ROOT/'FREEZE.json',{'schema':'r50-production-science-freeze-v1','files':{'PROTOCOL.json':protocol_sha,'configs/protocol.json':protocol_sha}})
    bindings=read(LEGACY/'configs/observer_bindings.json')
    bindings['schema']='r50-five-case-observer-bindings-v1'
    bindings['local_files']={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'configs').rglob('*')
       if p.is_file() and p.name not in ('observer_bindings.json','admission.json','queue.json','PARENT_CLOSURE.json')}
    for p in (ROOT/'scripts').glob('*.py'):
        bindings['local_files'][str(p.relative_to(ROOT))]=sha(p)
    put(ROOT/'configs/observer_bindings.json',bindings)
    put(ROOT/'audit/ACTUAL_PARENT_INTAKE.json',intake)
    print(json.dumps({'bound_cases':5,'protocol_sha256':protocol_sha,'production_GPU_gates':'pending root'}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True)
    main(parser.parse_args().archive)
