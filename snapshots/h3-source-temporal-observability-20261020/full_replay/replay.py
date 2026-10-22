"""One CPU replay of a fixed observed trajectory, without modifying frozen code."""
import copy, hashlib, json, sys, time, types
from pathlib import Path

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(config):
    started=time.monotonic()
    root=Path(config['producer_root'])
    package=types.ModuleType('H3AutomaticWindowRouter')
    package.__path__=[str(root/'extensions/H3AutomaticWindowRouter')]
    sys.modules['H3AutomaticWindowRouter']=package
    from H3AutomaticWindowRouter.geometry import Geometry
    from H3AutomaticWindowRouter.selector import Controller
    from H3AutomaticWindowRouter.automatic_window_policy import candidate
    for name in ['diagnose','check_centered_support']:
        spec=config['helper_sources'][name]
        assert hashlib.sha256(spec['source'].encode()).hexdigest()==spec['sha256']
        mod=types.ModuleType(name);mod.__file__=spec['original_path']
        sys.modules[name]=mod
        exec(compile(spec['source'],spec['original_path'],'exec'),mod.__dict__)
    d=sys.modules['diagnose'];support=sys.modules['check_centered_support']
    d.sanity()
    audit_path=Path(config['audit_file'])
    assert sha(audit_path)==config['audit_sha256']
    data=json.loads(audit_path.read_text())['counterfactual']
    assert len(data['measurements'])==len(data['steps'])==20
    case=json.loads((root/'configs/protocol.json').read_text())['cases'][0]
    geometry=Geometry.from_case(case)
    source=Path(config['source_pose']);source_sha=sha(source)
    assert source_sha==config['source_pose_sha256']
    source_features={str(c):d.directions(source,c) for c in [.3,.5]}
    original=Controller(geometry,arm='visible_only')
    actual=[];bindings=[]
    # Complete first pass: prove all original decisions before any filtering.
    for i,m in enumerate(data['measurements']):
        ref=m['observer']['full_remote_record']
        assert sha(ref['file'])==ref['sha256']
        observer=json.loads(Path(ref['file']).read_text())
        assert observer['source_pose_sha256']==source_sha
        measurement=dict(m,observer=observer)
        decision=original.select(i,measurement)
        recorded=data['steps'][i]['decision']
        assert all(recorded[k]==v for k,v in decision.items()),('original_decision_mismatch',i)
        actual.append(decision)
        bindings.append({'index':i,'observer_sha256':ref['sha256'],'observer_path':ref['file'],'full_window_rows':len(observer['windows']),'response_sha256':m['response_sha256']})
    actual_on=[i for i,x in enumerate(actual) if x['active']]
    assert actual_on==[1,3,4,10,14,17,18],actual_on
    filtered=Controller(geometry,arm='visible_only');rows=[];max_raw_error=0.
    for i,m in enumerate(data['measurements']):
        observer=json.loads(Path(bindings[i]['observer_path']).read_text())
        response_path=Path(m['response_file']);assert sha(response_path)==m['response_sha256']
        response=json.loads(response_path.read_text())
        pose=Path(response['pose']['file']);pose_sha=sha(pose)
        assert pose_sha==response['pose']['sha256']==observer['edited_pose_sha256']
        bindings[i]['pose_sha256']=pose_sha
        raw_candidates=[(j,candidate(row)) for j,row in enumerate(observer['windows']) if candidate(row) is not None]
        features={str(c):d.directions(pose,c) for c in [.3,.5]} if raw_candidates else {}
        changed=copy.deepcopy(observer);details=[]
        for j,proposal in raw_candidates:
            row=observer['windows'][j]
            arm={'left_arm_direction':'left','right_arm_direction':'right','arm_direction':'both'}[row['feature']]
            comparisons={c:support.compare(source_features[c],features[c],row['window'],arm,int(proposal['lags'][c]),float(c)) for c in ['0.3','0.5']}
            measured=all(x['status']=='measured' for x in comparisons.values())
            if measured:
                raw=min(x['min_raw_gain'] for x in comparisons.values())
                delta=abs(raw-proposal['min_gain']);max_raw_error=max(max_raw_error,delta)
                assert delta<1e-10,('raw_gain_mismatch',i,row['window'],row['feature'],raw,proposal['min_gain'])
                gain=min(x['min_centered_gain'] for x in comparisons.values())
            else:
                raw=None;gain=None
            accepted=measured and gain>.5
            if not accepted:
                # Existing policy's candidate function rejects unknown status;
                # every accepted row and every original ranking score stays exact.
                changed['windows'][j]['status']='unknown'
            details.append({'window':row['window'],'feature':row['feature'],'lags':proposal['lags'],'original_min_gain':proposal['min_gain'],'centered_min_gain':gain,'accepted':accepted,'status':'measured' if measured else 'unknown_support','centered_gains_by_null_lag':{c:[v.get('centered_gain') for v in comparisons[c]['null_comparisons']] for c in comparisons}})
        new=filtered.select(i,dict(m,observer=changed))
        fields=['active','selected','physical_intervals','latent_bins','reason']
        rows.append({'index':i,'original':{k:actual[i][k] for k in fields},'filtered':{k:new[k] for k in fields},'accepted_count':sum(x['accepted'] for x in details),'rejected_count':sum(not x['accepted'] for x in details),'candidates':details})
    filtered_on=[x['index'] for x in rows if x['filtered']['active']]
    return {'schema':'r133-r138-full20-fixed-trajectory-centered-support-v1','scope':'Post-hoc replay of already observed ordinary predictions only. No changed closed-loop trajectory was generated.','support_definition':'Per proposal-versus-each-null-lag comparison, source/proposal/null use identical visible entries and minimum confidence weights; five comparisons can have different supports. Unchanged parent helper.','null_lags':list(range(-2,3)),'confidence_thresholds':[.3,.5],'added_eligibility':'minimum demeaned relative gain across both thresholds and all five null comparisons strictly > 0.5','ranking_and_persistence':'Original raw absolute-gain ranking, connected-component grouping and persistence code unchanged; rejected candidates alone set status unknown.','original_all20_decisions_exact':True,'actual_ON_indices':actual_on,'filtered_ON_indices':filtered_on,'main_action_ON_retained':[i for i in [1,3,4] if i in filtered_on],'static_ON_removed':[i for i in [10,14,17,18] if i not in filtered_on],'new_ON_indices':[i for i in filtered_on if i not in actual_on],'accepted_candidates':sum(x['accepted_count'] for x in rows),'rejected_candidates':sum(x['rejected_count'] for x in rows),'max_recomputed_raw_gain_error':max_raw_error,'bindings':bindings,'source_pose_sha256':source_sha,'audit_sha256':config['audit_sha256'],'helper_sha256':{k:v['sha256'] for k,v in config['helper_sources'].items()},'frozen_code_sha256':{n:sha(root/'extensions/H3AutomaticWindowRouter'/n) for n in ['selector.py','automatic_window_policy.py','delayed_window_policy.py','geometry.py','dynamic_support.py']},'CPU_wall_seconds':time.monotonic()-started,'rows':rows,'GPU_started':False,'pose_extraction':False,'new_threshold_search':False,'all_null_shared_support_variant':'Not run; explicitly kept original helper per-comparison definition.'}

if __name__=='__main__':
    output=run(CONFIG)
    encoded=json.dumps(output,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    assert len(encoded.encode())<=200000,('result_too_large',len(encoded))
    print(encoded)
