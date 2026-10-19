"""Frozen CPU-only native-feature prediction audit. Never loads a model/GPU."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

os.environ['CUDA_VISIBLE_DEVICES']=''
import torch

HERE=Path(__file__).resolve().parent
CALIB=(0,2,4,6,8)
HEADS=(0,14,28,42)
STEPS=(6,10,14)
SPLITS={'val':(10,11,12),'event':(14,15,16,17,18),'post':tuple(range(20,41))}
TILES=tuple((y,x) for y in range(1,20,3) for x in range(1,38,3))
NEIGHBORS=tuple((dy,dx) for dy in (-1,0,1) for dx in (-1,0,1) if (dy,dx)!=(0,0))
METHODS=('I','D','A','M')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def tensor_info(x):
    if x.device.type!='cpu':raise ValueError('CPU tensors only')
    x=x.contiguous()
    return {'shape':list(x.shape),'dtype':str(x.dtype),'sha256':hashlib.sha256(x.view(torch.uint8).numpy()).hexdigest()}


def write_json(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def load_json(path):return json.loads(Path(path).read_text())


def bin_times(locator):
    rows=locator['position_mapping']
    if len(rows)!=42:raise ValueError('42 actual position-bin rows required')
    spans=[];cursor=0
    for i,row in enumerate(rows):
        a,b=row['position_bin_frames_inclusive']
        if row['latent_bin']!=i or a!=cursor or b<a:raise ValueError('non-contiguous bin table')
        spans.append((a,b));cursor=b+1
    if cursor!=141:raise ValueError('position-bin table must cover141 frames')
    return torch.tensor([(a+b)/48. for a,b in spans],dtype=torch.float64),spans


def check_condition(condition,locator):
    calls=condition['native_vae_calls']
    if len(calls)!=2 or calls[1]['latent']['shape']!=[1,24,42,46,82]:raise ValueError('unexpected reference geometry/order')
    old=locator['actual_pair_snapshot_reference']['clean_latent']
    if calls[1]['latent']['sha256']!=old['sha256']:raise ValueError('actual clean-reference hash differs; cannot reuse frozen bin audit')
    if calls[1]['prepared_frames']['shape']!=[141,736,1312,3]:raise ValueError('actual prepared RGB geometry mismatch')
    if condition['packed_layout']['seq_len']!=87592:raise ValueError('unexpected actual packed length')
    return calls[1]['prepared_frames']


def freeze_groups(condition_path,locator_path,audit_root,output):
    """Run before reading target features. Only actual prepared source RGB used."""
    c=load_json(condition_path);l=load_json(locator_path);meta=check_condition(c,l);_,spans=bin_times(l)
    base={'schema':'h3-source-only-frozen-groups-v1','protocol_sha256':sha(HERE/'FROZEN_PROTOCOL.txt'),
          'condition_sha256':sha(condition_path),'locator_sha256':sha(locator_path),
          'prepared_tensor_expected':meta,'tiles':[list(t) for t in TILES],
          'source_only':True,'target_features_read':False,'fps':24}
    path=Path(audit_root)/meta['tensor_file']
    if not path.is_file():
        base.update(status='unavailable',reason='Actual prepared RGB tensor file unavailable; no guessed geometry substitute',high=[],low=[])
        write_json(output,base);return base
    rgb=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
    if not isinstance(rgb,torch.Tensor) or tensor_info(rgb)!={k:meta[k] for k in ('shape','dtype','sha256')}:raise ValueError('prepared RGB content hash/shape/dtype mismatch')
    reps=[math.floor((a+b)/2+.5) for a,b in spans]
    scores=torch.zeros(len(TILES),dtype=torch.float64)
    for i in SPLITS['event']:
        diff=(rgb[reps[i+1]]-rgb[reps[i]]).abs()
        if not bool(torch.isfinite(diff).all()):raise ValueError('nonfinite prepared source RGB')
        grid=diff.reshape(23,32,41,32,3).double().mean((1,3,4))
        for j,(y,x) in enumerate(TILES):scores[j]+=grid[y-1:y+2,x-1:x+2].mean()
    values=[float(v) for v in scores]
    low=sorted(range(len(TILES)),key=lambda i:(values[i],TILES[i]))[:23]
    high=sorted(range(len(TILES)),key=lambda i:(-values[i],TILES[i]))[:23]
    base.update(status='available',prepared_file=str(path),prepared_file_sha256=sha(path),
                representative_frames=reps,event_edges=list(SPLITS['event']),
                scores=[{'center':list(t),'score':values[i]} for i,t in enumerate(TILES)],
                high=[list(TILES[i]) for i in high],low=[list(TILES[i]) for i in low],
                metric='sum over5 event edges of mean absolute prepared source RGB difference in fixed3x3 patch tile')
    write_json(output,base);return base


def validate_groups(groups,prepared_metadata):
    if groups.get('source_only') is not True or groups.get('target_features_read') is not False:
        raise ValueError('source-only grouping declaration missing')
    if groups.get('prepared_tensor_expected')!=prepared_metadata or groups.get('tiles')!=[list(t) for t in TILES]:
        raise ValueError('group source metadata/fixed spatial tiles differ')
    if groups['status']=='unavailable':
        if groups.get('high') or groups.get('low'):raise ValueError('unavailable source activity cannot supply selected ROI')
        return
    if groups['status']!='available':raise ValueError('unknown source-group status')
    scores=groups['scores']
    if len(scores)!=len(TILES) or [r['center'] for r in scores]!=[list(t) for t in TILES]:
        raise ValueError('source tile scores do not follow fixed order')
    values=[r['score'] for r in scores]
    if not all(math.isfinite(v) and v>=0 for v in values):raise ValueError('invalid source activity score')
    for name,sign in (('high',-1),('low',1)):
        indices=sorted(range(len(TILES)),key=lambda i:(sign*values[i],TILES[i]))[:23]
        if groups[name]!=[list(TILES[i]) for i in indices]:raise ValueError('source activity group differs from frozen ranking')


def fit_map(rc,yc):
    """Rows are40 frozen state/outer-position pairs, no held-out samples."""
    r=rc.double()-rc.double().mean(0);y=yc.double()-yc.double().mean(0)
    gram=r@r.T;trace=float(gram.trace())
    if not math.isfinite(trace) or trace<=0:return None,{'status':'unknown','reason':'zero_or_nonfinite_source_calibration_energy'}
    lam=1e-3*trace/r.shape[0]
    if not bool(torch.isfinite(y).all()):return None,{'status':'unknown','reason':'nonfinite_target_calibration'}
    try:
        _,sing,vh=torch.linalg.svd(y,full_matrices=False)
    except torch.linalg.LinAlgError:
        return None,{'status':'unknown','reason':'calibration_svd_failed'}
    if len(sing)==0 or float(sing[0])<=0:return None,{'status':'unknown','reason':'rank_zero_target_calibration'}
    keep=sing>1e-3*sing[0];rank=int(keep.sum())
    if rank==0:return None,{'status':'unknown','reason':'rank_zero_target_calibration'}
    system=gram+lam*torch.eye(len(rc),dtype=torch.float64)
    try:
        coeff=torch.linalg.solve(system,y)
    except torch.linalg.LinAlgError:
        return None,{'status':'unknown','reason':'fixed_lambda_solve_failed_no_retuning'}
    diag=(r*y).sum(0)/(r.square().sum(0)+lam)
    try:
        condition_number=float(torch.linalg.cond(system))
    except torch.linalg.LinAlgError:
        return None,{'status':'unknown','reason':'condition_number_decomposition_failed'}
    if not math.isfinite(condition_number) or not bool(torch.isfinite(coeff).all()) or not bool(torch.isfinite(diag).all()):
        return None,{'status':'unknown','reason':'nonfinite_fixed_map_solution'}
    basis=vh[keep]
    fit=r@r.T@coeff;den=float(y.square().sum())
    info={'status':'fit','lambda':lam,'rank':rank,'singular_max':float(sing[0]),
          'singular_min_all':float(sing[-1]),'singular_min_retained':float(sing[keep][-1]),
          'condition_number':condition_number,
          'centered_fit_nmse':float((fit-y).square().sum())/den if den>0 else None,
          'calibration_samples':len(rc),'low_rank_note':'rank1 remains reported; rank0 rejects;25% energy gate controls identifiable coverage'}
    return {'r':r,'coeff':coeff,'diag':diag,'basis':basis},info


def project(x,basis):return (x@basis.T)@basis


def predict_edge(r0,r1,y0,dr,dt,fit):
    """r0/y0 are3x3 tiles at edge START; no target future in predictors."""
    jr=torch.stack(((r0[1,2]-r0[1,0])/2,(r0[2,1]-r0[0,1])/2),dim=-1)
    jy=torch.stack(((y0[1,2]-y0[1,0])/2,(y0[2,1]-y0[0,1])/2),dim=-1)
    jgram=jr.T@jr;tr=float(jgram.trace());reason=None;displacement=None
    if tr==0:
        if bool((dr!=0).any()):a=None;reason='zero_source_gradient_nonzero_change'
        else:a=torch.zeros_like(dr);displacement=0.
    elif not math.isfinite(tr):a=None;reason='nonfinite_source_gradient'
    else:
        eta=1e-3*tr/2
        try:
            u=-torch.linalg.solve(jgram+eta*torch.eye(2,dtype=torch.float64),jr.T@dr)
        except torch.linalg.LinAlgError:
            a=None;reason='fixed_eta_advection_solve_failed_no_retuning'
        else:
            displacement=float(torch.linalg.vector_norm(u*dt))
            if not math.isfinite(displacement):
                a=None;reason='nonfinite_advection_displacement';displacement=None
            elif displacement>1:a=None;reason='advection_outside_one_token_linear_range'
            else:a=-jy@u
    pred={'I':dr,'D':fit['diag']*dr,'A':a,'M':(dr@fit['r'].T)@fit['coeff']}
    if any(p is not None and not bool(torch.isfinite(p).all()) for p in pred.values()):reason='nonfinite_prediction'
    return pred,{'advection_status':'valid' if a is not None and reason is None else 'unknown',
                 'advection_reason':reason,'advection_displacement_tokens':displacement}


def edge_record(reference,target,tau,fit,edge):
    dt=float(tau[edge+1]-tau[edge]);r0=reference[edge];r1=reference[edge+1];y0=target[edge]
    if dt<=0 or not math.isfinite(dt):raise ValueError('non-positive or nonfinite actual bin time difference')
    if any(not bool(torch.isfinite(t).all()) for t in (r0,r1,y0,target[edge+1,1,1])):
        return {'edge':edge,'delta_time_seconds':dt,'status':'unknown','reason':'nonfinite_heldout_feature'}
    dr=(r1[1,1]-r0[1,1])/dt;dy=(target[edge+1,1,1]-y0[1,1])/dt
    preds,extra=predict_edge(r0,r1,y0,dr,dt,fit)
    projected=project(dy,fit['basis']);target_energy=float(projected.square().sum())
    record={'edge':edge,'delta_time_seconds':dt,'target_projected_energy':target_energy,
            'target_full_energy':float(dy.square().sum()),**extra}
    if any(p is None or not bool(torch.isfinite(p).all()) for p in preds.values()):
        record.update(status='unknown',reason=extra['advection_reason'] or 'nonfinite_prediction');return record
    record['status']='valid';record['methods']={}
    for name,p in preds.items():
        pp=project(p,fit['basis']);pn=float(pp.square().sum());den=math.sqrt(pn*target_energy)
        record['methods'][name]={'sse':float((pp-projected).square().sum()),
            'full_sse':float((p-dy).square().sum()),'pred_energy':pn,
            'cosine':float((pp*projected).sum())/den if den>0 else None}
    return record


def summarize(records,nominal):
    valid=[r for r in records if r['status']=='valid']
    target=sum(r['target_projected_energy'] for r in valid);full=sum(r['target_full_energy'] for r in valid)
    result={'nominal_count':nominal,'common_count':len(valid),'common_fraction':len(valid)/nominal if nominal else None,
            'projected_target_energy':target,'full_target_energy':full,
            'identifiable_energy_fraction':target/full if full>0 else None,
            'status':'valid' if valid and target>0 and full>0 else 'unknown','methods':{}}
    for method in METHODS:
        sse=sum(r['methods'][method]['sse'] for r in valid);energy=sum(r['methods'][method]['pred_energy'] for r in valid)
        cos=[r['methods'][method]['cosine'] for r in valid if r['methods'][method]['cosine'] is not None]
        quant=torch.quantile(torch.tensor(cos,dtype=torch.float64),torch.tensor([.1,.5,.9],dtype=torch.float64)).tolist() if cos else None
        result['methods'][method]={'nmse':sse/target if target>0 else None,'sse':sse,
            'full_nmse':sum(r['methods'][method]['full_sse'] for r in valid)/full if full>0 else None,
            'norm_ratio':math.sqrt(energy/target) if target>0 else None,'cosine_q10_median_q90':quant}
    result['support_gate']=(result['common_fraction'] is not None and result['common_fraction']>=.8
                            and result['identifiable_energy_fraction'] is not None and result['identifiable_energy_fraction']>=.25)
    return result


def load_feature(path,record,condition):
    if sha(path)!=record['sha256']:raise ValueError('feature file SHA mismatch')
    data=torch.load(path,map_location='cpu',weights_only=True,mmap=True);meta=data['metadata']
    if meta!=record['metadata']:raise ValueError('payload/audit metadata disagree')
    if meta['mode']!='native' or meta['block_index']!=25 or meta['forward_index'] not in STEPS or meta['head_indices']!=list(HEADS):raise ValueError('feature mode/block/call/head mismatch')
    if meta['grid']!=[42,23,41] or meta['source_shape']!=[1,87592,7168] or 'before native Attention.out_proj' not in meta['stage']:raise ValueError('feature grid/source stage mismatch')
    if meta['layout']['segments']!=condition['packed_layout']['segments']:raise ValueError('feature/condition packed segments mismatch')
    actual_segments=condition['packed_layout']['segments']
    references=[s[:2] for s in actual_segments if s[2]=='ref_img' and s[1]-s[0]==42*23*41]
    targets=[s[:2] for s in actual_segments if s[2]=='video']
    if len(references)!=1 or len(targets)!=1 or meta['layout']['reference_video_segment']!=references[0] or meta['layout']['target_video_segment']!=targets[0]:raise ValueError('actual reference/target row spans differ')
    if meta['layout']['signature'][1:4]!=[42,46,82] or meta['layout']['frame_rows']!=943:raise ValueError('actual patch/latent grid differs')
    if meta['num_heads']!=56 or meta['head_dim']!=128 or meta['source_dtype']!='torch.bfloat16':raise ValueError('native head/dtype geometry mismatch')
    if meta['tensor_axis_order']!=['batch','selected_head','latent_time','patch_row','patch_col','head_channel']:raise ValueError('captured axes do not identify exact head/grid order')
    for name in ('reference','target'):
        tensor=data[name]
        if list(tensor.shape)!=[1,4,42,23,41,128] or tensor.dtype!=torch.bfloat16:raise ValueError('must preserve actual BF16 capture with one batch axis')
        expected={k:meta['tensors'][name][k] for k in ('shape','dtype','sha256')}
        if tensor_info(tensor)!=expected:raise ValueError('captured tensor SHA mismatch')
    return data


def evaluate_checkpoint(data,tau,groups,output):
    ref,target=data['reference'][0],data['target'][0];step=data['metadata']['forward_index']
    group_sets={'all':set(TILES)}
    if groups['status']=='available':group_sets.update(high={tuple(v) for v in groups['high']},low={tuple(v) for v in groups['low']})
    records=[];fits=[]
    for hi,head in enumerate(HEADS):
        for y,x in TILES:
            r=ref[hi,:,y-1:y+2,x-1:x+2].double();v=target[hi,:,y-1:y+2,x-1:x+2].double()
            rc=torch.stack([r[t,dy+1,dx+1] for t in CALIB for dy,dx in NEIGHBORS]);yc=torch.stack([v[t,dy+1,dx+1] for t in CALIB for dy,dx in NEIGHBORS])
            fit,info=fit_map(rc,yc);fits.append({'head':head,'tile':[y,x],**info})
            for split,edges in SPLITS.items():
                for edge in edges:
                    row=({'edge':edge,'status':'unknown','reason':info['reason']} if fit is None else edge_record(r,v,tau,fit,edge))
                    row.update(head=head,tile=[y,x],split=split);records.append(row)
    with (output/f'step{step:03d}_edges.jsonl').open('x') as f:
        for r in records:f.write(json.dumps(r,allow_nan=False)+'\n')
    write_json(output/f'step{step:03d}_fits.json',fits)
    summaries={}
    for group,tiles in group_sets.items():
        summaries[group]={}
        for split,edges in SPLITS.items():
            heads={str(h):summarize([r for r in records if r['head']==h and r['split']==split and tuple(r['tile']) in tiles],len(tiles)*len(edges)) for h in HEADS}
            valid=all(h['status']=='valid' for h in heads.values())
            averaged={m:sum(h['methods'][m]['nmse'] for h in heads.values())/4 if valid else None for m in METHODS}
            directions=sum(h['status']=='valid' and h['methods']['M']['nmse']<min(h['methods'][m]['nmse'] for m in ('I','D','A')) for h in heads.values())
            best=min(averaged[m] for m in ('I','D','A')) if valid else None
            support=all(h['support_gate'] for h in heads.values())
            summaries[group][split]={'per_head':heads,'equal_head_nmse':averaged,'heads_with_M_better_than_best_baseline':directions,
                'best_equal_head_baseline_nmse':best,'equal_head_relative_gain':1-averaged['M']/best if best is not None and best>0 else None,
                'support_gate_all_four_heads':support,'candidate_gate':valid and support and best is not None and best>0 and averaged['M']<=.9*best and directions>=3,
                'gate_scope':'all four head support gates; >=10% equal-head gain; >=3 strictly positive individual-head gains'}
    result={'step_zero_based':step,'summaries':summaries,'source_groups_status':groups['status'],
            'high_change_val_post_gate':all(summaries['high'][s]['candidate_gate'] for s in ('val','post')) if 'high' in summaries else None,
            'event_used_for_selection':False,'calibration_state_indices':list(CALIB),'prediction_label_caveat':'Y is actual native output, possibly wrong motion; predicting it is not action correction'}
    write_json(output/f'step{step:03d}_summary.json',result);return result


def evaluate(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    c=load_json(args.condition);locator=load_json(args.locator);check_condition(c,locator);tau,_=bin_times(locator)
    groups=load_json(args.groups)
    validate_groups(groups,c['native_vae_calls'][1]['prepared_frames'])
    if groups['protocol_sha256']!=sha(HERE/'FROZEN_PROTOCOL.txt') or groups['condition_sha256']!=sha(args.condition) or groups['locator_sha256']!=sha(args.locator):raise ValueError('source-only grouping provenance differs')
    router=load_json(args.router)
    if router['mode']!='native' or router['run_id']!=c['run_id']:raise ValueError('native router/condition run mismatch')
    if router['backend']!='aten._scaled_dot_product_flash_attention.default' or router['routed_calls']!=0:
        raise ValueError('not an untouched explicit Flash native trajectory')
    noise=load_json(args.noise);runtime=load_json(args.runtime_provenance)
    if noise['schema']!='h3-event-noise-v1' or noise['run_id']!=router['run_id'] or noise['signature']['seed']!=2026101311:raise ValueError('actual noise run/seed mismatch')
    if noise['signature']['shapes']!=c['target_latent_shapes'] or len(noise['actual_noise_streams'])!=2:raise ValueError('actual noise stream shapes mismatch')
    if len(runtime['models'])!=4 or not runtime['core_matches'] or not all(runtime['core_matches'].values()):raise ValueError('actual runtime core/model provenance unavailable or mismatched')
    captures=router['native_feature_captures']
    if len(captures)!=3 or [r['metadata']['forward_index'] for r in captures]!=list(STEPS):raise ValueError('exact three ordered native captures required')
    protocol={'protocol_sha256':sha(HERE/'FROZEN_PROTOCOL.txt'),'implementation_sha256':sha(__file__),
              'groups_sha256':sha(args.groups),'condition_sha256':sha(args.condition),'router_sha256':sha(args.router),
              'locator_sha256':sha(args.locator),'noise_sha256':sha(args.noise),'runtime_provenance_sha256':sha(args.runtime_provenance),
              'actual_condition_run_id':c['run_id'],'actual_reference_latent':c['native_vae_calls'][1]['latent'],
              'actual_packed_layout':c['packed_layout'],'actual_noise_signature':noise['signature'],
              'actual_noise_streams':noise['actual_noise_streams'],'runtime_models':runtime['models'],
              'runtime_core_matches':runtime['core_matches'],'runtime_code':runtime['code'],
              'actual_input_video':c['input_video'],'actual_attention_backend':router['backend'],
              'router_status_at_read':router['status'],'router_completed_calls_at_read':router['completed_calls'],
              'actual_capture_records':captures,
              'position_bin_frames':[list(v) for v in bin_times(locator)[1]],
              'actual_video_sigmas':[router['sample_sigmas'][s] for s in STEPS],
              'audio_timestep_note':'Native feature capture records only video sampler sigma; audio coordinate must be read from separate actual pipeline/x0 audit, not inferred here.',
              'started_unix':time.time(),'torch':torch.__version__,'cpu_threads':torch.get_num_threads(),
              'gate_interpretation':'four heads equally weighted; every head must pass support; >=3 directions positive; no added rank>0 cutoff',
              'passivity_status':'not certified by this tool; root must independently verify same-host native replay'}
    write_json(out/'frozen_input_audit.json',protocol)
    results=[]
    for record in captures:
        step=record['metadata']['forward_index']
        if Path(record['path']).name!=f'block25_step{step:03d}.pt':raise ValueError('unexpected snapshot name')
        if record['metadata']['sampler_sigma_video']!=router['sample_sigmas'][step]:raise ValueError('captured video sigma differs from actual router call')
        path=Path(args.feature_dir)/Path(record['path']).name
        data=load_feature(path,record,c)
        if data['metadata']['run_id']!=router['run_id']:raise ValueError('capture run mismatch')
        results.append(evaluate_checkpoint(data,tau,groups,out));del data
    primary=results[0]['high_change_val_post_gate']
    result={'status':'exploratory_offline_prediction_only','call6_numerical_candidate_gate':primary,
            'overall_positive_research_claim':'not_allowed_without_independent_native_passivity_gate_and_correct_correspondence',
            'checkpoint_summaries':results,'finished_unix':time.time(),
            'interpretation':'Even a passing numerical gate only supports a predictable relation in this native trajectory; does not establish correct motion, causal correction, novelty, or generalization.'}
    write_json(out/'RESULTS.json',result);return result


def main():
    torch.set_num_threads(1)
    if torch.cuda.is_initialized():raise RuntimeError('CPU-only tool cannot start after CUDA initialization')
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    g=sub.add_parser('freeze-groups');g.add_argument('--condition',required=True);g.add_argument('--locator',required=True);g.add_argument('--audit-root',required=True);g.add_argument('--output',required=True)
    e=sub.add_parser('evaluate')
    for name in ('condition','locator','groups','router','feature-dir','noise','runtime-provenance','output'):e.add_argument('--'+name,required=True)
    args=p.parse_args()
    result=freeze_groups(args.condition,args.locator,args.audit_root,args.output) if args.command=='freeze-groups' else evaluate(args)
    print(json.dumps({'status':result['status'],'output':args.output},allow_nan=False))


if __name__=='__main__':main()
