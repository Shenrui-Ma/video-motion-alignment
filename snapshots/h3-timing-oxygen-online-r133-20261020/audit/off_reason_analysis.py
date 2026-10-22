"""Read-only post-hoc attribution of the frozen R133 controller's decisions.

No model, policy, thresholds, remote files, or running process is changed.
Row-level diagnostic counts are evidence, not causal claims about final motion.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r'''
import hashlib,json,time
from pathlib import Path
r=Path('/data4/researcher/h3_runs/timing_oxygen_online_r133_20261020')
p=r/'audit/counterfactual/r133_short_0252_seed2026101703_visible_only.json'
b=p.read_bytes();v=json.loads(b);c=v['counterfactual']
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def compact_row(w):
    out={k:w[k] for k in ('window','feature','baseline','status','min_gain') if k in w}
    out['measurements']={}
    for confidence,m in w.get('measurements',{}).items():
        z={k:m[k] for k in ('status','flags','reliable_lag_frames','relative_error_reduction_after_local_shift','distinct_lag_relative_gap') if k in m}
        for k in ('same_frame','best','unqualified_best'):
            x=m.get(k)
            if x is not None:z[k]={a:x[a] for a in ('lag_frames','error','coverage','valid_frame_count') if a in x}
        out['measurements'][confidence]=z
    out['comparison']={}
    for confidence,m in w.get('comparison',{}).items():
        out['comparison'][confidence]={k:m[k] for k in ('status','min_gain','proposal_lag','null_comparisons') if k in m}
    return out
completed={s['physical_index']:s for s in c['steps']}
rows=[]
for m in c['measurements']:
    i=m['physical_index']
    if i not in completed:continue
    o=m['observer'];d=dict(completed[i]['decision'])
    rows.append({'index':i,'decision':d,'request_file':m['request_file'],'request_sha256':m['request_sha256'],
      'response_file':m['response_file'],'response_sha256':m['response_sha256'],
      'observer_status':o['status'],'observer_reasons':o.get('reasons',[]),
      'rows':[compact_row(w) for w in o['windows']]})
sources=['extensions/H3AutomaticWindowRouter/automatic_window_policy.py','extensions/H3AutomaticWindowRouter/delayed_window_policy.py','scripts/timing_metrics.py','scripts/scan_current_pose.py','scripts/pairwise_gain.py']
print(json.dumps({'schema':'r133-off-reason-compact-evidence-v1','observed_unix':time.time(),
 'run_id':v['run_id'],'runtime_status':v['status'],'counterfactual_path':str(p),'counterfactual_sha256':hashlib.sha256(b).hexdigest(),
 'completed_steps':len(completed),'ON':c['full_physical_indices'],'policy_file_sha256':{s:h(r/s) for s in sources},'steps':rows},allow_nan=False))
'''

PARTS = {'left_arm_direction': {'left'}, 'right_arm_direction': {'right'},
         'arm_direction': {'left', 'right'}}


def continuity(current, previous):
    a, b = current['window'], previous['window']
    overlap = max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)
    ratio = overlap / min(a[1] - a[0] + 1, b[1] - b[0] + 1)
    failures = []
    if not PARTS[current['feature']] & PARTS[previous['feature']]:
        failures.append('observed_body_part_switch')
    if current['direction'] != previous['direction']:
        failures.append('lag_direction_switch')
    if ratio < .5:
        failures.append('temporal_window_overlap_below_half')
    return {'previous_window': b, 'previous_feature': previous['feature'],
            'previous_direction': previous['direction'], 'overlap_fraction': ratio,
            'failed_conditions': failures, 'persistent': not failures}


def row_reason(row):
    causes = set()
    baseline = row['baseline']
    ms = list(row['measurements'].values())
    if baseline == 'aligned':
        causes.add('both_confidence_lags_within_two_frames')
    if baseline == 'unknown':
        for m in ms:
            if m['status'] == 'unreliable_detection_coverage':
                causes.add('insufficient_visible_pose_coverage')
            for flag in m.get('flags', []):
                causes.add(flag)
        lags = [m['reliable_lag_frames'] for m in ms]
        if len(lags) == 2 and all(x is not None for x in lags):
            if abs(lags[0] - lags[1]) > 2:
                causes.add('two_confidence_lags_disagree')
            else:
                causes.add('two_confidence_lags_straddle_alignment_threshold')
    if baseline in ('delayed_candidate', 'advanced_candidate'):
        if row['status'] == 'measured':
            if row['min_gain'] <= .5:
                causes.add('gain_at_or_below_half')
            else:
                costs = [n['null_cost'] - n['proposal_cost']
                         for c in row['comparison'].values()
                         for n in c['null_comparisons']]
                causes.add('eligible_error_candidate' if costs and min(costs) > 0
                           else 'nonpositive_absolute_gain')
        else:
            for c in row['comparison'].values():
                for n in c['null_comparisons']:
                    if n['status'] != 'valid':
                        causes.add('pairwise_' + n['status'])
    return sorted(causes)


def analyze(evidence):
    records = []
    previous_reps, previous_members = [], []
    primary = Counter()
    for s in evidence['steps']:
        d = s['decision']
        reps = [g['representative'] for g in d['groups']]
        matrices = [{'current': r, 'previous_representatives':
                     [continuity(r, p) for p in previous_reps],
                     'persistent_candidate_in_previous_group':
                     any(continuity(r, p)['persistent'] for p in previous_members)}
                    for r in reps]
        member_continuity = []
        for group in d['groups']:
            matching = [m for m in group['members']
                        if m != group['representative'] and
                        any(continuity(m, p)['persistent'] for p in previous_reps)]
            member_continuity.append({'span':group['span'],
                'nonrepresentative_persistent_count':len(matching),
                'persistent_nonrepresentative_members':matching})
        calculated = [r for r, matrix in zip(reps, matrices)
                      if any(x['persistent'] for x in matrix['previous_representatives'])]
        if calculated != d['selected']:
            raise ValueError('Frozen representative persistence differs from actual decision')
        counts = Counter(reason for row in s['rows'] for reason in row_reason(row))
        baseline = Counter(row['baseline'] for row in s['rows'])
        if d['active']:
            cause = 'ON_persistent_signed_error'
        elif reps:
            if not previous_reps:
                cause = 'initial_persistence_wait' if s['index'] == 0 else 'previous_step_has_no_candidate'
            else:
                failures = [set(x['failed_conditions']) for m in matrices
                            for x in m['previous_representatives']]
                common = set.intersection(*failures)
                cause = next(iter(common)) if len(common) == 1 else 'mixed_persistence_conditions_failed'
        elif d.get('all_unknown'):
            cause = 'all_rows_unobservable_or_ambiguous'
        elif baseline.get('aligned', 0) == len(s['rows']):
            cause = 'all_rows_within_two_frame_tolerance'
        else:
            cause = 'no_qualifying_candidate_mixed_row_evidence'
        if not d['active']:
            primary[cause] += 1
        records.append({'index':s['index'],'active':d['active'],'runtime_reason':d['reason'],
            'offline_primary_reason':cause,'selected':d['selected'],'representatives':reps,
            'reliable_rows':d['reliable_rows'],'total_rows':d['total_rows'],
            'baseline_counts':dict(baseline),'nonexclusive_row_reason_counts':dict(counts),
            'persistence_evidence':matrices,
            'current_nonrepresentative_continuity':member_continuity,
            'request_sha256':s['request_sha256'],'response_sha256':s['response_sha256']})
        previous_reps = reps
        previous_members = [m for g in d['groups'] for m in g['members']]
    return {'schema':'r133-off-reason-summary-v1','run_id':evidence['run_id'],
        'completed_steps':evidence['completed_steps'],'ON':evidence['ON'],
        'OFF_primary_reason_counts':dict(primary),'steps':records,
        'interpretation':'OFF reasons describe observed controller conditions. A persistence failure does not establish motion improvement. Row reasons overlap and are not separate sampling steps. Final motion requires completed video review.',
        'runtime_code_changed':False,'policy_file_sha256':evidence['policy_file_sha256']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input',type=Path)
    a = ap.parse_args()
    if a.input:
        evidence=json.loads(a.input.read_text())
    else:
        p=subprocess.run(['ssh','-o','ConnectTimeout=15','H3_SERVER_B','python3 -'],
            input=REMOTE,text=True,capture_output=True,timeout=90,check=True)
        evidence=json.loads(p.stdout)
    out=ROOT/'audit/actual_formal/off_reasons';out.mkdir(parents=True,exist_ok=True)
    prefix=f'step{evidence["completed_steps"]:02d}'
    raw=out/(prefix+'_COMPACT_EVIDENCE.json')
    raw.write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    result=analyze(evidence)
    result['compact_evidence_sha256']=hashlib.sha256(raw.read_bytes()).hexdigest()
    target=out/(prefix+'_OFF_REASON_SUMMARY.json')
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'completed_steps':result['completed_steps'],'ON':result['ON'],
        'OFF_primary_reason_counts':result['OFF_primary_reason_counts']}))


if __name__=='__main__':main()
