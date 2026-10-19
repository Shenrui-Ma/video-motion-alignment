"""Offline completed-archive intake. No service, CUDA, decode, or pose inference.

Run only after parent/independent review, under existing Mac then remote locks.
Binding is separate from code freeze, and must bind every expected endpoint.
"""
import argparse,hashlib,json,math,os,re,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
FEATURES=('arm_direction','left_arm_direction','right_arm_direction')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def at_pointer(value,pointer):
    for part in pointer:
        value=value[part]
    return value


def validate_binding(binding):
    if binding.get('authorized_for_actual_evaluation') is not True:
        raise ValueError('actual evaluation not authorized in reviewed binding')
    if binding['protocol_sha256']!=sha(HERE/'PROTOCOL.json'):
        raise ValueError('protocol changed')
    freeze=json.loads((HERE/'FREEZE.json').read_text())
    if binding['freeze_sha256']!=sha(HERE/'FREEZE.json'):raise ValueError('freeze mismatch')
    for rel,h in freeze['files'].items():
        if sha(HERE/rel)!=h:raise ValueError('frozen tool changed '+rel)
    if not binding.get('cases'):raise ValueError('no cases')
    hashes={};ids=[];groups={}
    # All terminal/archive gates are validated before reading any pose payload.
    for case in binding['cases']:
        if not re.fullmatch(r'[A-Za-z0-9_-]+',case['case_id']):raise ValueError('unsafe case ID')
        ids.append(case['case_id']);group=case['run_id']
        groups.setdefault(group,[]).append(case)
        for key in ('source_pose','target_pose'):
            item=case[key];hashes[item['path']]=item['sha256']
        if not case.get('gates') or not case.get('archive_evidence'):
            raise ValueError('terminal gate and complete archive evidence required')
        has_run_gate=False
        for item in case['gates']:
            if sha(item['path'])!=item['sha256']:raise ValueError('gate hash mismatch')
            gate=json.loads(Path(item['path']).read_text())
            if gate.get('passed') is not True:raise ValueError('terminal gate not passed')
            if gate.get('run_id')!=group:raise ValueError('gate run identity mismatch')
            has_run_gate |= item.get('kind')=='RUN_GATE'
            hashes[item['path']]=item['sha256']
        if not has_run_gate:raise ValueError('missing RUN_GATE')
        for item in case['archive_evidence']:
            if sha(item['path'])!=item['sha256']:raise ValueError('archive evidence hash mismatch')
            if not item.get('predicates'):raise ValueError('archive evidence needs explicit predicates')
            evidence=json.loads(Path(item['path']).read_text())
            for predicate in item['predicates']:
                if at_pointer(evidence,predicate['pointer'])!=predicate['equals']:
                    raise ValueError('archive evidence predicate failed')
            hashes[item['path']]=item['sha256']
        # Bind poses to existing producer/archive evidence, not just arbitrary
        # files with matching self-declared hashes. The reviewed binding names
        # the exact JSON pointer in an already hashed evidence document.
        if set(case.get('pose_evidence',{}))!={'source_pose','target_pose'}:
            raise ValueError('source and target archival pose evidence required')
        for key,item in case['pose_evidence'].items():
            if item['path'] not in hashes:raise ValueError('pose evidence outside bound archive')
            evidence=json.loads(Path(item['path']).read_text())
            if at_pointer(evidence,item['pointer'])!=case[key]['sha256']:
                raise ValueError('pose not linked to original archive')
    if len(ids)!=len(set(ids)):raise ValueError('duplicate case')
    expected=binding['expected_runs']
    if set(groups)!=set(expected):raise ValueError('run inventory mismatch')
    for run,cases in groups.items():
        actual=[c['endpoint'] for c in cases]
        if actual!=expected[run]:raise ValueError('ordered endpoint inventory mismatch')
        if any(c['family']=='R27' for c in cases):
            if any(c['family']!='R27' for c in cases) or actual!=list(range(20)):
                raise ValueError('R27 requires all twenty endpoints before reading target poses')
        elif any(c['family']!='R26' or c['endpoint']!='final' for c in cases):
            raise ValueError('unsupported family/endpoint')
    for path,h in hashes.items():
        if sha(path)!=h:raise ValueError('bound file changed '+path)
    return hashes


def windows():
    for length in (16,32):
        for start in sorted(set(range(0,141-length+1,4))|{141-length}):
            yield [start,start+length-1]


def rows_for_null(source,target,window,lag,null_lag,feature,np):
    conf_name={'arm_direction':'arm_conf','left_arm_direction':'left_arm_conf','right_arm_direction':'right_arm_conf'}[feature]
    frames=list(range(window[0],window[1]+1))
    if any(not 0<=t+offset<141 for t in frames for offset in (lag,null_lag)):
        return None
    slots=[]
    for t in frames:
        for b in range(source[feature].shape[1]):
            s,p,n=source[feature][t,b],target[feature][t+lag,b],target[feature][t+null_lag,b]
            finite=[bool(np.isfinite(v).all()) for v in (s,p,n)]
            for good,v in zip(finite,(s,p,n)):
                if good and abs(float(np.linalg.norm(v))-1)>1e-6:raise ValueError('non-unit direction')
            def distance(a,b):
                value=float(np.linalg.norm(a-b))
                if value>2+1e-12:raise ValueError('unit distance exceeds numeric tolerance')
                return min(2.,value)
            dp=distance(s,p) if finite[0] and finite[1] else None
            dn=distance(s,n) if finite[0] and finite[2] else None
            weight=None
            if all(finite):
                cs=[float(source[conf_name][t,b]),float(target[conf_name][t+lag,b]),float(target[conf_name][t+null_lag,b])]
                if not all(math.isfinite(c) and 0<=c<=1 for c in cs):raise ValueError('invalid raw confidence')
                weight=min(cs)
            slots.append({'frame':t,'proposal':dp,'null':dn,'weight':weight})
    return slots


