"""Read-only actual29NFE static control; physical_index is denoising index, not video frame."""
import argparse,json,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'extensions'))
from H3StaticWindowRouter import transport as t

def check_record_semantics(record,capture,case):
    t.require(record['schema']=='h3-x0-readout-v1' and record['seed']==case['seed'] and record['run_id']==case['run_id'] and record['total_steps']==20,'capture semantic metadata')
    t.require(record['geometry']==capture['geometry']=={'width':1312,'height':736,'frames':141,'fps':24},'capture geometry')
    t.require(record['normalization_stage']=='after_process_latent_out' and record['audio_scale']==4.0 and record['video_latent_scale_factor']==1.0,'capture normalization')
    n=record['step_zero_based'];t.require(type(n) is int and 0<=n<20 and record['model_call_one_based']==n+1,'capture step')
    expected='sampler_final' if record['file']=='sampler_final.pt' else 'x0_estimate'
    t.require(record['snapshot_kind']==expected and (expected!='sampler_final' or n==19),'capture kind')
    sigma=0.0 if expected=='sampler_final' else capture['sigmas_video'][n]
    next_sigma=0.0 if expected=='sampler_final' else capture['sigmas_video'][n+1]
    t.require(record['endpoint_sanity']==(n==19) and record['sigma_video']==sigma and record['sigma_next_video']==next_sigma and record['sigma_audio']==sigma/(4-3*sigma),'capture sigma/endpoint')

def check_submission(job,history,run,graph_sha):
    t.require(job['status']=='success' and job['name']==run and job['graph_sha256']==graph_sha,'submission identity/status/graph mismatch')
    t.require(history['prompt'][1]==job['prompt_id'],'history prompt ID differs from submitted job')

def check_owner_evidence(owner,jobs,cleanup=None):
    import service
    t.require(owner['gpu_uuid']==service.GPU and owner['port']==service.PORT,'service GPU/port differs')
    identity=owner['identity'];t.require(set(identity)=={'uid','start_ticks','cmdline'} and type(identity['uid']) is int and identity['start_ticks'],'service identity schema')
    t.require(str(service.CORE/'main.py') in identity['cmdline'] and str(service.RUN) in identity['cmdline'],'service command differs')
    t.require(owner['command']==service.command(owner['cache_none']),'service argv differs')
    for j in jobs:t.require(j['service_pid']==owner['pid'] and j['service_identity']==identity,'job belongs to mixed service generation')
    if cleanup is not None:
        t.require(cleanup['pid']==owner['pid'] and cleanup['service_record']==owner,'stale cleanup owner')
        t.require(cleanup['process_absent'] and cleanup['own_compute_absent'] and cleanup.get('child_compute_absent',True),'cleanup incomplete')

def check_condition_blobs(root,run,c):
    import torch
    from evidence_helpers import inspect_blob,signature
    from H3StaticWindowRouter.pair_gate import condition_audit_matches
    graph=t.read_json(root/'configs/graphs'/f'{run}.json')
    current=t.read_json(root/'audit'/f'{run}_conditioning.json')
    old=t.read_json(root/'configs/parent_conditioning.json')
    condition_audit_matches(current,old)
    shared=root/'audit'/f"{graph['5']['inputs']['run_id']}_conditioning.json"
    t.require(current['run_id']==run and current['pair_snapshot']['verified'] is True and current['pair_snapshot']['source_manifest_sha256']==t.sha(shared),'condition cache snapshot binding')
    seen=set()
    def visit(value):
        if isinstance(value,dict):
            if 'tensor_file' in value and {'shape','dtype','sha256'}<=set(value) and value['tensor_file'] not in seen:
                seen.add(value['tensor_file']);inspect_blob(root/'audit',value)
            for v in value.values():visit(v)
        elif isinstance(value,list):
            for v in value:visit(v)
    visit(t.read_json(shared));t.require(len(seen)==8,'expected8 actual condition blobs')
    pair=graph['6']['inputs']['pair_id'];n=t.read_json(root/'audit'/f'{run}_noise.json');oldn=t.read_json(root/'configs/parent_noise.json')
    saved=torch.load(root/'audit'/f'{pair}_noise.pt',map_location='cpu',weights_only=True)
    actual=[{k:signature(v)[k] for k in ('shape','dtype','sha256')} for v in saved['tensors']]
    t.require(n['run_id']==run and n['pair_id']==pair and saved['signature']==n['signature']==oldn['signature'] and saved['hashes']==actual==n['actual_noise_streams']==oldn['actual_noise_streams'],'actual noise differs')
    packed=torch.cat([x.reshape(1,1,-1) for x in saved['tensors']],dim=-1)
    t.require(c['initial_noise']==signature(packed),'sampler packed noise differs from actual saved AV streams')

