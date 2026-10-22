"""R138 lineage adapter over the sealed R133 intake boundary."""
from pathlib import Path
import hashlib,json,copy,uuid
_here=Path(__file__).resolve().parents[1]
_pins=json.loads((_here/'configs/SHARED_HELPERS.json').read_text())
_base=Path(_pins['common.py']['file']);assert hashlib.sha256(_base.read_bytes()).hexdigest()==_pins['common.py']['sha256']
exec(compile(_base.read_text(),str(_base),'exec'),globals())
RUN='r138_short_0252_seed2026101703_visible_only'
_base_static=validate_static
_base_counts=verify_counts

def safe_path(path):
    p=Path(path);c=config()
    allowed=p.is_relative_to(c['producer_remote']) or p.is_relative_to(Path(c['old_producer_remote'])/'audit/observations')
    require(allowed and '..' not in p.parts,'outside registered new producer/old observation evidence')
    return p

def validate_static():
    c=_base_static();check_bindings(c['old_consumer_freeze']);check_bindings(c['actual_execution']);check_bindings(c['failed_attempts'])
    old=read(ROOT/'configs/OLD_AUDIT_COMPACT.json');resume=read(ROOT/'configs/RESUME.json')
    receipt=old['compact_receipt'];rel=str(Path(resume['source_audit']).relative_to(resume['source_root']))
    require(receipt['original_sha256']==resume['source_files'][rel]['sha256'] and receipt['extractor_sha256']==sha(ROOT/'scripts/compact_audit.py'),'old compact source/extractor differs')
    require(old['status']=='failed' and len(old['counterfactual']['steps'])==9 and len(old['counterfactual']['branches'])==13,'original incomplete generation differs')
    return c