def evaluate_case(case,m,scan,compare,np,bounds):
    source=case['source_pose']['path'];target=case['target_pose']['path']
    scan.valid_pose(source);scan.valid_pose(target)
    loaded={};errors={}
    for c in (.3,.5):
        try:loaded[c]=(m.load_pose(source,c),m.load_pose(target,c))
        except ValueError as e:
            if str(e)!='Insufficient reliable torso anchors for scale normalization':raise
            errors[str(c)]=str(e)
    rows=[]
    for window in windows():
        for feature in FEATURES:
            row={'window':window,'feature':feature,'confidence':{},'joint':{}}
            by_method={key:{} for key in ('uniform_coarse','uniform_tight','confidence_completion_coarse','confidence_completion_tight')}
            for c in (.3,.5):
                key=str(c)
                if key in errors:
                    row['confidence'][key]={'status':'UNKNOWN_INPUT','reason':errors[key]}
                    for name in by_method:by_method[name][key]={'candidate_lag':None,'candidate_flags':['unknown_input'],'comparisons':[]}
                    continue
                s,t=loaded[c];original=m.clean(m.local_diagnostic(s,t,window,24,feature))
                proposal=bounds.select_candidate(original['curve'])
                lag=proposal['candidate_lag']
                oldlag=original['reliable_lag_frames']
                oldcompare=m.clean(compare(s,t,window,oldlag,feature)) if oldlag is not None and abs(oldlag)>2 else None
                record={'original_diagnostic':original,'original_pairwise_gain':oldcompare,'proposal':proposal,'bounds':{}}
                for method in ('uniform','confidence_completion'):
                    for tight in (False,True):
                        name=method+('_tight' if tight else '_coarse');comparisons=[];flags=list(proposal['candidate_flags'])
                        if lag is not None:
                            for e in range(-2,3):
                                slots=rows_for_null(s,t,window,lag,e,feature,np)
                                if slots is None:
                                    flags.append('outside_real_video_domain')
                                    result={'certified':False,'reasons':['outside_real_video_domain']}
                                else:result=bounds.interval(slots,method,tight)
                                comparisons.append({'null_lag':e,'bound':result})
                        result={'candidate_lag':lag,'candidate_flags':sorted(set(flags)),'comparisons':comparisons}
                        record['bounds'][name]=result;by_method[name][key]=result
                row['confidence'][key]=record
            row['joint']={name:bounds.joint_decision(values) for name,values in by_method.items()}
            lags=[row['confidence'][str(c)].get('original_diagnostic',{}).get('reliable_lag_frames') for c in (.3,.5)]
            original_status='unknown'
            if all(v is not None for v in lags) and abs(lags[0]-lags[1])<=2:
                if all(abs(v)<=2 for v in lags):original_status='aligned'
                elif min(lags)>2 or max(lags)<-2:
                    gs=[row['confidence'][str(c)]['original_pairwise_gain'] for c in (.3,.5)]
                    if all(g['status']=='measured' and g['min_gain']>.5 for g in gs):
                        original_status='delayed_evidence' if min(lags)>2 else 'advanced_evidence'
            row['original_joint_status']=original_status
            rows.append(row)
    if len(rows)!=186:raise ValueError('expected all186 part/windows')
    return {'case_id':case['case_id'],'run_id':case['run_id'],'endpoint':case['endpoint'],
            'source_pose':case['source_pose'],'target_pose':case['target_pose'],'rows':rows,'input_unknown':errors}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--binding',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.resolve().parent!=HERE:raise ValueError('output must be a new direct child of owned pilot directory')
    # The exclusive global locks are acquired by the reviewed external launcher,
    # whose exact command must be recorded in the binding; do not acquire only
    # the remote lock here and bypass Mac->remote order.
    if os.environ.get('H3_ROBUST_PILOT_LOCKED')!='mac_then_remote':raise ValueError('reviewed two-lock launcher required')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CUDA must be hidden')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        if not os.environ.get(name,'').isdigit() or not 1<=int(os.environ[name])<=4:raise ValueError('explicit <=4 CPU threads required')
    binding=json.loads(args.binding.read_text());inputs=validate_binding(binding)
    if args.output.exists():raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    sys.path.insert(0,str(HERE/'frozen'))
    import numpy as np
    import timing_metrics as m
    import scan_current_pose as scan
    from pairwise_gain import compare
    import bounds
    started=time.time();results=[]
    for case in binding['cases']:
        result=evaluate_case(case,m,scan,compare,np,bounds)
        path=args.output/(case['case_id']+'.json')
        with path.open('x') as f:json.dump(m.clean(result),f,allow_nan=False)
        results.append({'case_id':case['case_id'],'file':str(path),'sha256':sha(path)})
    for path,h in inputs.items():
        if sha(path)!=h:raise ValueError('bound input changed during evaluation '+path)
    with (args.output/'COMPLETE.json').open('x') as f:
        json.dump({'complete':True,'binding_sha256':sha(args.binding),'protocol_sha256':sha(HERE/'PROTOCOL.json'),
                   'freeze_sha256':sha(HERE/'FREEZE.json'),'results':results,'elapsed_seconds':time.time()-started,
                   'scope':'offline conditional evidence; no policy trajectory or causal intervention'},f,indent=2)


if __name__=='__main__':main()
