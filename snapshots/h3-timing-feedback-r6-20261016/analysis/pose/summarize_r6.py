"""Summarize already archived frozen metrics; no image inference or tuning."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

RUNS = {'native':'r2_s05_native','full':'r2_s05_full_6to14','feedback':'r6_s05_feedback_retry1'}
R2=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default=str(Path(__file__).resolve().parent))
    args=p.parse_args();root=Path(args.root);runs={};pending=[];failures={}
    for label,run in RUNS.items():
        run_root=root if label=='feedback' else R2
        prov=run_root/'pilot'/f'{run}_provenance'
        manifest=prov/'archive_manifest.json'
        failure=run_root/'pilot'/f'{run}.failure.json'
        if failure.exists():failures[label]=json.loads(failure.read_text())
        if not manifest.exists():pending.append(run);continue
        m=json.loads(manifest.read_text());stem=Path(m['relative_video']).stem
        raw=run_root/'raw'/m['relative_video']
        assert hashlib.sha256(raw.read_bytes()).hexdigest()==m['video_sha256']
        thresholds={}
        for t in ('0.3','0.5'):
            data=json.loads((run_root/'pilot'/f'{stem}.threshold{t}.timing.json').read_text())
            rows=[x for x in data['diagnostics'] if x['feature']=='arm_direction']
            thresholds[t]={'primary':next(x for x in rows if x['window']==[50,65]),'all_original_windows':rows}
        runs[label]={'run_id':run,'raw':str(raw),'sha256':m['video_sha256'],
                     'producer_host':m['producer_host'],'producer_root':m['producer_root'],
                     'config_sha256':m['config_sha256'],'thresholds':thresholds}
    gates={}
    for t in ('0.3','0.5'):
        lag={label:d['thresholds'][t]['primary'].get('reliable_lag_frames') for label,d in runs.items()}
        g={'primary_lag':lag}
        if 'native' in lag and 'full' in lag:
            n,f=lag['native'],lag['full']
            g['archived_baseline_failure_and_repair_present']=(n is not None and f is not None and abs(n)>2 and abs(f)<=2 and abs(n)-abs(f)>=4)
        if 'native' in lag:
            for label in ('feedback',):
                if label in lag:
                    n,x=lag['native'],lag[label]
                    g[label+'_complete_direction_endpoint']=None if x is None else abs(x)<=2
                    g[label+'_partial_direction_endpoint']=None if n is None or x is None else abs(n)-abs(x)>=4
        gates[t]=g
    report={'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'scope':'R6 causal feedback against archived same-host .41 R2 native/full; fixed Full forward indices6..14 (zero-based). Feedback may activate indices6..19 based only on prior callback. Baselines are reused, not new samples; actual-input/noise pairing is required. No benchmark. Detector thresholds are sensitivity checks, not confidence intervals.',
            'pending':pending,'failures_retained':failures,'runs':runs,'threshold_specific_gates':gates,
            'common_support_and_quality':'Must be reviewed separately; individual-support phase success is not sufficient for architectural or edit-quality claims.',
            'unknown':'Retained as null; never treated as a failed static mechanism or zero lag.',
            'runtime_audit':'Actual feedback operator execution and input pairing are separate gates.'}
    compact=dict(updated_utc=report['updated_utc'],scope=report['scope'],pending=pending,
                 failures_retained=failures,threshold_specific_gates=gates,runs={})
    for label,entry in runs.items():
        thresholds={}
        for threshold,items in entry['thresholds'].items():
            rows=[]
            for item in items['all_original_windows']:
                rows.append({key:item.get(key) for key in ('window','reliable_lag_frames','status','flags')} |
                            {'same_frame_error':item['same_frame']['error'],
                             'same_frame_coverage':item['same_frame']['coverage'],
                             'best_shift_error':item.get('best',{}).get('error'),
                             'best_shift_coverage':item.get('best',{}).get('coverage')})
            thresholds[threshold]={'primary_lag_frames':items['primary']['reliable_lag_frames'],'windows':rows}
        compact['runs'][label]={'run_id':entry['run_id'],'sha256':entry['sha256'],
                                'thresholds':thresholds,
                                'quality_gate':'pending independent fixed-frame review; phase success is not quality success'}
        quality_path=(root if label=='feedback' else R2)/'pilot'/(entry['run_id']+'.quality_review.json')
        if quality_path.is_file():
            quality=json.loads(quality_path.read_text())
            assert quality['video_sha256']==entry['sha256']
            compact['runs'][label]['quality_gate']=quality['quality_gate']
    (root/'compact_summary.json').write_text(json.dumps(compact,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'pending':pending,'failures':list(failures),'gates':gates},ensure_ascii=False))


if __name__=='__main__':main()
