"""Bounded, JSON-only final-pose candidate replay; no model/pose/lag inference."""
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time
import signed_policy as s

ROOT=Path(__file__).resolve().parents[1]
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def process(case):
    for key in ('source_pose','target_pose','final_scan','summary','cpu_complete','derived_files'):
        rec=case[key]
        if Path(rec['path']).stat().st_size!=rec['bytes'] or sha(rec['path'])!=rec['sha256']:
            raise ValueError('frozen input changed: '+key)
    for rec in case['postrun_numeric_code'].values():
        if sha(rec['path'])!=rec['sha256']:raise ValueError('postrun numerical source changed')
    scan=read(case['final_scan']['path']);summary=read(case['summary']['path'])
    if scan['source_pose_sha256']!=case['source_pose']['sha256'] or scan['edited_pose_sha256']!=case['target_pose']['sha256']:
        raise ValueError('scan not bound to actual pose pair')
    if summary['run_id']!=case['run_id'] or summary['source_id']!=case['source_id'] or summary['passed'] is not True:
        raise ValueError('summary case mismatch')
    if read(case['cpu_complete']['path'])['passed'] is not True:raise ValueError('parent CPU completion missing')
    batch=Path(case['derived_files']['path']).parent
    if read(case['derived_files']['path'])[str(Path(case['final_scan']['path']).relative_to(batch))]!=case['final_scan']['sha256']:
        raise ValueError('scan differs from archived derived manifest')
    rows=scan['windows']
    if scan['status']!='measured' or len(rows)!=186 or scan['thresholds']!=[.3,.5]:raise ValueError('fixed whole-scan schema differs')
    output=[]
    for i,row in enumerate(rows):
        old=s.old.candidate(row);new=s.candidate(row)
        output.append({'row_index':i,'window':row['window'],'feature':row['feature'],'baseline':row['baseline'],
                       'status':row['status'],'min_gain':row.get('min_gain'),
                       'old_candidate':old,'signed_candidate':new,
                       'confidence_diagnostics':{c:{k:d.get(k) for k in ('status','flags','reliable_lag_frames')} for c,d in row['measurements'].items()},
                       'common_support_comparisons':row.get('comparison')})
    old_groups=s.old.components(rows);signed_groups=s.components(rows)
    old_reset=s.old.Policy().update(0,rows);signed_reset=s.Policy().update(0,rows)
    if old_reset['active'] or signed_reset['active']:raise ValueError('single final cannot manufacture persistence')
    counts={'all_rows':len(rows),'old_eligible_rows':sum(x['old_candidate'] is not None for x in output),
            'signed_eligible_rows':sum(x['signed_candidate'] is not None for x in output),
            'signed_delayed_rows':sum(x['signed_candidate'] is not None and x['signed_candidate']['direction']=='delayed' for x in output),
            'signed_advanced_rows':sum(x['signed_candidate'] is not None and x['signed_candidate']['direction']=='advanced' for x in output),
            'old_components':len(old_groups),'signed_components':len(signed_groups)}
    return {'source_id':case['source_id'],'run_id':case['run_id'],'role':case['role'],'input':case,
            'counts':counts,'baseline_counts':summary['scan_summary']['baseline_counts'],
            'old_groups':old_groups,'signed_groups':signed_groups,'every_row':output,
            'reset_single_observation_sanity':{'artificial_index':0,'old_active':old_reset['active'],'signed_active':signed_reset['active'],
              'scope':'Only confirms initial state has no persistence; not an actual denoising decision.'},
            'online_active_indices':None,'final_controlled_effect':None,
            'full_curves_and_support':case['final_scan']}

def main():
    with LOCK.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:print('CPU_LOCK_BUSY');return 75
        start=time.monotonic();freeze=read(ROOT/'audit/PRE_REPLAY_FREEZE.json')
        for rel,digest in freeze['files'].items():
            if sha(ROOT/rel)!=digest:raise ValueError('replay payload changed: '+rel)
        protocol=read(ROOT/'design/PROTOCOL.json');results=[]
        for case in protocol['cases']:
            result=process(case);save(ROOT/'results'/(case['source_id']+'.json'),result)
            results.append({'source_id':case['source_id'],'counts':result['counts'],
                            'old_representatives':[g['representative'] for g in result['old_groups']],
                            'signed_representatives':[g['representative'] for g in result['signed_groups']]})
        total={'status':'OFFLINE_CANDIDATE_REPLAY_COMPLETE','protocol_sha256':sha(ROOT/'design/PROTOCOL.json'),
               'payload_freeze_sha256':sha(ROOT/'audit/PRE_REPLAY_FREEZE.json'),'cases':results,
               'seconds':time.monotonic()-start,'new_model_or_pose_or_lag_calls':0,
               'persistence_actual_evidence':False,'online_generation_comparison':False,
               'files':{p.name:sha(p) for p in sorted((ROOT/'results').glob('*.json'))}}
        save(ROOT/'results/SUMMARY.json',total)
        print(json.dumps({'status':total['status'],'seconds':total['seconds'],'cases':[{'source_id':x['source_id'],**x['counts']} for x in results]}))
        return 0

if __name__=='__main__':sys.exit(main())
