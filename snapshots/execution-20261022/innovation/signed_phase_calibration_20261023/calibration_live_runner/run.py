"""CPU-only, all-inputs-first orchestration of frozen live calibration functions."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,math,os,shutil,sys,tempfile,types
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
METHODS=('native','global_weak');STEPS=(9,19)
class Pending(Exception):pass
class Invalid(ValueError):pass

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def dump(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load_module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def dependencies():
    root=HERE.parent;locked=read(HERE/'DEPENDENCIES.json')
    for name,digest in locked['files_sha256'].items():
        if sha(root/name)!=digest:raise Invalid('frozen dependency changed: '+name)
    live=load_module('_live_runner_eval',root/'calibration_live/evaluate_live.py')
    old=sys.modules.get('evaluate_live');sys.modules['evaluate_live']=live
    try:paired=load_module('_live_runner_pair',root/'calibration_live/paired_readout.py')
    finally:
        if old is None:sys.modules.pop('evaluate_live',None)
        else:sys.modules['evaluate_live']=old
    rec=load_module('_live_runner_reconstruct',root/'replay/reconstruct.py')
    return {'root':root,'locked':locked,'live':live,'base':live.base,'paired':paired,'rec':rec,
            'plan':read(root/'calibration_live/PLAN.json'),'numeric':read(root/'replay_diagnostics/POLICY.json')}

def paths_from_manifest(path):
    p=Path(path)
    if not p.is_file():raise Pending('input manifest missing')
    doc=read(p)
    if doc.get('schema')!='h3-live-calibration-runner-input-v1':raise Invalid('runner input schema differs')
    paths={};missing=[]
    def add(key,value):
        if not isinstance(value,str) or not value:missing.append(key);return
        value=Path(value);value=value if value.is_absolute() else p.parent/value
        paths[key]=value
        if not value.is_file():missing.append(key)
    add('annotations',doc.get('annotations'))
    keys=set(doc.get('methods',{}))
    if keys-set(METHODS):raise Invalid('unknown method in input manifest')
    if keys!=set(METHODS):raise Pending('both native and global_weak paths required')
    for method in METHODS:
        m=doc['methods'][method]
        for key in ('science_contract','trajectory_gate','observation_manifest','video','annotation_record'):add(method+'.'+key,m.get(key))
        keys=set(m.get('captures',{}))
        if keys-{'9','19'}:raise Invalid('unknown capture step for '+method)
        if keys!={'9','19'}:raise Pending('exactly steps9/19 paths required for '+method)
        for step in STEPS:
            for key in ('qk','state','numerical_check'):add(f'{method}.{step}.{key}',m['captures'][str(step)].get(key))
    if missing:raise Pending('required inputs missing: '+', '.join(missing))
    return paths

def require(condition,message):
    if not condition:raise Invalid(message)

def numeric_check(report,qk_hash,capture,env):
    policy=env['numeric'];expected=env['locked']['files_sha256']['replay_diagnostics/POLICY.json']
    require(report.get('schema')=='h3-passive-qk-numerical-diagnostic-v1' and report.get('capture_sha256')==qk_hash,'numeric capture identity differs')
    require(report.get('policy_sha256')==expected and report.get('numerical_definition_pass') is True,'fixed numerical policy did not pass')
    require(report.get('forward_identity')==capture['forward_identity'],'numeric forward identity differs')
    for key in ('case','method','step_zero_based','layer_zero_based'):require(report.get(key)==capture[key],'numeric metadata differs: '+key)
    require(set(report.get('branches',{}))=={'Q_C','Q_R','K_R'},'all three numerical branches required')
    for name,b in report['branches'].items():
        require(b.get('dtype')=='torch.bfloat16' and b.get('shape')==[32,8,56,128] and b.get('numerical_definition_pass') is True,'numerical geometry/dtype/branch differs')
        rows=b.get('full',[]);require(len(rows)==56 and [r.get('head') for r in rows]==list(range(56)),'all56 numerical heads in fixed order required')
        for r in rows:
            require(r.get('numerical_definition_pass') is True,'numerical head failed')
            for metric in ('nrmse','p99_abs_over_actual_rms','max_abs_over_actual_rms'):
                value=r.get(metric);require(type(value) in (int,float) and math.isfinite(value) and 0<=value<=policy['head_gate'][metric],'numerical per-head limit failed: '+metric)

def geometry(c,torch):
    require((c.get('heads'),c.get('head_dim'),c.get('rot_dim'))==(56,128,96),'fixed H3 geometry differs')
    require(c.get('spatial_ids')==[0,135,269,404,538,673,807,942],'fixed8 spatial probes differ')
    spans=[];start=0
    for t in range(32):
        width=(1,4,4,4,4)[t%5];spans.append([start,start+width-1]);start+=width
    require(c.get('physical_frame_spans_inclusive')==spans,'full physical time support differs')
    require(c.get('valid_bins')==[b<105 for a,b in spans],'complete-valid-bin mask differs')
    require(c.get('time_role')==[i%5 for i in range(32)],'time role metadata differs')
    for name in ('raw_Q_C','raw_Q_R','raw_K_R','actual_Q_C','actual_Q_R','actual_K_R'):
        x=c.get(name);require(isinstance(x,torch.Tensor) and x.device.type=='cpu' and list(x.shape)==[32,8,56,128] and x.dtype==torch.bfloat16 and bool(torch.isfinite(x).all()),'fixed finite BF16 capture required: '+name)
    for name in ('q_norm_weight','k_norm_weight'):
        x=c.get(name);require(isinstance(x,torch.Tensor) and list(x.shape)==[128] and bool(torch.isfinite(x).all()),'actual norm weight missing')
    require(c.get('q_norm_eps')==1e-5 and c.get('k_norm_eps')==1e-5,'actual norm epsilon differs')

def preflight(paths,env):
    import torch
    torch.set_num_threads(1);torch.set_grad_enabled(False)
    annotations=read(paths['annotations'])
    if annotations.get('status') in ('pending','unreviewed'):raise Pending('new full-video event annotation pending')
    plan_sha=env['locked']['files_sha256']['calibration_live/PLAN.json']
    env['live'].validate_events(annotations,env['plan'],plan_sha)
    captures={};provenance={'annotations_sha256':sha(paths['annotations']),'plan_sha256':plan_sha,'methods':{}}
    baseline_geometry=None
    for method in METHODS:
        def path(k):return paths[method+'.'+k]
        science=read(path('science_contract'));science_sha=sha(path('science_contract'))
        require(science_sha==env['locked']['science_contract_sha256'][method],'frozen runtime science contract differs')
        contract={'science_contract_sha256':science_sha,'sample_sigmas_video':science['sigmas_video'],'noise_sha256':science['noise_tensor_sha256']}
        gate=read(path('trajectory_gate'));observation=read(path('observation_manifest'));video=annotations['video_provenance'][method]
        require(gate.get('schema')=='h3-live-phase-trajectory-gate-v1' and gate.get('passed') is True,'trajectory gate failed or schema differs')
        require(sha(path('video'))==video['sha256']==gate.get('actual_video_sha256'),'new actual video byte identity differs')
        require(sha(path('annotation_record'))==video['annotation_record_sha256'],'new annotation record changed')
        require(video['frame_count']==science['frames']==107,'complete new video frame count differs')
        record=read(path('annotation_record'))
        require(record.get('schema')=='h3-live-phase-single-video-annotation-v1' and record.get('complete_new_video_reviewed') is True,'complete single-video annotation required')
        for key,value in {'video_sha256':video['sha256'],'trajectory_id':video['trajectory_id'],'case_id':'short_0358','method':method,'annotation_source':'new_complete_video','frame_count':107,'valid_frames':105,'fps':24,'inspected_frames':[0,104]}.items():
            require(record.get(key)==value,'single-video annotation provenance differs: '+key)
        require([e['id'] for e in record['events']]==[e['id'] for e in annotations['events']],'single-video event set differs')
        for row,merged in zip(record['events'],annotations['events']):
            observed=merged[method]
            require(row.get('source')==merged['source'] and row.get('status')==observed['status'] and row.get('interval')==observed.get('interval'),'single-video/merged event differs')
            if observed['status']=='observed':require(row['interval'][1]<105,'event lies outside complete inspected frames')
            else:require(row.get('reason')==observed['reason'],'single-video missing-event reason differs')
        require(sha(path('observation_manifest'))==gate.get('observation_manifest_sha256'),'observation manifest byte identity differs')
        if observation.get('status') in ('pending','running'):raise Pending('observation is not complete')
        require(observation.get('status')=='complete','observation failed or status unknown')
        for key in ('trajectory_id','case','method','science_contract_sha256','callback_count','actual_model_forward_count','completed_blocks','extra_model_forward_calls'):
            require(observation.get(key)==gate.get(key),'observation/gate differs: '+key)
        require(observation.get('original_result_returned_without_copy') is True,'original sampler return proof absent')
        expected_shapes=science['target_shapes'];packed_shape=[1,1,sum(math.prod(s[1:]) for s in expected_shapes)]
        require(observation.get('target_shapes')==expected_shapes and observation.get('sample_sigmas_video')==science['sigmas_video'],'observation AV/sigma geometry differs')
        require(observation.get('noise',{}).get('sha256')==contract['noise_sha256'],'actual initial noise differs')
        final=observation.get('final_raw_result',{})
        require(final.get('shape')==packed_shape and final.get('dtype')=='torch.float32' and final.get('finite') is True,'full final AV result missing')
        obsrows=observation.get('captures',[]);require(len(obsrows)==2 and [r.get('step_zero_based') for r in obsrows]==[9,19],'complete observer capture pair required')
        method_prov={'science_contract_sha256':science_sha,'gate_sha256':sha(path('trajectory_gate')),'observation_manifest_sha256':sha(path('observation_manifest')),'actual_video_sha256':video['sha256'],'annotation_record_sha256':video['annotation_record_sha256'],'captures':{}}
        for step in STEPS:
            cp=path(f'{step}.qk');sp=path(f'{step}.state');npth=path(f'{step}.numerical_check')
            qhash=sha(cp);statehash=sha(sp);c=torch.load(cp,map_location='cpu',weights_only=True)
            env['live'].validate_gate(c,qhash,gate,annotations,method,contract);geometry(c,torch)
            identity=c['forward_identity'];require(statehash==identity['state_file_sha256'],'actual AV state byte identity differs')
            obsrow=next(r for r in obsrows if r['step_zero_based']==step)
            require(obsrow.get('qk_sha256')==qhash and obsrow.get('state_file_sha256')==statehash and obsrow.get('forward_identity')==identity,'observer/capture binding differs')
            state=torch.load(sp,map_location='cpu',weights_only=True)
            require(state.get('schema')=='h3-live-phase-state-v1' and state.get('step_zero_based')==step and state.get('target_shapes')==expected_shapes and state.get('sample_sigmas_video')==science['sigmas_video'],'actual state metadata differs')
            for name in ('packed_x','raw_packed_x0'):
                x=state.get(name);require(isinstance(x,torch.Tensor) and x.dtype==torch.float32 and list(x.shape)==packed_shape,'complete actual AV tensor required')
                require(env['rec'].tensor_info(x)==identity[name],'actual AV tensor signature differs: '+name)
            del state
            numeric_check(read(npth),qhash,c,env)
            if baseline_geometry is None:baseline_geometry=c
            else:
                for key in ('spatial_ids','valid_bins','physical_frame_spans_inclusive','time_role','q_norm_eps','k_norm_eps'):require(c[key]==baseline_geometry[key],'cross-capture geometry differs: '+key)
                for key in ('q_norm_weight','k_norm_weight','position_canvas','position_reference','rope_canvas','rope_reference'):
                    a,b=c.get(key),baseline_geometry.get(key)
                    require(isinstance(a,torch.Tensor) and isinstance(b,torch.Tensor) and a.dtype==b.dtype and torch.equal(a,b),'cross-capture norm/layout differs: '+key)
            captures[(method,step)]=c
            method_prov['captures'][str(step)]={'qk_sha256':qhash,'state_sha256':statehash,'numerical_check_sha256':sha(npth),'forward_identity':identity}
        provenance['methods'][method]=method_prov
    return {'captures':captures,'annotations':annotations,'provenance':provenance}

def analyze(data,env):
    base=env['base'];paired=env['paired'];steps=[];archives={}
    for step in STEPS:
        c={m:data['captures'][(m,step)] for m in METHODS};features={}
        for m in METHODS:
            def a(k):return c[m][k].detach().float().numpy()
            features[m]={name:base.normalized_content(a(key),a(weight),c[m][eps]) for name,key,weight,eps in [('q','raw_Q_C','q_norm_weight','q_norm_eps'),('qr','raw_Q_R','q_norm_weight','q_norm_eps'),('k','raw_K_R','k_norm_weight','k_norm_eps')]}
        n,w=features['native'],features['global_weak'];valid=np.asarray(c['native']['valid_bins'],bool);spans=np.asarray(c['native']['physical_frame_spans_inclusive'])
        pairs={'qn_kn':(n['q'],n['k']),'qw_kw':(w['q'],w['k']),'qw_kn':(w['q'],n['k']),'qn_kw':(n['q'],w['k']),'qrn_kn':(n['qr'],n['k']),'qrw_kw':(w['qr'],w['k'])}
        prob={key:base.retrieval_probabilities(q,k,valid) for key,(q,k) in pairs.items()}
        report,arrays=paired.compare(prob['qn_kn'],prob['qw_kw'],prob['qrn_kn'],prob['qrw_kw'],spans,valid,env['plan']['events'])
        cross=paired.cross_key_decomposition(prob['qn_kn'],prob['qw_kw'],prob['qw_kn'],prob['qn_kw'],spans,valid)
        events=[]
        for event in env['plan']['events']:
            lo,hi=event['source_interval_frames'];bins=np.flatnonzero(valid&(spans[:,0]<=hi)&(spans[:,1]>=lo))
            row={'event_id':event['id'],'common_query_bins':bins.tolist()}
            if not len(bins):row['status']='missing_source_bin_support'
            else:row.update(status='measured_at_identical_query_times',query_contribution=base.quantiles(cross['query_contribution'][:,bins]),key_contribution=base.quantiles(cross['key_contribution'][:,bins]))
            events.append(row)
        description={m:env['live'].summarize_live(prob['qn_kn' if m=='native' else 'qw_kw'],prob['qrn_kn' if m=='native' else 'qrw_kw'],spans,valid,data['annotations'],m) for m in METHODS}
        steps.append({'step_zero_based':step,'layer_zero_based':25,'paired':report,'cross_key':{'events':events,'max_decomposition_error':cross['max_decomposition_error'],'interpretation':read(env['root']/'calibration_live/CROSS_KEY_POLICY.json')['interpretation']},'event_selected_descriptive_only':description})
        archives[step]={**prob,**arrays,**{k:v for k,v in cross.items() if isinstance(v,np.ndarray)},'spatial_ids':np.asarray(c['native']['spatial_ids'])}
    summary={'schema':'h3-live-paired-calibration-summary-v1','case':'short_0358','status':'complete','steps':steps,'provenance':data['provenance'],'policy_sha256':{k:env['locked']['files_sha256']['calibration_live/'+k] for k in ('PLAN.json','PAIRED_READOUT_POLICY.json','CROSS_KEY_POLICY.json')},'all_heads':56,'all_probes':8,'all_time_bins':32,'semantic_phase_validated':False,'alpha_control_deployed':False,'extra_gpu_calls':0}
    return summary,archives

def run(inputs,output):
    out=Path(output)
    if out.exists():raise FileExistsError(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    try:
        paths=paths_from_manifest(inputs);env=dependencies();data=preflight(paths,env)
        summary,archives=analyze(data,env)
        with tempfile.TemporaryDirectory(prefix='.live-calibration-',dir=out.parent) as tmp:
            tmp=Path(tmp)
            for step,values in archives.items():np.savez_compressed(tmp/f'step{step:03d}_all_probabilities.npz',**values)
            summary['npz_files']={p.name:sha(p) for p in tmp.glob('*.npz')}
            dump(tmp/'summary.json',summary);dump(tmp/'STATUS.json',{'status':'complete','results_written':True,'summary_sha256':sha(tmp/'summary.json')})
            os.replace(tmp,out)  # Publish all results as one directory rename.
        return read(out/'STATUS.json')
    except (Pending,ValueError,KeyError,TypeError,OSError,RuntimeError) as error:
        # No probability files are written until every prerequisite has passed.
        status='pending' if isinstance(error,Pending) else 'invalid'
        out.mkdir(exist_ok=False)
        result={'status':status,'results_written':False,'reason':type(error).__name__+': '+str(error)};dump(out/'STATUS.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']=''
    result=run(a.inputs,a.output);print(json.dumps(result,ensure_ascii=False));return 0 if result['status'] in ('complete','pending') else 2
if __name__=='__main__':raise SystemExit(main())
