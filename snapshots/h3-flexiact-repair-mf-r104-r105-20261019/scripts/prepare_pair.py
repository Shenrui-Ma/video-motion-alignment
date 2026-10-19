"""Prepare official FlexiAct MF inputs for a verified actual native/guided pair; CPU only."""
from pathlib import Path
import argparse,copy,hashlib,importlib.util,json,shutil,subprocess,sys
R=Path(__file__).resolve().parents[1]
OLD=R.parent/'h3-flexiact-character-repair-mf-r98-20261019'
INDICES=list(range(0,147,3))

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def save(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def verify_manifest(m,prov,gate):
    require(m['evaluate_indices']==INDICES and m['evaluation_fps']==8 and m['valid_frames']==147,'fixed original instants required')
    require(set(m['raw_videos'])=={'source','native','forced'},'actual native and guided required')
    require(gate['passed'] is True and all(x is True for x in gate['checks'].values()),'actual pair gate failed')
    require(prov['source_original_sha256']==prov['official_source']['sha256'],'official source identity differs')
    for arm in ('native','forced'):
        require(gate['runs'][arm]['video']['sha256']==m['raw_videos'][arm]['sha256'],'actual video binding differs')
    require(gate['runs']['native']['video']['sha256']!=gate['runs']['forced']['video']['sha256'],'identical native/guided media need review')
    return True

def prepare(consumer,case,lane):
    consumer=Path(consumer).resolve();require(lane in ('r104','r105'),'unknown consumer lane')
    require(case and all(x.isalnum() or x=='_' for x in case),'unsafe case name')
    dest=R/'pairs'/lane/case;require(not dest.exists(),'existing pair package retained')
    manifest=consumer/'prepared'/case/'paired/MF_INPUTS.json';m=read(manifest)
    code='import sys;sys.path.insert(0,'+repr(str(consumer/'scripts'))+');from common import validate_static;from paired import verify_pair_intake;validate_static();verify_pair_intake('+repr(case)+');print("actual_pair_verified")'
    subprocess.run([sys.executable,'-c',code],check=True,capture_output=True,text=True,timeout=120)
    for key in ('gate','provenance','collection'):
        require(sha(m[key]['file'])==m[key]['sha256'],'consumer '+key+' changed')
    gate=read(m['gate']['file']);prov=read(m['provenance']['file']);verify_manifest(m,prov,gate)
    original=Path(prov['official_source']['local_path']);require(sha(original)==prov['source_original_sha256'],'original source bytes differ')
    require(Path(prov['official_source']['official_path']).stem==m['task']['motion_source_id'],'canonical motion source differs')
    for arm in ('native','forced'):
        require(sha(m['raw_videos'][arm]['file'])==m['raw_videos'][arm]['sha256'],'actual video bytes differ')
    dest.mkdir(parents=True);(dest/'inputs').mkdir();(dest/'prepared').mkdir();(dest/'configs').mkdir();(dest/'audit').mkdir()
    for src,name in [(manifest,'CONSUMER_MF_INPUTS.json'),(m['gate']['file'],'PAIR_RUNTIME_GATE.json'),
            (m['provenance']['file'],'SOURCE_PROVENANCE.json'),(m['collection']['file'],'COLLECTION.json'),(original,'official_reference49_8fps.mp4')]:
        shutil.copy2(src,dest/'inputs'/name)
    helper=OLD/'runtime/release/release49.py';require(sha(helper)=='5bd956e4225d23e97429c4a09d8302477b6d392b176392e13ce0faf8b41fef3f','sampling helper differs')
    release=load('unchanged_release49',helper);target_rows={};case_id='human/'+m['task']['motion_source_id']+'/000'
    for role,arm in [('native','native'),('guided','forced')]:
        full=dest/'inputs'/(role+'_full158.mp4');shutil.copy2(m['raw_videos'][arm]['file'],full)
        out=dest/'prepared'/(role+'_49_8fps.mp4');release.run(full,out)
        target_rows[role]={'file':str(out),'sha256':sha(out),'mapping':str(out.with_suffix('.mapping.json')),
            'mapping_sha256':sha(out.with_suffix('.mapping.json')),'full':str(full),'full_sha256':sha(full),
            'indices':INDICES,'run_id':gate['runs'][arm]['run_id'],'producer_arm':arm}
    reference=dest/'inputs/official_reference49_8fps.mp4';runtime=dest/'runtime/official_metric'
    shutil.copytree(OLD/'runtime/official_metric',runtime,ignore=shutil.ignore_patterns('inputs','SOURCE_INPUTS.json','__pycache__'))
    numeric={str(p.relative_to(runtime)):sha(p) for p in sorted(runtime.rglob('*')) if p.is_file()}
    require(all(sha(OLD/'runtime/official_metric'/p)==h for p,h in numeric.items()),'official numeric source differs')
    save(runtime/'SOURCE_INPUTS.json',{'schema':'repair-official-flex-reference-v1','inputs':[{'id':case_id,'role':'reference',
        'file':str(reference),'sha256':sha(reference),'frames':49,'pts_seconds':[i/8 for i in range(49)],
        'original_frame_indices':list(range(49)),'original_fps':8,'official_source_url':prov['official_source']['pinned_url'],
        'id_scope':'motion-source identity; image pairing retained separately in task'}]})
    for role,row in target_rows.items():
        meta={'run_id':row['run_id'],'method':role,'comparison_kind':'actual_paired_guidance','official_pair_id':case_id,
            'edited49':row['file'],'edited49_sha256':row['sha256'],'full158_output':row['full'],'full158_output_sha256':row['full_sha256'],
            'full_output_indices':INDICES,'physical_seconds':[i/8 for i in range(49)],'padding_evaluated':False,
            'original_source_sha256':sha(reference),'producer_receipt':{'file':str(dest/'inputs/PAIR_RUNTIME_GATE.json'),'sha256':sha(dest/'inputs/PAIR_RUNTIME_GATE.json')}}
        mp=dest/'prepared'/role/'METRIC_INPUTS.json';save(mp,meta)
        item={'id':case_id,'role':'generated','file':row['file'],'sha256':row['sha256'],'frames':49,
            'pts_seconds':[i/8 for i in range(49)],'generation_frame_indices':INDICES,
            'generation_binding':{'metric_inputs':{'file':str(mp),'sha256':sha(mp)},
                                  'release_mapping':{'file':row['mapping'],'sha256':row['mapping_sha256']}}}
        save(dest/'prepared'/role/'TRACK_INPUTS.json',{'schema':'repair-official-flex-generated-v1','inputs':[item]})
    save(dest/'prepared/guided/MATCHED_GATE_BINDING.json',{'gate':{'file':str(dest/'inputs/PAIR_RUNTIME_GATE.json'),
        'sha256':sha(dest/'inputs/PAIR_RUNTIME_GATE.json')},'native_sha256':target_rows['native']['full_sha256'],
        'guided_sha256':target_rows['guided']['full_sha256'],'consumer_manifest_sha256':sha(manifest)})
    runner=load('unchanged_official_flex_runner',runtime/'run_tracks.py');checks=[]
    for role in ('reference','native','guided'):
        mf=runtime/'SOURCE_INPUTS.json' if role=='reference' else dest/'prepared'/role/'TRACK_INPUTS.json'
        item=read(mf)['inputs'][0];runner.check_timebase(Path(item['file']));checks.append(role+'_49_original_instants')
        if role!='reference':runner.validate_generated_binding(item,Path(item['file']));checks.append(role+'_actual_generation_binding')
    require('torch' not in sys.modules,'CPU preparation imported torch unexpectedly')
    data={'schema':'repair-official-flex-mf-inputs-v1','benchmark':'FlexiAct','lane':lane,'case':case,'canonical_motion_id':case_id,
        'comparison_kind':'actual_paired_guidance','task':m['task'],'source_original':{'file':str(reference),'sha256':sha(reference),'indices':list(range(49))},
        'targets':target_rows,'frame_count':49,'fps':8,'official_grid_size':55,'mask':None,'scores':None,'GPU_started':False,
        'status':'CPU_READY_WAIT_SCORING_SLOT','consumer_manifest':{'file':str(manifest),'sha256':sha(manifest)},
        'release49_original_sha256':sha(helper),'checkpoint_required_sha256':'dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3'}
    save(dest/'prepared/MF_INPUTS.json',data)
    save(dest/'configs/NUMERIC_INHERITANCE.json',{'source_runtime':str(OLD/'runtime/official_metric'),'files':numeric,
        'official_commit':'de9fe1d536732c4d1a384577b5ae54f8fc1730d7','checkpoint_sha256':data['checkpoint_required_sha256']})
    save(dest/'audit/OFFICIAL_BINDING_CPU_CHECK.json',{'passed':True,'checks':checks,'frozen_numeric_files':len(numeric),
        'GPU_started':False,'input_sha256':sha(dest/'prepared/MF_INPUTS.json')})
    print(json.dumps({'path':str(dest),'inputs_sha256':sha(dest/'prepared/MF_INPUTS.json'),'GPU_started':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('consumer');p.add_argument('case');p.add_argument('lane');a=p.parse_args();prepare(a.consumer,a.case,a.lane)
