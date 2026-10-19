"""Read-only CPU verification of actual online observations and chosen trajectory."""
import argparse,json,sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from observer_import import t,ROOT

def check_record_semantics(record,capture,case):
    t.require(record['schema']=='h3-x0-readout-v1' and record['seed']==case['seed'] and record['run_id']==case['run_id'] and record['total_steps']==20,'capture semantic metadata')
    t.require(record['geometry']==capture['geometry']=={'width':1312,'height':736,'frames':141,'fps':24},'capture geometry')
    t.require(record['normalization_stage']=='after_process_latent_out' and record['audio_scale']==4.0 and record['video_latent_scale_factor']==1.0,'capture normalization')
    n=record['step_zero_based'];t.require(type(n) is int and 0<=n<20 and record['model_call_one_based']==n+1,'capture step')
    expected='sampler_final' if record['file']=='sampler_final.pt' else 'x0_estimate'
    t.require(record['snapshot_kind']==expected and (expected!='sampler_final' or n==19),'capture kind')
    sigma=0.0 if expected=='sampler_final' else capture['sigmas_video'][n]
    next_sigma=0.0 if expected=='sampler_final' else capture['sigmas_video'][n+1]
    t.require(record['endpoint_sanity']==(n==19) and record['sigma_video']==sigma and record['sigma_next_video']==next_sigma,'capture sigma/endpoint')

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
        t.require(cleanup['process_absent'] and cleanup['own_compute_absent'] and cleanup['child_compute_absent'],'cleanup incomplete')