def condition_equivalence(current,old):
    canonical=[];records={}
    for label,value in (('current',current),('source',old)):
        require(set(value)=={'sha256','tree'},'condition signature schema differs')
        encoded=json.dumps(value['tree'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        require(hashlib.sha256(encoded).hexdigest()==value['sha256'],'complete condition hash does not match tree')
        tree=copy.deepcopy(value['tree']);ids={}
        for stage in ('original','processed'):
            rows=tree[stage]['positive'];require(len(rows)==1 and 'uuid' in rows[0],'condition identity structure differs')
            raw=rows[0].pop('uuid');require(isinstance(raw,str) and str(uuid.UUID(raw))==raw,'noncanonical condition UUID')
            ids[stage]=raw
        require(ids['original']==ids['processed'],'same-generation UUID propagation differs')
        canonical.append(tree);records[label]={'complete_sha256':value['sha256'],'condition_UUIDs':ids}
    require(canonical[0]==canonical[1],'conditioning differs beyond the two registered UUID fields')
    records['equivalent_except_paths']=['tree/original/positive/0/uuid','tree/processed/positive/0/uuid']
    records['canonical_sha256']=hashlib.sha256(json.dumps(canonical[0],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return records

def verify_lineage(c):
    cfg=read(ROOT/'configs/RESUME.json');old=read(ROOT/'configs/OLD_AUDIT_COMPACT.json')['counterfactual'];r=c['resume']
    expected={'schema':'r138-resume-lineage-v1','config_sha256':sha(ROOT/'configs/RESUME.json'),'source_run':cfg['source_run'],'source_audit':cfg['source_audit'],'source_release':cfg['source_release'],'start_physical_index':9,'inherited_complete_updates':9,'inherited_logical_model_nfe':12,'old_actual_executed_model_nfe':13,'reconstruction_model_nfe':0,'initial_rng_bytes_available':False,'replayed_archival_callbacks':list(range(9)),'first_restored_native_exact':True,'prefix_reconstruction_exact':True}
    require(all(r.get(k)==v for k,v in expected.items()),'recovery identity/control/state evidence differs')
    require(c['measurements'][:9]==old['measurements'][:9],'inherited observer evidence changed')
    for key in ('seed','full_grid','initial_noise','reference'):require(c[key]==old[key],'old scientific state differs: '+key)
    require(condition_equivalence(c['conditioning'],old['conditioning'])==r['conditioning_identity_equivalence'],'condition identity equivalence receipt differs')
    initial=dict(r['new_initial_binding']);require(initial['current_processed_condition_sha256']==c['conditioning']['sha256'],'initial new-generation condition hash differs');initial['current_processed_condition_sha256']=old['conditioning']['sha256']
    require(initial==old['pair_gates'][0],'initial source/noise binding changed')
    for i,step in enumerate(c['steps']):
        require(step.get('execution_generation')==('R133' if i<9 else 'R138'),'step execution generation differs')
        if i<9:
            normalized=dict(step);normalized.pop('execution_generation');normalized['chosen_file']=old['steps'][i]['chosen_file']
            require(normalized==old['steps'][i],'inherited completed update changed')
    old_branches={(b['physical_index'],b['branch']):b for b in old['branches']}
    new=[]
    for b in c['branches']:
        i=b['physical_index'];require(b.get('execution_generation')==('R133' if i<9 else 'R138'),'branch execution generation differs')
        require(b['condition_sha256']==(old if i<9 else c)['conditioning']['sha256'],'branch complete condition hash differs from its generation')
        if i<9:
            normalized=dict(b);normalized.pop('execution_generation');normalized['file']=normalized.pop('original_file')
            require(normalized==old_branches[i,b['branch']],'inherited branch/cost changed')
        else:new.append(b)
    restored=[b for b in new if b['physical_index']==9 and b['branch']=='native']
    require(len(restored)==1 and r['discarded_old_execution']==old_branches[9,'native'],'failed old step9 execution hidden or changed')
    for key in ('same_input','normalized_stream_signatures','raw_stream_signatures','sigma','sigma_next','seed','reference_sha256'):
        require(restored[0][key]==old_branches[9,'native'][key],'restored Native9 differs: '+key)
    require(r['state9_signature']==restored[0]['same_input'] and r['state9_signature']['sha256']==cfg['state_packed_sha256'],'state9 signature differs')
    logical=len(c['branches']);require(r['logical_model_nfe']==c['logical_model_nfe']==logical and r['actual_new_model_nfe']==len(new)==logical-12,'new/logical prediction cost differs')
    require(r['actual_all_generations_model_nfe']==13+len(new)==logical+1,'all-generation prediction cost omits failed work')
    require(r['actual_new_euler_updates']==11 and r['logical_euler_updates']==c['logical_euler_updates']==20,'Euler generation count differs')
    require(sorted(v['physical_index'] for v in c['inputs'] if v['physical_index']>=9)==list(range(9,20)),'new checkpoint indices incomplete/duplicated')
    return {'logical_NFE':logical,'old_actual_NFE':13,'inherited_logical_NFE':12,'actual_new_NFE':len(new),'actual_all_generations_NFE':13+len(new),'old_failed_step9_NFE':1,'reconstruction_NFE':0,'new_Euler_updates':11,'logical_Euler_updates':20}

def verify_counts(a):
    cost=verify_lineage(a['counterfactual'])
    logical=copy.deepcopy(a);c=logical['counterfactual'];c['actual_model_nfe']=c['logical_model_nfe'];c['actual_euler_updates']=c['logical_euler_updates']
    result=_base_counts(logical);result.update(cost)
    require(a['compact_receipt']['extractor_sha256']==sha(ROOT/'scripts/compact_audit.py') and a['compact_receipt']['measurements_complete']==20,'complete compact provenance missing')
    require(a['compact_receipt']['original_file']==str(Path(config()['producer_remote'])/f'audit/counterfactual/{RUN}.json'),'compact source generation differs')
    return result

def verify_gate(g,started,complete,release,a):
    c=config();runtime=read(ROOT/'configs/FORMAL_RUNTIME.json');owner=started['service'];counts=verify_counts(a)
    require(g['schema']=='r138-resumed-online-runtime-gate-v1' and g['passed'] is True and g['status']=='pass' and g['valid_frames']==98 and g['cleanup_verified'] is True,'resumed actual gate incomplete/failed')
    require(g['producer_manifest_sha256']==c['producer_seal_sha256'] and g['protocol_sha256']==c['protocol_sha256']==started['protocol_sha256'],'producer/protocol differs')
    require(g['service_record']==release['service']==owner,'new actual owner generation differs')
    require(owner==read(c['actual_execution']['file'])['owner'],'actual owner differs from registered recovery generation')
    require(owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'] and owner['identity']['uid']==runtime['uid'] and owner['identity']['start_ticks'],'runtime identity differs')
    cmd=owner['identity']['cmdline'];require(c['producer_remote'] in (' '.join(cmd) if isinstance(cmd,list) else cmd),'new service command outside producer')
    require(complete['passed'] is True and complete['run_id']==RUN and complete['no_followup_submission'] is True,'completion missing')
    require(release['passed'] is True and release['service_cleanup']['process_absent'] is True and release['service_cleanup']['own_compute_absent'] is True,'main release incomplete')
    require(release['observer_children']['all_exact_generations_absent'] is True and release['observer_children']['all_registered_CUDA_pids_absent'] is True,'decoder child release incomplete')
    require(g['verified_runs']==[RUN] and len(g['cases'])==1,'extra/missing output')
    case=g['cases'][0];require(case['run']==RUN and case['arm']=='visible_only' and case['mask']==counts['active_indices'] and case['first_on']==counts['first_on'] and case['NFE']==counts['logical_NFE'] and case['updates']==case['observations']==20,'gate logical decisions differ')
    require(case['independent_parent_inputs']['actual_clean_inputs_equal'] is True and case['independent_parent_inputs']['initial_video_audio_noise_equal'] is True,'parent input/noise gate failed')
    prefix=case['independent_native_prefix'];end=counts['first_on'] if counts['first_on'] is not None else 19
    require([x['physical_index'] for x in prefix]==list(range(end+1)) and all(x['actual_video_audio_tensor_equal'] is True for x in prefix),'eligible historical prefix incomplete')
    require([x['index'] for x in g['raw_filtered_pose_binding']]==list(range(20)) and [x['index'] for x in g['efficiency']['per_step']]==list(range(20)),'pose/timing coverage incomplete')
    for key in ('logical_NFE','actual_new_NFE','actual_all_generations_NFE','old_actual_NFE','reconstruction_NFE','new_Euler_updates','logical_Euler_updates'):require(g['efficiency'][key]==counts[key],'efficiency generation cost differs: '+key)
    require(g['efficiency']['interrupted_old_step9_NFE']==1,'interrupted ordinary call missing')
    cfg=read(ROOT/'configs/RESUME.json');lineage=g['resume_lineage']
    require(all(lineage[k]==v for k,v in a['counterfactual']['resume'].items()),'gate lineage differs from actual audit')
    require(lineage['source_files']==cfg['source_files'] and lineage['verified_new_checkpoint_indices']==list(range(9,20)),'new checkpoint/old exact archive binding incomplete')
    for key,path in [('source_audit_sha256',cfg['source_audit']),('source_release_sha256',cfg['source_release']),('state_file_sha256',cfg['state_file'])]:require(lineage[key]==cfg['source_files'][str(Path(path).relative_to(cfg['source_root']))]['sha256'],'old archive hash differs: '+key)
    require(all(row['execution_generation']==('R133' if row['index']<9 else 'R138') for row in g['efficiency']['per_step']),'timing generation attribution differs')
    safe_path(g['video']['file']);return counts