def check_branch_ledger(audit,c,gates):
    keys=[(r['physical_index'],r['branch']) for r in c['branches']]
    expected=[(i,b) for i in range(20) for b in (('native','full') if i in (6,7,8,9,10,11,12,13,14) else ('native',))]
    t.require(keys==expected and [(g['physical_index'],g['branch']) for g in gates]==expected,'branch/prefix unique ordered keys differ')
    t.require(audit['routed_by_forward']==[50 if b=='full' else 0 for _,b in expected] and audit['calls_by_block']==[29]*50 and audit['routed_by_block']==[9]*50,'per-NFE/block routing differs')
    sums=audit['forward_summaries'];t.require(len(sums)==29,'forward summary count')
    for i,(n,b) in enumerate(expected):
        z=sums[i];active=b=='full'
        t.require(z['forward_index']==i and z['nfe_index']==i and z['physical_index']==n and z['branch']==b and z['active'] is active and z['latent_bins']==(list(range(17,38)) if active else []) and z['completed_blocks']==50 and z['routed_blocks']==(50 if active else 0),'forward summary identity/selection differs')

def check(root=ROOT,allow_resident=False):
    root=Path(root);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path.insert(0,str(root/'extensions'))
    import torch
    torch.set_num_threads(1)
    from H3X0Readout.core import tensor_signature
    from H3StaticWindowRouter.static_plan import StaticPlan
    from H3StaticWindowRouter.pair_gate import actual_prefix,canonical_condition,condition_audit_matches
    from r41_contract import RUN_ID,SEED
    from evidence_helpers import inspect_blob,signature
    from r41_contract import validate_job
    from preflight import check as preflight
    preflight(root);t.bindings()
    manifest=t.read_json(root/'deploy_manifest.json')
    for rel,row in manifest['files'].items():t.require(t.sha(root/rel)==row['sha256'],'immutable file changed: '+rel)
    results=[];jobs=[]
    owner=t.read_json(root/'processes/service.json')
    for case in [{'run_id':RUN_ID,'seed':SEED}]:
        run=case['run_id'];validate_job(run,root)
        jobs.append(t.read_json(root/'logs'/f'{run}_job.json'))
        audit=t.read_json(root/'audit/counterfactual'/f'{run}.json');c=audit['counterfactual'];mask=c['full_physical_indices'];K=len(mask);nfe=20+K
        t.require(audit['status']=='complete' and mask==list(range(6,15)) and nfe==29,'invalid complete mask')
        t.require(c['actual_model_nfe']==nfe and c['actual_euler_updates']==c['callback_count']==20,'NFE/Euler/callback mismatch')
        t.require(audit['completed_forward_calls']==nfe and audit['completed_calls']==50*nfe and audit['routed_calls']==50*K,'block count mismatch')
        t.require(audit['calls_by_forward']==[50]*nfe and len(c['branches'])==nfe and len(c['steps'])==20 and c['measurements']==[] and c['online_observations']==0 and c['decision_source']=='frozen_static_plan','incomplete histories')
        history=t.read_json(root/'logs'/f'{run}_history.json')
        check_submission(jobs[-1],history,run,t.sha(root/'configs/graphs'/f'{run}.json'))
        t.require(history['status']['status_str']=='success' and history['status']['completed'] is True and history['prompt'][2]==t.read_json(root/'configs/graphs'/f'{run}.json'),'actual Comfy graph/history mismatch')
        branches={(r['physical_index'],r['branch']):r for r in c['branches']}
        t.require(c['full_grid']==t.read_json(root/'configs/parent_captures.json')['sigmas_video'],'actual full grid differs')
        t.require(c['conditioning']['sha256']==__import__('hashlib').sha256(json.dumps(c['conditioning']['tree'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),'condition tree SHA differs')
        canonical_condition(c['conditioning']['tree'])  # Current canonical UUID validity only; historical R38 tree unavailable.
        check_condition_blobs(root,run,c)
        initial=[g for g in c['pair_gates'] if g['gate']=='initial_binding']
        old_cond=t.read_json(root/'configs/parent_conditioning.json');emb=old_cond['conditioning_embedding']
        rel='audit/'+emb['tensor_file'];old_file=Path(t.read_json(root/'PROTOCOL.json')['case']['parent_root'])/rel
        expected_entity=t.read_json(root/'configs/parent_file_inventory.json')[rel]
        t.require(len(initial)==1 and initial[0]['pass'] is True and initial[0]['seed']==SEED and initial[0]['actual_clean_conditions_and_AV_noise_exact'] is True,'initial gate absent')
        t.require(initial[0]['actual_historical_embedding_file']==str(old_file) and initial[0]['actual_historical_embedding_file_sha256']==expected_entity['sha256']==t.sha(old_file),'historical actual embedding binding differs')
        from H3StaticWindowRouter.pair_gate import clean_record,signature_without_bytes
        old_embedding=torch.load(old_file,map_location='cpu',weights_only=True)
        t.require(signature_without_bytes(tensor_signature(old_embedding))==clean_record(emb),'historical actual embedding entity differs')
        t.require(initial[0]['historical_processed_condition_tree']=='not_archived' and initial[0]['historical_packed_input']=='not_archived','historical missing-evidence scope changed')
        t.require(len(branches)==nfe and [r['nfe_index'] for r in c['branches']]==list(range(nfe)),'branch or observation index mismatch')
        policy=StaticPlan()
        for index,step in enumerate(c['steps']):
            t.require(step['physical_index']==index and step['callback_observed_once'],'callback order')
            dec=policy.select(index)
            t.require(all(step['decision'][k]==v for k,v in dec.items()),'automatic selection not reproduced')
            t.require(dec['chosen_full']==(index in mask),'mask mismatch')
            start=index+sum(k<index for k in (6,7,8,9,10,11,12,13,14));expected_nfe=[start,start+1] if index in (6,7,8,9,10,11,12,13,14) else [start]
            t.require(step['nfe_indices']==expected_nfe and step['selected_branch']==('full' if index in (6,7,8,9,10,11,12,13,14) else 'native'),'physical to NFE/choice mismatch')
            chosen=branches[index,'full' if index in mask else 'native']
            t.require(step['chosen_raw_stream_signatures']==chosen['raw_stream_signatures'],'chosen endpoint mismatch')
            for name in ('native','full') if index in mask else ('native',):
                row=branches[index,name];p=t.inside(row['file'],root/'audit/counterfactual')
                t.require(t.sha(p)==row['file_sha256'],'endpoint archive changed')
                value=torch.load(p,map_location='cpu',weights_only=True)
                for key,shape in (('video',(1,24,42,46,82)),('audio',(1,32,2,235))):
                    v=value[key];t.require(v.dtype==torch.float32 and tuple(v.shape)==shape and bool(torch.isfinite(v).all()),'endpoint tensor schema')
                t.require([tensor_signature(value[k]) for k in ('video','audio')]==row['normalized_stream_signatures'],'endpoint signature')
                t.require(all(value['metadata'][k]==row[k] for k in ('physical_index','branch','nfe_index','seed','sigma','sigma_next','condition_sha256','reference_sha256','raw_stream_signatures')) and row['seed']==case['seed'] and row['physical_index']==index and row['branch']==name,'endpoint metadata binding')
                t.require([tensor_signature(value['video']),tensor_signature(value['audio']*4)]==row['raw_stream_signatures'],'endpoint raw signature')
                t.require(row['condition_sha256']==c['conditioning']['sha256'] and row['reference_sha256']==c['reference']['sha256'] and row['sigma']==c['full_grid'][index] and row['sigma_next']==c['full_grid'][index+1],'branch actual condition/ref/grid binding')
                t.require(row['observation'] is None,'fabricated observation')
                t.require(row['global_rng_unchanged'] and row['condition_unchanged'] and row['full_grid_unchanged'],'runtime branch invariant')
                if name=='full':
                    t.require(row['same_input']==branches[index,'native']['same_input'],'same-state branch input mismatch')
                    summary=audit['forward_summaries'][row['nfe_index']]
                    t.require(summary['latent_bins']==dec['latent_bins'],'actual latched union differs')
        first=mask[0] if mask else None
        gates=[g for g in c['pair_gates'] if g['gate']=='native_prefix']
        t.require(len(gates)==nfe,'prefix qualification record incomplete')
        check_branch_ledger(audit,c,gates)
        expected_prefix=t.read_json(root/'PROTOCOL.json')['actual_native_prefix_evidence']
        prefix_proofs=[]
        for g in gates:
            n,b=g['physical_index'],g['branch']
            expected='pass' if b=='native' and n<=6 else 'not_applicable'
            t.require(g['status']==expected,'historical prefix qualification mismatch')
            if expected=='pass':prefix_proofs.append(actual_prefix(branches[n,b],expected_prefix[n],branches[n,b]['file']))
        t.require(len(prefix_proofs)==7,'seven actual Native prefix rechecks required')
        snapshot_folder=root/'audit/counterfactual'/f'{run}_snapshots'
        expected_branch_names=[f'step{i:03d}_native.pt' for i in range(20)]+[f'step{i:03d}_full.pt' for i in (6,7,8,9,10,11,12,13,14)]+[f'step{i:03d}_input_raw.pt' for i in (6,7,8,9,10,11,12,13,14)]+['sampler_final_raw.pt']
        t.require(sorted(p.name for p in snapshot_folder.glob('*.pt'))==sorted(expected_branch_names),'exact branch/input/final tensor inventory differs')
        t.require([x['physical_index'] for x in c['inputs']]==list(range(6,15)),'rawinput inventory differs')
        for inp in c['inputs']:
            n=inp['physical_index'];t.require(t.sha(inp['file'])==inp['file_sha256'],'input PT SHA differs')
            value=torch.load(inp['file'],map_location='cpu',weights_only=True)
            t.require(set(value)=={'packed','metadata'} and value['metadata']=={k:v for k,v in inp.items() if k not in ('file','file_sha256','archive_seconds')},'input metadata')
            t.require(value['packed'].dtype==torch.float32 and tuple(value['packed'].shape)==(1,1,24*42*46*82+32*2*235) and bool(torch.isfinite(value['packed']).all()),'packed input shape/dtype/finite')
            t.require(tensor_signature(value['packed'])==inp['packed_signature']==branches[n,'native']['same_input']==branches[n,'full']['same_input'],'same-state actual input signature differs')
            t.require(inp['full_grid']==c['full_grid'] and inp['seed']==SEED and inp['condition_sha256']==c['conditioning']['sha256'] and inp['reference_sha256']==c['reference']['sha256'],'rawinput binding differs')
        capture=t.read_json(root/'audit/x0'/run/'manifest.json');folder=root/'audit/x0'/run
        t.require(capture['schema']=='h3-x0-readout-v1' and capture['status']=='complete' and capture['callback_count']==capture['expected_callback_count']==20 and capture['capture_steps_zero_based']==list(range(20)),'chosen recorder contract')
        t.require(capture['seed']==c['seed']==case['seed'] and capture['sigmas_video']==c['full_grid'],'chosen seed/grid mismatch')
        t.require(capture['run_id']==run and capture['sampler']=='sample_euler' and capture['audio_scale']==4 and capture['video_latent_scale_factor']==1 and capture['normalization_stage']=='after_process_latent_out' and capture['target_latent_shapes']==[[1,24,42,46,82],[1,32,2,235]],'chosen top-level normalization/shape/sampler')
        records=capture['captures']+[capture['final_sampler_result']]
        names=[f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt']
        t.require([r['file'] for r in records]==names and sorted(p.name for p in folder.glob('*.pt'))==sorted(names),'chosen unique tensor inventory')
        for record in records:
            value=torch.load(t.inside(folder/record['file'],folder),map_location='cpu',weights_only=True)
            t.require(set(value)=={'video','audio','metadata'} and value['metadata']=={k:v for k,v in record.items() if k not in ('file','capture_seconds')},'capture metadata mismatch')
            check_record_semantics(record,capture,case)
            for key,shape in (('video',(1,24,42,46,82)),('audio',(1,32,2,235))):
                v=value[key];t.require(v.dtype==torch.float32 and tuple(v.shape)==shape and bool(torch.isfinite(v).all()) and tensor_signature(v)==record[key],'capture tensor integrity')
            if record['snapshot_kind']=='x0_estimate':
                n=record['step_zero_based'];chosen=branches[n,'full' if n in mask else 'native']
                t.require([tensor_signature(value['video']),tensor_signature(value['audio']*4)]==chosen['raw_stream_signatures'],'chosen raw endpoint mismatch')
            else:
                raw=torch.load(root/'audit/counterfactual'/f'{run}_snapshots/sampler_final_raw.pt',map_location='cpu',weights_only=True)
                t.require(all(torch.equal(value[k],raw[k] if k=='video' else raw[k]*.25) for k in ('video','audio')),'final raw sampler mismatch')
        provenance=t.read_json(root/'configs/runtime_provenance.json')
        t.require(all(provenance['core_matches'].values()) and all(v['size_mtime_match'] and v['prior_full_sha256']==t.read_json(root/'configs/model_hashes_host9.json')[k]['sha256'] for k,v in provenance['models'].items()) and all(t.sha(root/p)==h for p,h in provenance['code'].items()),'actual backend/core/model provenance differs')
        results.append({'run':run,'mask':mask,'bins':list(range(17,38)),'NFE':29,'updates':20,'observations':0,'first_on':6,'blocks':1450,'routes':450,'independent_prefix_recheck':prefix_proofs,'prefix_scope':'actual Native0..6 and chosen0..5 only; later comparison permanently N/A','efficiency':{'job_wall_seconds':jobs[-1]['observed_unix']-jobs[-1]['submitted_unix'],'model_seconds':sum(v['model_seconds_synchronized'] for v in c['branches']),'branch_archive_seconds':sum(v['archive_and_readout_seconds'] for v in c['branches']),'condition_hash_seconds':sum(v['condition_copy_hash_seconds'] for v in c['branches']),'chosen_capture_seconds':sum(v['capture_seconds'] for v in capture['captures']),'online_observer_seconds':0,'final_capture_cost':'included in job wall time'}})
    cleanup=root/'processes/cleanup.json'
    if cleanup.exists():
        d=t.read_json(cleanup);check_owner_evidence(owner,jobs,d);released=True
    elif allow_resident:
        import service
        check_owner_evidence(owner,jobs);service.assert_owned(owner);released=False
    else:raise ValueError('cleanup not recorded; resident verification requires explicit flag')
    t.require(not torch.cuda.is_initialized(),'CPU verifier initialized CUDA')
    return {'status':'pass','cases':results,'runtime_integrity_only':True,'new_method_claim':False,'cleanup_verified':released,'historical_scope':'Actual R38 Native0..6 AV independently reloaded; current same-state Native/Full input equality enforced. Historical full processed/postaugmentation tree and packed preforward inputs unavailable, no equality claim; Full6 and all later states N/A.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(ROOT));p.add_argument('--allow-resident',action='store_true');p.add_argument('--output');a=p.parse_args();result=check(a.root,a.allow_resident)
    if a.output:
        with Path(a.output).open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