def check(root=ROOT,allow_resident=False,run_id=None):
    root=Path(root);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path.insert(0,str(root/'extensions'))
    import torch
    torch.set_num_threads(1)
    from H3X0Readout.core import tensor_signature
    from H3AutomaticWindowRouter.selector import Controller
    from r35_contract import validate_job
    t.bindings();t.admission_document(approved=True)
    manifest=t.read_json(root/'deploy_manifest.json')
    for rel,row in manifest['files'].items():t.require(t.sha(root/rel)==row['sha256'],'immutable file changed: '+rel)
    results=[];jobs=[]
    owner=t.read_json(root/'processes/service.json')
    cases=t.read_json(root/'configs/protocol.json')['cases']
    t.require(run_id in [c['run_id'] for c in cases], 'unregistered single-run request')
    for case in cases:
        if case['run_id']!=run_id:continue
        run=case['run_id'];validate_job(run,root,inputs=False)
        jobs.append(t.read_json(root/'logs'/f'{run}_job.json'))
        audit=t.read_json(root/'audit/counterfactual'/f'{run}.json');c=audit['counterfactual'];mask=c['full_physical_indices'];K=len(mask);nfe=20+K
        t.require(audit['status']=='complete' and sorted(set(mask))==mask and 0 not in mask and 0<=K<=19,'invalid complete mask')
        t.require(c['actual_model_nfe']==nfe and c['actual_euler_updates']==c['callback_count']==20,'NFE/Euler/callback mismatch')
        t.require(audit['completed_forward_calls']==nfe and audit['completed_calls']==50*nfe and audit['routed_calls']==50*K,'block count mismatch')
        t.require(audit['calls_by_forward']==[50]*nfe and len(c['branches'])==nfe and len(c['steps'])==20 and len(c['measurements'])==20,'incomplete histories')
        history=t.read_json(root/'logs'/f'{run}_history.json')
        check_submission(jobs[-1],history,run,t.sha(root/'configs'/f'{run}.json'))
        t.require(history['status']['status_str']=='success' and history['status']['completed'] is True and history['prompt'][2]==t.read_json(root/'configs'/f'{run}.json'),'actual Comfy graph/history mismatch')
        branches={(r['physical_index'],r['branch']):r for r in c['branches']};measurements={m['physical_index']:m for m in c['measurements']}
        t.require(len(branches)==nfe and sorted(measurements)==list(range(20)) and [r['nfe_index'] for r in c['branches']]==list(range(nfe)),'branch or observation index mismatch')
        policy=Controller()
        for index,step in enumerate(c['steps']):
            t.require(step['physical_index']==index and step['callback_observed_once'],'callback order')
            m=measurements[index];dec=policy.select(index,m)
            t.require(all(step['decision'][k]==v for k,v in dec.items()),'automatic selection not reproduced')
            t.require(dec['chosen_full']==(index in mask),'mask mismatch')
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
                t.require(row['global_rng_unchanged'] and row['condition_unchanged'] and row['full_grid_unchanged'],'runtime branch invariant')
                if name=='full':
                    t.require(row['same_input']==branches[index,'native']['same_input'],'same-state branch input mismatch')
                    summary=audit['forward_summaries'][row['nfe_index']]
                    t.require(summary['latent_bins']==dec['latent_bins'],'actual latched union differs')
            r=t.read_json(m['request_file']);response=t.validate_response(t.read_json(m['response_file']),r,m['request_sha256'])
            t.require(t.sha(m['request_file'])==m['request_sha256'] and t.sha(m['response_file'])==m['response_sha256'],'request/response changed')
            t.require(r['endpoint_file_sha256']==branches[index,'native']['file_sha256'] and r['seed']==case['seed'] and r['physical_index']==index and r['run_id']==run,'observer current native binding')
            for name in ('decode','pose','observer'):t.require(t.sha(response[name]['file'])==response[name]['sha256'],'observer archive changed')
            t.require(t.read_json(response['observer']['file'])==m['observer'],'measurement differs')
            decode=t.read_json(response['decode']['file'])
            t.require(decode['status']=='complete' and decode['fallback_guard']['calls']==0 and decode['fallback_guard']['installed'],'decode complete/fallback')
            t.require(decode['decoded_shape']==[141,736,1312,3] and decode['fps']==24 and len(decode['preencode_rgb24_frame_sha256'])==141,'decoder timebase')
        initial=[g for g in c['pair_gates'] if g['gate']=='initial_binding']
        t.require(len(initial)==1 and initial[0]['pass'] is True and initial[0]['seed']==case['seed'] and initial[0]['actual_noise_and_producer_clean_inputs_exact'] is True,'initial input binding missing')
        embedding=initial[0]['archived_embedding_tensor'];old_condition=t.read_json(root/case['parent_conditioning'])
        from H3AutomaticWindowRouter.pair_gate import clean_record
        t.require('tensor_file' not in old_condition['conditioning_embedding'],'historical embedding contract changed')
        t.require(embedding['actual_signature_equal'] is True and embedding['signature']==clean_record(old_condition['conditioning_embedding']) and embedding['actual_tensor_equal'] is None and embedding['historical_tensor_available'] is False,'runtime actual embedding signature gate unbound')
        first=mask[0] if mask else None
        gates=[g for g in c['pair_gates'] if g['gate']=='native_prefix']
        t.require(len(gates)==nfe,'prefix qualification record incomplete')
        oldcap=t.read_json(root/case['parent_captures'])
        available={r['step_zero_based'] for r in oldcap['captures']}
        for g in gates:
            n,b=g['physical_index'],g['branch']
            expected='not_applicable' if b=='full' or (first is not None and n>first) else ('pass' if n in available else 'unavailable_historical_capture')
            t.require(g['status']==expected,'historical prefix qualification mismatch')
        capture=t.read_json(root/'audit/x0'/run/'manifest.json');folder=root/'audit/x0'/run
        t.require(capture['schema']=='h3-x0-readout-v1' and capture['status']=='complete' and capture['callback_count']==capture['expected_callback_count']==20 and capture['capture_steps_zero_based']==list(range(20)),'chosen recorder contract')
        t.require(capture['seed']==c['seed']==case['seed'] and capture['sigmas_video']==c['full_grid'],'chosen seed/grid mismatch')
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
                if first is None:
                    oldpath=Path(case['parent_root'])/'audit/x0'/case['parent_run']/oldcap['final_sampler_result']['file']
                    old=torch.load(oldpath,map_location='cpu',weights_only=True)
                    t.require(all(tensor_signature(old[k])==oldcap['final_sampler_result'][k] and torch.equal(value[k],old[k]) for k in ('video','audio')),'all-OFF final Native replay mismatch')
        results.append({'run':run,'mask':mask,'NFE':nfe,'updates':20,'observations':20,'first_on':first,'case_role':'source07 previously inspected development transfer','prefix_scope':'old Native only005/010/015/019; compare eligible current Native through firstON; earlyON<5 means prefix unavailable, never postponed','all_OFF_final_exact':not bool(mask)})
    cleanup=root/'processes/cleanup.json'
    if cleanup.exists():
        d=t.read_json(cleanup);check_owner_evidence(owner,jobs,d);released=True
    elif allow_resident:
        import service
        check_owner_evidence(owner,jobs);service.assert_owned(owner);released=False
    else:raise ValueError('cleanup not recorded; resident verification requires explicit flag')
    t.require(not torch.cuda.is_initialized(),'CPU verifier initialized CUDA')
    return {'status':'pass','cases':results,'runtime_integrity_only':True,'new_method_claim':False,'cleanup_verified':released,'historical_scope':'runtime prefix/clean embedding gates are records, not independent postrun recomputation; exact historical final rechecked only all-OFF. R27 decoder bridge inherited with explicit source-accuracy limits.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(ROOT));p.add_argument('--allow-resident',action='store_true');p.add_argument('--run',required=True);p.add_argument('--output',required=True);a=p.parse_args();result=check(a.root,a.allow_resident,a.run)
    t.write_new(a.output,result);print(json.dumps(result,indent=2))
