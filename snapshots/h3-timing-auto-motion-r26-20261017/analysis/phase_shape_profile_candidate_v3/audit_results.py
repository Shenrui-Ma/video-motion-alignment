"""Bounded read-only result audit; writes new summary files only after verification."""
import fcntl
import json
import signal
import statistics
import time
from pathlib import Path
from run_once import HERE,LOCK,read,record,verify,write


def main():
    with LOCK.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:print('BUSY');return 75
        signal.signal(signal.SIGALRM,lambda *args:(_ for _ in ()).throw(TimeoutError('audit >120s')));signal.alarm(120)
        start=time.perf_counter();summary=read(HERE/'results/SUMMARY.json')
        used=[record(HERE/'results/SUMMARY.json'),*summary['files']]
        for freeze in ('PROTOCOL_FREEZE.json','CODE_FREEZE.json'):
            item=read(HERE/freeze);used.extend([record(HERE/freeze),*item['files'],*item.get('external_inputs',[])])
        for item in used:verify(item)
        previous=read(HERE.parent/'phase_shape_profile_candidate_v2/results/SUMMARY.json')
        old={row['case']['id']:row for row in previous['rows']}
        detail=[];same=True;timings={'v2':0.,'v3':0.};unknown={name:{} for name in timings}
        for row in summary['rows']:
            result=read(row['result']['path']);case=row['case'];baseline=old[case['id']]['methods']['v2']
            for field in ('K','selected','counts','assessment'):
                if row['methods']['v2'][field]!=baseline[field]:raise ValueError('Historical v2 changed: '+case['id']+field)
            entry={'id':case['id'],'expected':case['expected'],'methods':{}}
            for name,m in row['methods'].items():
                timings[name]+=m['seconds'];a=m['assessment'];r=result['methods'][name]['result']
                item={'K':m['K'],'direction_task':a['direction_task'],'selected':m['selected'],
                      'plateaus':a.get('plateaus'),'windows':a.get('selected_windows'),'original_point_task':a.get('original_point_task')}
                if name=='v3':
                    item['order_audit']={p:{k:v for k,v in part['selector_audit'].items() if k!='all_candidates'} for p,part in r['parts'].items()}
                entry['methods'][name]=item
                for part in m['counts'].values():
                    for key,n in part.items():unknown[name][key]=unknown[name].get(key,0)+n
            detail.append(entry)
        receipts=[read(p) for p in (HERE/'audit').glob('*.json')]
        durations=[x['seconds'] for x in receipts if x['status']=='pass' and x['phase']=='case']
        def score(name,rows):
            a=[r['methods'][name]['direction_task'] for r in rows if r['methods'][name]['direction_task']['required']]
            return {'n':len(a),'pass':sum(x['pass'] for x in a)}
        output={'all43_complete':len(detail)==43,'historical_v2_reproduced':same,
            'artifact_records_verified':len(summary['files']),'required':{n:score(n,detail) for n in timings},
            'original31_required':{n:score(n,detail[:31]) for n in timings},
            'local12_required':{n:score(n,detail[31:]) for n in timings},
            'analysis_seconds':timings,'phase_seconds':{'sum':sum(durations),'median':statistics.median(durations),'min':min(durations),'max':max(durations)},
            'attempts':{'busy':sum(x['status']=='busy' for x in receipts),'technical_failures':sum(x['status']=='failed' for x in receipts)},
            'interval_status_counts':unknown,'rows':detail,'real_targets_scored':0,'online_enabled':False}
        for item in used:verify(item)
        write(HERE/'RESULT_STATISTICS.json',output)
        write(HERE/'RESULT_AUDIT.json',{'status':'pass','seconds':time.perf_counter()-start,'used':used,'statistics':record(HERE/'RESULT_STATISTICS.json'),'script':record(Path(__file__))})
        print(json.dumps({k:output[k] for k in ('required','original31_required','local12_required','analysis_seconds','phase_seconds','attempts')},indent=2))
        signal.alarm(0)
        return 0
if __name__=='__main__':raise SystemExit(main())
