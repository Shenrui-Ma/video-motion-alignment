"""Independent final-only CPU phases; never writes the formal postrun archive."""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
POST = ROOT / 'analysis/postrun'
sys.path.insert(0, str(POST))
from contract import read, save, sha, require, output_file, observer_summary
import remote_consume as formal
import evaluate as frozen

def inputs():
    spec = read(HERE/'PROTOCOL.json')
    require(str(ROOT) == spec['remote_root'], 'remote root mismatch')
    require(sha(POST/'PROTOCOL.json') == spec['formal_protocol_sha256'], 'formal protocol changed')
    require(sha(POST/'FREEZE.json') == spec['formal_freeze_sha256'], 'formal freeze changed')
    formal.verify_consumer_seal()
    arc=POST/'captured'/spec['run_id']; gate=read(arc/'RUN_GATE.json')
    require(sha(arc/'RUN_GATE.json')==spec['run_gate_sha256'] and gate['passed'] is True, 'run gate changed')
    require(sha(arc/'FILE_INVENTORY.json')==spec['inventory_sha256']==gate['file_inventory_sha256'], 'inventory changed')
    inv=read(arc/'FILE_INVENTORY.json'); histpath=arc/'logs'/f"{spec['run_id']}_history.json"
    hist=read(histpath); require(hist['status']['completed'] is True and hist['status']['status_str']=='success','not success')
    video=output_file(arc,hist,spec['run_id']); source=arc/'configs/source.pose.json'
    for p in [histpath,video,source,arc/'DECISION_LEDGER.json']:
        expected = gate['ledger_sha256'] if p.name=='DECISION_LEDGER.json' else inv[str(p.relative_to(arc))]['sha256']
        require(sha(p)==expected, 'actual archived input changed '+str(p))
    require(sha(video)==spec['video_sha256'] and sha(source)==spec['source_pose_sha256'],'input identity')
    protocol=read(POST/'PROTOCOL.json'); case=[c for c in protocol['cases'] if c['run_id']==spec['run_id']][0]
    require(case['windows']==spec['windows'] and protocol['thresholds']==spec['thresholds'],'evaluation scope changed')
    for path,digest in protocol['frozen_external'].items(): require(sha(path)==digest,'external hash changed '+path)
    parents={}
    for name in case['comparators']:
        r=protocol['parents'][name]; p=POST/r['pose']
        require(sha(p)==r['pose_sha256'] and read(p)['video']['sha256']==r['video_sha256'] and sha(r['video'])==r['video_sha256'],'parent binding '+name)
        parents[name]=p
    return spec,arc,video,source,protocol,case,parents

