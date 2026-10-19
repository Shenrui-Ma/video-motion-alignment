"""One bounded descriptive aggregation of the completed frozen 63-target run."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='4'
import collections
import fcntl
import hashlib
import json
from pathlib import Path
import signal
import statistics
import time
import numpy as np

HERE=Path(__file__).resolve().parents[1]
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def read(path):return json.loads(Path(path).read_text())
def record(path):
    path=Path(path);b=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
def verify(item):
    actual=record(item['path'])
    assert all(actual[k]==item[k] for k in actual),item['path']
def write(path,value):
    with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

with LOCK.open('a+') as lock:
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:print('BUSY');raise SystemExit(75)
    def timeout(*args):raise TimeoutError('120-second audit bound')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(120)
    started=time.perf_counter()
    summary=read(HERE/'results/SUMMARY.json')
    assert len(summary['rows'])==63
    for item in summary['files']:verify(item)
    for item in read(HERE/'FREEZE.json')['files']:verify(item)
    groups={};total=collections.Counter();families_checked=0
    aa,bb=np.indices((141,141));family=bb-aa+1>=8
    for row in summary['rows']:
        r=read(row['result']['path'])
        group=groups.setdefault(row['run_id'],{'endpoints':0,'nonzero_K_endpoints':0,'K':0,'selected_delay':0,'selected_advance':0,'first_rejection_counts':collections.Counter(),'joint_failure_bit_counts':collections.Counter(),'common_known_slots':0,'nominal_bone_slots':0,'known_slots_by_part':{'left_arm':[],'right_arm':[]},'selected':[],'endpoint_rows':[],'feature_missingness_endpoints':0})
        group['endpoints']+=1;group['K']+=r['K'];group['nonzero_K_endpoints']+=r['K']>0
        group['feature_missingness_endpoints']+=bool(r['feature_failures']['source'] or r['feature_failures']['target'])
        path=Path(row['result']['path']).parent/'EVIDENCE.npz'
        with np.load(path,allow_pickle=False) as evidence:
            for part,pdata in r['parts'].items():
                j=evidence[part+'__J'][family]
                assert np.isfinite(j).all() and (j>=0).all(),(row['id'],part)
                families_checked+=len(j)
                bits=evidence[part+'__failure_bits'][family]
                for bit,name in enumerate(('UNKNOWN_SUPPORT','UNKNOWN_ROTATION','UNKNOWN_RESIDUAL','UNKNOWN_IDENTIFIABILITY','NO_SUPPORTED_TIME_DEVIATION','UNKNOWN_MULTIPLE_PHASES','UNKNOWN_SEARCH_BOUNDARY','NONPOSITIVE_VALUE')):
                    group['joint_failure_bit_counts'][name]+=int(((bits>>bit)&1).sum())
                group['first_rejection_counts'].update(pdata['counts']);total.update(pdata['counts'])
                d=pdata['diagnostics'];known=d['common_known_slots'];nominal=d['nominal_slots']
                assert int(evidence[part+'__common_mask'].sum())==known
                group['common_known_slots']+=known;group['nominal_bone_slots']+=nominal
                group['known_slots_by_part'][part].append(known)
        group['endpoint_rows'].append({'id':row['id'],'endpoint_index':row['endpoint_index'],'K':row['K'],'parts':row['parts']})
        for s in r['selected']:
            group['selected_delay']+=s['lag']>0;group['selected_advance']+=s['lag']<0
            group['selected'].append({'target_id':row['id'],'endpoint_index':row['endpoint_index'],**s})
    receipts=[read(p) for p in (HERE/'audit').glob('target*.json')]
    passed=[r for r in receipts if r['status']=='pass'];times=[r['seconds'] for r in passed]
    assert len(passed)==63
    output={'scope':'All63 previously-seen developmental endpoints; descriptive counts, no independent semantic truth',
            'groups':groups,'first_rejection_counts_total':total,'joint_failure_bits_overlap':True,
            'correctness':{'legal_J_values_checked':families_checked,'all_legal_J_finite_nonnegative':True,'common_masks_match_saved_slot_counts':True,'verified_target_artifacts':len(summary['files'])},
            'timing':{'target_phase_sum_s':sum(times),'target_phase_median_s':statistics.median(times),'target_phase_min_s':min(times),'target_phase_max_s':max(times),'analysis_sum_s':sum(r['analysis_seconds'] for r in summary['rows']),'conversion_sum_s':sum(r['conversion_seconds'] for r in summary['rows']),'busy_target_attempts':sum(r['status']=='busy' for r in receipts),'failed_target_attempts':sum(r['status']=='failed' for r in receipts),'finalize_seconds':read(HERE/'audit/finalize_attempt003.json')['seconds']},
            'semantic_accuracy':None,'false_positive_rate':None,'online_control':False,'input_summary':record(HERE/'results/SUMMARY.json'),'aggregation_seconds':time.perf_counter()-started}
    write(HERE/'audit/RESULT_STATISTICS.json',output)
    write(HERE/'audit/TARGET_RESULT_FREEZE.json',{'files':summary['files'],'summary':record(HERE/'results/SUMMARY.json')})
    print(json.dumps({'groups':{k:{f:v[f] for f in ('endpoints','K','selected_delay','selected_advance','common_known_slots','nominal_bone_slots')} for k,v in groups.items()},'correctness':output['correctness'],'timing':output['timing'],'statistics':record(HERE/'audit/RESULT_STATISTICS.json')},indent=2))
