"""Frozen four-arm common-support report after both formal R16 poses exist.

CPU-only postprocessing, no detector/model reruns. Run once under shared locks
after the single consumer exits. This file never changes root's auxiliary code.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('/data5/researcher/h3_runs/timing_local_route_r16_20261016')
OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
R3=Path('/data5/researcher/h3_runs/timing_spatial_r3_20261016/analysis/pose/pilot')
SOURCE=OLD/'analysis/pose/old_sam/05_real_megumi_v.pose.json'
BASELINES={
    'native':('r3_s05_native_00001_.pose.json','45e130c98e8e39e29efaab7f8d0158695170357182525b5e3ef1742867765759'),
    'full':('r3_s05_full_6to14_00001_.pose.json','9ad37e2485618dda8edc6eef75f7ac1e8b5687742ba6e88fad3a317ed4132739'),
}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    os.environ['CUDA_VISIBLE_DEVICES']=''
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='4'
    out=ROOT/'analysis/pose';result=out/'common_support';result.mkdir(exist_ok=True)
    with Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert sha(OLD/'analysis/pose/compare_runs.py')=='1e725cd5063ae9e9e770f94c54c91dfa5d0473e951e92dfcebaa56619c844b33'
        assert sha(OLD/'analysis/pose/evaluate_x0.py')=='3ec61c9c2e1fc0eb250b3428a3414cba5a897ad74450b0b70c633d388473dadf'
        protocol=out/'intermediate_observer_protocol.txt'
        assert sha(protocol)=='92c093d6896a1eab563d69a33a707c23d7ade491c614fbf84ae123e89f10f3e2'
        poses={}
        for name,(file,wanted) in BASELINES.items():
            assert sha(R3/file)==wanted;poses[name]=R3/file
        for name,run in [('roi','r16_s05_roi_6to14'),('uniform','r16_s05_uniform_6to14')]:
            b=json.loads((out/'bundles'/(run+'.json')).read_text())
            integrity=json.loads((out/'replication'/(run+'_integrity.json')).read_text());assert integrity['passed']
            p=out/'pilot'/(Path(b['relative_video']).stem+'.pose.json')
            assert json.loads(p.read_text())['video']['sha256']==b['video_sha256'];poses[name]=p
        started=time.time();all_rows={}
        for name,p in poses.items():
            dest=result/(name+'.observer.json')
            subprocess.run([sys.executable,str(OLD/'analysis/pose/evaluate_x0.py'),'--source',str(SOURCE),'--pose',str(p),
                            '--checkpoint',name,'--protocol',str(protocol),'--output',str(dest)],check=True,capture_output=True,text=True)
            all_rows[name]=json.loads(dest.read_text())
        common={}
        for t in (.3,.5):
            dest=result/f'four_arm_{t}.json'
            command=[sys.executable,str(OLD/'analysis/pose/compare_runs.py'),'--source',str(SOURCE),'--confidence',str(t),'--output',str(dest)]
            for name,p in poses.items():command+=['--run',name+'='+str(p)]
            for w in ('50:65','69:81','80:92','99:111','0:46','47:67','68:140','112:140','0:140'):command+=['--window',w]
            subprocess.run(command,check=True,capture_output=True,text=True)
            common[str(t)]=[dict(window=x['window'],feature=x['feature'],common_valid_fraction=x['common_valid_fraction'],
                status=x['status'],errors={k:v['same_frame_error_on_common_support'] for k,v in x['runs'].items()})
                for x in json.loads(dest.read_text())['results']]
        summary={'status':'complete','four_arm_common_support':common,
                 'observability':{name:d['observability'] for name,d in all_rows.items()},
                 'pose_inventory':{name:{'path':str(p),'sha256':sha(p)} for name,p in poses.items()},
                 'source_sha256':sha(SOURCE),'cpu_seconds':time.time()-started,'NFE_added':0,
                 'all_unknown_retained':True,'scope':'Known source05 seed1; four-arm valid-joint intersection. Not an independent benchmark or novelty verdict.'}
        (out/'four_arm_compact.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps({'status':'complete','summary':str(out/'four_arm_compact.json'),'cpu_seconds':summary['cpu_seconds']}))
if __name__=='__main__':main()