def pose():
    started=time.monotonic()
    with formal.locked():
        spec,arc,video,source,protocol,case,parents=inputs()
        require(not (HERE/'POSE_COMPLETE.json').exists() and not (HERE/'pose').exists(),'pose already exists; explicit review required')
        cmd=[sys.executable,str(frozen.OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(HERE/'pose'),'--threads','4','--stride','1']
        for f in protocol['fixed_visual_frames']:cmd+=['--overlay-frame',str(f)]
        with (HERE/'pose.log').open('x') as log:
            r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4'),timeout=240)
        require(r.returncode==0,'pose technical failure')
        sys.path.insert(0,str(ROOT/'scripts'))
        from scan_current_pose import valid_pose
        target=HERE/'pose'/(video.stem+'.pose.json'); raw=valid_pose(target)
        require(raw['video']['sha256']==sha(video),'pose video identity')
        proof=frozen.check_provenance(read(source)['provenance'],raw['provenance'],[read(p)['provenance'] for p in parents.values()],read(source)['video']['sha256'])
        files={str(p.relative_to(HERE)):sha(p) for p in (HERE/'pose').rglob('*') if p.is_file()}
        result={'passed':True,'pose':str(target),'pose_sha256':sha(target),'input_sha256':sha(video),'source_pose_sha256':sha(source),'provenance':proof,'files':files,'seconds':time.monotonic()-started,'no_GPU':True,'threads':4}
        save(HERE/'POSE_COMPLETE.json',result)
        return {'phase':'pose','passed':True,'seconds':result['seconds'],'pose_sha256':result['pose_sha256']}

def metrics():
    started=time.monotonic()
    with formal.locked():
        spec,arc,video,source,protocol,case,parents=inputs(); proof=read(HERE/'POSE_COMPLETE.json')
        for rel,digest in proof['files'].items():require(sha(HERE/rel)==digest,'priority pose inventory changed')
        target=Path(proof['pose']); require(sha(target)==proof['pose_sha256'],'priority pose changed')
        dest=HERE/'metrics';require(not dest.exists(),'metrics already exists; explicit review required');dest.mkdir()
        sys.path.insert(0,str(ROOT/'scripts'))
        import timing_metrics as tm
        from scan_current_pose import observe
        poses={**parents,'auto':target}
        fixed=frozen.fixed_metrics(source,poses,case['windows'],protocol['thresholds'],tm)
        save(dest/'FIXED_WINDOWS.json',{'windows':case['windows'],'results':fixed})
        # Same source-normalized feature representation, shared minimum weights.
        ledger=read(arc/'DECISION_LEDGER.json'); regions=frozen.region_sets(ledger,case); save(dest/'REGIONS.json',regions)
        common={}
        for names in [list(poses),[case['comparators'][0],'auto']]:
            label='__'.join(names); common[label]={}
            for confidence in protocol['thresholds']:
                v=frozen.common_regions(source,{n:poses[n] for n in names},regions,confidence,tm)
                save(dest/f'COMMON_{label}_{confidence}.json',v)
                common[label][str(confidence)]=v
        scans={}
        for name,path in poses.items():
            scan=observe(source,path,19);save(dest/f'{name}_WHOLE_SCAN.json',scan)
            s=observer_summary(scan);scans[name]={k:v for k,v in s.items() if k!='support'}
        compact={}
        for name,cs in fixed.items():
            compact[name]={}
            for conf,v in cs.items():
                compact[name][conf]=[{'window':r['window'],'feature':r['feature'],'status':r['status'],'lag':r['reliable_lag_frames'],'flags':r.get('flags'),'same_frame':r.get('same_frame'),'best':r.get('best')} for r in v['diagnostics']]
        common_compact={label:{c:[{k:v for k,v in row.items() if k not in ('common_valid_mask','common_weights','source_frames')} for row in record['rows']] for c,record in cs.items()} for label,cs in common.items()}
        result={'scope':'independent priority final-only evaluation; formal consumer still performs full observer replay and final check','input_sha256':sha(video),'pose_sha256':sha(target),'source_pose_sha256':sha(source),'frozen_protocol_sha256':spec['formal_protocol_sha256'],'fixed':compact,'whole_scan':scans,'common_support':common_compact,'active_indices':ledger['active_indices'],'NFE':ledger['NFE'],'manual_quality':'root fixed frames viewed separately; no comprehensive identity/ghosting claim','seconds':time.monotonic()-started,'UNKNOWN_retained':True,'formal_match_pending':True}
        save(HERE/'SUMMARY.json',result)
        files={str(p.relative_to(HERE)):sha(p) for p in dest.rglob('*') if p.is_file()}
        save(HERE/'METRICS_COMPLETE.json',{'passed':True,'files':files,'summary_sha256':sha(HERE/'SUMMARY.json'),'seconds':result['seconds']})
        return {'phase':'metrics','passed':True,'seconds':result['seconds'],'summary_sha256':sha(HERE/'SUMMARY.json')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['pose','metrics','imports']);a=p.parse_args()
    try:
        if a.phase=='imports':
            sys.path.insert(0,str(ROOT/'scripts'));import timing_metrics,scan_current_pose
            print(json.dumps({'imports':True,'root':str(ROOT),'GPU':False}))
        else: print(json.dumps(globals()[a.phase]()))
    except BlockingIOError:
        print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
