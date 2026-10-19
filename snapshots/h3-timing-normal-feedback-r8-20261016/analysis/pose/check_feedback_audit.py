"""Independent audit of the frozen causal state machine; no observer/model call."""
from pathlib import Path
import argparse
import json
import consumer_r8 as consumer

HERE=Path(__file__).resolve().parent
RUN='r8_s05_normal_feedback'


def expected_decision(observation, previous):
    if not observation['accepted']:
        return False, 'OFF_UNKNOWN'
    lag=observation['best']['lag_frames']
    if type(lag) is not int or not -24<=lag<=24:
        raise ValueError('Out-of-protocol accepted lag')
    if lag>=4:return True,'ON_DELAYED'
    if -2<=lag<=2:return False,'OFF_ALIGNED'
    if lag==3:return previous,'HOLD_LAG3'
    return False,'OFF_ADVANCED'


def audit(trace):
    f=trace['feedback'];obs=f['observations'];active=f['active_indices'];latched=f['latched_forwards']
    checks={'completed':trace['status']=='complete','policy':f['policy']=='feedback' and f['fixed_indices']==[],
            'full_actuator':trace['mode']=='mass_preserve' and trace['alpha']==1 and trace['radius']==0 and trace['time_offset']==0,
            'fixed_window':trace['pixel_interval_inclusive']==[50,65],
            'all_blocks':trace['block_interval_half_open']==[0,50],
            '20_forwards':trace['completed_forward_calls']==20 and trace['calls_by_forward']==[50]*20,
            '1000_attention_calls':trace['completed_calls']==1000,
            '20_callbacks':f['callback_count']==20,
            'unique_active_indices':active==sorted(set(active)) and all(6<=i<=19 for i in active),
            'reported_active_count':f['active_forward_count']==len(active),
            'all50_or_none_routes':trace['routed_by_forward']==[50 if i in active else 0 for i in range(20)],
            'total_routes':trace['routed_calls']==50*len(active),
            'routes_per_block':trace['routed_by_block']==[len(active)]*50,
            'callbacks5_through19_only':[o['callback_index'] for o in obs]==list(range(5,20)),
            'latched20_forward_indices':[r['forward_index'] for r in latched]==list(range(20)),
            'active_matches_latched':[r['forward_index'] for r in latched if r['active']]==active,
            'native_prefix':all(not r['active'] for r in latched[:6])}
    rows=[];previous=False
    for row in obs:
        index=row['callback_index'];terminal=index==19
        decision,reason=expected_decision(row['observation'],previous)
        ok=(row['observer_proposed_active']==decision and row['reason']==reason and
            row['terminal_audit_only']==terminal and row['current_forward_active']==(index in active))
        if terminal:
            ok=ok and row['next_forward_index'] is None and row['next_active'] is None
        else:
            ok=ok and row['next_forward_index']==index+1 and row['next_active']==decision
            ok=ok and latched[index+1]['decision_callback_index']==index and latched[index+1]['active']==decision
            previous=decision
        rows.append({'callback_index':index,'checks_passed':bool(ok),'accepted':row['observation']['accepted'],
                     'best_lag':None if row['observation'].get('best') is None else row['observation']['best']['lag_frames'],'reason':reason,
                     'next_active':row['next_active'],'readout_seconds':row['readout_seconds']})
    checks['decisions_use_only_previous_callback']=all(r['checks_passed'] for r in rows)
    return {'checks':checks,'passed':all(checks.values()),'active_forward_indices_zero_based':active,
            'active_forward_count':len(active),'observations':rows,
            'observer_seconds_total':f['observer_seconds_total'],
            'active_sigma_intervals':f['active_sigma_intervals'],'sigma_dose':f['sigma_dose'],
            'scope':'Execution/state-machine audit, not independent evidence of alignment. OFF_UNKNOWN/OFF_ADVANCED are not successful alignment. NFE stays20; route count alone is not wall-time efficiency.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');args=p.parse_args()
    if args.self_test:
        for lag,prev,wanted in [(4,False,(True,'ON_DELAYED')),(0,True,(False,'OFF_ALIGNED')),
                                (3,False,(False,'HOLD_LAG3')),(3,True,(True,'HOLD_LAG3')),
                                (-3,True,(False,'OFF_ADVANCED'))]:
            assert expected_decision({'accepted':True,'best':{'lag_frames':lag}},prev)==wanted
        assert expected_decision({'accepted':False},True)==(False,'OFF_UNKNOWN')
        print(json.dumps({'passed':True,'decision_boundary_tests':6,'no_network_or_gpu':True}));return
    path=HERE/'pilot'/(RUN+'_provenance')/'router_audit.json'
    result=audit(json.loads(path.read_text()));result['audit_sha256']=consumer.digest(path)
    consumer.save(HERE/'operator_execution_gate.json',result)
    print(json.dumps({'passed':result['passed'],'active_indices':result['active_forward_indices_zero_based']}))


if __name__=='__main__':main()
