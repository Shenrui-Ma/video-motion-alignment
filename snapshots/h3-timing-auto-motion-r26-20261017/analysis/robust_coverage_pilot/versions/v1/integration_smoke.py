"""Synthetic JSON through frozen real NumPy pose loader; no real inputs/model.

Called only after review, under Mac->remote CPU locks. Writes one JSON report.
"""
import argparse,hashlib,json,math,os,sys,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'frozen'))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def synthetic_pose(delay=0,missing=False):
    frames=[]
    for t in range(141):
        phase=t-delay
        xy=[[550.,150.] for _ in range(17)]
        xy[5]=[500.,220.];xy[6]=[600.,220.];xy[11]=[510.,450.];xy[12]=[590.,450.]
        for shoulder,elbow,wrist,offset in ((5,7,9,0.),(6,8,10,.7)):
            a=.009*phase*phase+.3*math.sin(.173*phase)+offset
            b=.006*phase*phase+.3*math.cos(.117*phase)+offset
            xy[elbow]=[xy[shoulder][0]+80*math.cos(a),xy[shoulder][1]+80*math.sin(a)]
            xy[wrist]=[xy[elbow][0]+65*math.cos(b),xy[elbow][1]+65*math.sin(b)]
        score=[.9]*17
        if missing and 58<=t<=64:score[9]=.4
        frames.append({'frame':t,'time_s':t/24,'selected_person':0,
                       'persons':[{'coco17_xy':xy,'coco17_score':score}]})
    return {'video':{'fps':24,'width':1312,'height':736,'container_frame_count':141},'frames':frames}

def run():
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CUDA must remain hidden')
    freeze=json.loads((HERE/'FREEZE.json').read_text())
    for rel,h in freeze['files'].items():
        if sha(HERE/rel)!=h:raise ValueError('frozen payload mismatch '+rel)
    import numpy as np
    import timing_metrics as m
    import scan_current_pose as scan
    from pairwise_gain import compare
    import bounds,evaluate
    started=time.time();checks={};readouts=[]
    with tempfile.TemporaryDirectory(prefix='synthetic_pose_') as td:
        root=Path(td);src=root/'source.json';tgt=root/'target.json';miss=root/'missing.json'
        src.write_text(json.dumps(synthetic_pose()));tgt.write_text(json.dumps(synthetic_pose(4)));miss.write_text(json.dumps(synthetic_pose(4,True)))
        for p in (src,tgt,miss):scan.valid_pose(p)
        for c in (.3,.5):
            source=m.load_pose(src,c);target=m.load_pose(tgt,c)
            for feature in evaluate.FEATURES:
                original=m.clean(m.local_diagnostic(source,target,[50,65],24,feature))
                proposal=bounds.select_candidate(original['curve'])
                if proposal['candidate_lag']!=4 or proposal['candidate_flags']:raise AssertionError('knownshift proposal')
                old=compare(source,target,[50,65],4,feature)
                comparisons=[]
                for e in range(-2,3):
                    slots=evaluate.rows_for_null(source,target,[50,65],4,e,feature,np)
                    result=bounds.interval(slots,'confidence_completion',True)
                    oldrow=next(x for x in old['null_comparisons'] if x['null_lag']==e)
                    if abs(result['proposal_cost_upper']-oldrow['proposal_cost'])>1e-12:raise AssertionError('complete proposal metric mismatch')
                    if abs(result['null_cost_lower']-oldrow['null_cost'])>1e-12:raise AssertionError('complete null metric mismatch')
                    if not result['certified']:raise AssertionError('complete knownshift not certified')
                    comparisons.append(result)
                readouts.append({'confidence':c,'feature':feature,'lag':4,'all5_certified':True})
            missing=m.load_pose(miss,c)
            slots=evaluate.rows_for_null(source,missing,[50,65],4,0,'left_arm_direction',np)
            coarse=bounds.interval(slots,'confidence_completion',False);tight=bounds.interval(slots,'confidence_completion',True)
            if tight['advantage_unnormalized_lower']+1e-12<coarse['advantage_unnormalized_lower']:raise AssertionError('tight advantage weakened')
            if tight['proposal_cost_upper']>coarse['proposal_cost_upper']+1e-12:raise AssertionError('tight residual weakened')
            readouts.append({'confidence':c,'synthetic_missing_common_slots':tight['common_slots'],'expected_slots':32,
                             'tight_certified':tight['certified'],'coarse_certified':coarse['certified']})
        # Small full186-window integration via the unchanged evaluator. Inputs
        # remain synthetic; this tests serialization and both-threshold routing.
        case={'case_id':'synthetic_shift4','run_id':'synthetic','endpoint':'final',
              'source_pose':{'path':str(src),'sha256':sha(src)},'target_pose':{'path':str(tgt),'sha256':sha(tgt)}}
        full=evaluate.evaluate_case(case,m,scan,compare,np,bounds)
        if len(full['rows'])!=186:raise AssertionError('missing windows')
        json.dumps(m.clean(full),allow_nan=False)
        checks={'actual_numpy_loader':True,'fixed_geometry_time_validation':True,
                'known_plus4_three_parts_two_conf':True,'complete_confidence_metric_equal_old':True,
                'partial_threshold_mask_and_tightening':True,'full186_synthetic_evaluator_and_json':True,
                'torch_not_imported':'torch' not in sys.modules,'actual_target_inputs_read':False}
    return {'passed':all(v for k,v in checks.items() if k!='actual_target_inputs_read'),'checks':checks,
            'readouts':readouts,'elapsed_seconds':time.time()-started,'numpy_version':np.__version__,
            'freeze_sha256':sha(HERE/'FREEZE.json'),'script_sha256':sha(__file__),'thread_env':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=run()
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)
