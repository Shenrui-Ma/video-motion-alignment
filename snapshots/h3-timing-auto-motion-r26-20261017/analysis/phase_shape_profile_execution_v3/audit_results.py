"""One locked read-only postrun summary; no model or feature computation."""
import fcntl
import json
import signal
import statistics
import time
from pathlib import Path
from collections import Counter
import run_once as r


def main():
    with r.LOCK.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:print('BUSY');return 75
        signal.signal(signal.SIGALRM,lambda *args:(_ for _ in ()).throw(TimeoutError('audit >120s')));signal.alarm(120)
        start=time.perf_counter();summary=r.read(r.HERE/'results/SUMMARY.json')
        used=[r.record(r.HERE/'results/SUMMARY.json'),*summary['files']]
        for item in used:r.verify(item)
        if len(summary['rows'])!=63 or len(summary['files'])!=189:raise ValueError('Incomplete63/189')
        groups={};differences=[];totals={name:Counter() for name in ('v1','v2','v3')}
        def signature(row):
            return row['part'],row['start'],row['end'],tuple(row['phase_set'])
        for row in summary['rows']:
            group=groups.setdefault(row['run_id'],{'rows':0,'methods':{name:{'K_positive':0,'selected':0,'delay':0,'advance':0,'common_known_slots':0,'nominal_slots':0,'analysis_seconds':0.,'counts':{},'windows':[]} for name in totals}})
            group['rows']+=1
            for name,m in row['methods'].items():
                out=group['methods'][name];out['K_positive']+=m['K']>0;out['selected']+=m['K']
                out['common_known_slots']+=m['common_known_slots'];out['nominal_slots']+=m['nominal_slots'];out['analysis_seconds']+=m['analysis_seconds']
                for part in m['parts'].values():
                    for key,count in part['counts'].items():out['counts'][key]=out['counts'].get(key,0)+count
                for w in m['selected']:
                    direction='delay' if min(w['phase_set'])>2 else 'advance' if max(w['phase_set'])< -2 else 'unknown'
                    out[direction]=out.get(direction,0)+1
                    out['windows'].append({'id':row['id'],'endpoint_index':row['endpoint_index'],**w})
                totals[name].update({'endpoints':1,'K_positive':int(m['K']>0),'selected':m['K'],'common_known_slots':m['common_known_slots'],'nominal_slots':m['nominal_slots'],'analysis_seconds':m['analysis_seconds']})
            v2=row['methods']['v2'];v3=row['methods']['v3']
            if any(v2['parts'][p]['counts']!=v3['parts'][p]['counts'] for p in v2['parts']):raise ValueError('Candidate counts changed')
            a=set(map(signature,v2['selected']));b=set(map(signature,v3['selected']))
            if a!=b:differences.append({'id':row['id'],'v2_only':sorted(a-b),'v3_only':sorted(b-a),'v2_K':v2['K'],'v3_K':v3['K']})
        receipts=[r.read(p) for p in (r.HERE/'audit').glob('*.json') if p.name.startswith('target')]
        seconds=[x['seconds'] for x in receipts if x.get('status')=='pass']
        output={'status':'complete','groups':groups,'totals':{n:dict(c) for n,c in totals.items()},'v2_v3_changed_endpoints':differences,
                'target_attempts':{'pass':sum(x.get('status')=='pass' for x in receipts),'busy':sum(x.get('status')=='busy' for x in receipts),'failed':sum(x.get('status')=='failed' for x in receipts)},
                'target_phase_seconds':{'sum':sum(seconds),'median':statistics.median(seconds),'min':min(seconds),'max':max(seconds)},
                'development_set':True,'accuracy':None,'false_positive_rate':None,'online_enabled':False,'safety_counterexample_unresolved':True}
        for item in used:r.verify(item)
        r.write(r.HERE/'RESULT_STATISTICS.json',output)
        r.write(r.HERE/'RESULT_AUDIT.json',{'status':'pass','seconds':time.perf_counter()-start,'files_verified':189,'used':used,'script':r.record(Path(__file__)),'statistics':r.record(r.HERE/'RESULT_STATISTICS.json')})
        print(json.dumps({k:output[k] for k in ('totals','target_attempts','target_phase_seconds')},indent=2));signal.alarm(0)
        return 0
if __name__=='__main__':raise SystemExit(main())
