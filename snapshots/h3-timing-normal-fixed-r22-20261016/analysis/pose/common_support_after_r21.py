"""Explicit post-R21 CPU comparison. No implicit waiting, pose extraction or GPU."""
import argparse,fcntl,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('/data5/researcher/h3_runs/timing_normal_fixed_r22_20261016')
R14=Path('/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016')
R21=Path('/data5/researcher/h3_runs/timing_coarse_to_pose_r21_20261016')
OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--r21-pose',type=Path);p.add_argument('--r21-completion',type=Path);a=p.parse_args()
    if not a.execute:print(json.dumps({'status':'prepared_only','requires':'actual completed R21 final pose and completion gate; do not substitute R14'}));return
    if not a.r21_pose or not a.r21_completion:raise ValueError('Actual R21 artifacts required')
    for path in (a.r21_pose,a.r21_completion):
        if not path.resolve().is_relative_to((R21/'analysis').resolve()):raise ValueError('R21 evidence must remain in its own analysis tree')
    gate=read(a.r21_completion)
    if not (gate.get('status')=='pass' and gate.get('cleanup_verified')):raise ValueError('R21 actual completion/cleanup not passed')
    run='r21_s05_seed1313_coarse_pose';h=read(R21/'logs'/f'{run}_history.json');g=read(R21/'configs'/f'{run}.json')
    if h['status']['status_str']!='success' or not h['status']['completed'] or h['prompt'][2]!=g:raise ValueError('R21 actual history mismatch')
    items=[i for k,n in g.items() if n['class_type']=='SaveVideo' for i in h['outputs'].get(k,{}).get('images',[]) if i.get('type')=='output' and i['filename'].endswith('.mp4')]
    if len(items)!=1:raise ValueError('Need unique R21 actual MP4')
    v=R21/'output'/items[0].get('subfolder','')/items[0]['filename']
    if not v.resolve().is_relative_to((R21/'output').resolve()) or read(a.r21_pose)['video']['sha256']!=sha(v):raise ValueError('R21 final pose is not its actual controlled output')
    r14pose=R14/'analysis/pose/pilot/r14_s05_seed1313_native_host9_00001_.pose.json'
    if sha(r14pose)!='4843ee7280367b2f80aa021b7c44592c5af2f56dd0d7a58a5af95a07b25a6ae3':raise ValueError('Frozen R14 normal pose differs')
    folder=ROOT/'analysis/pose';b=read(folder/'bundles/r22_s05_seed1313_full6to11.json')
    r22pose=folder/'pilot'/(Path(b['relative_video']).stem+'.pose.json')
    if not read(folder/'replication/r22_s05_seed1313_full6to11_integrity.json')['passed'] or read(r22pose)['video']['sha256']!=b['video_sha256']:raise ValueError('R22 final result not passed/bound')
    source=OLD/'analysis/pose/old_sam/05_real_megumi_v.pose.json';tool=OLD/'analysis/pose/compare_runs.py'
    if sha(tool)!='1e725cd5063ae9e9e770f94c54c91dfa5d0473e951e92dfcebaa56619c844b33' or sha(source)!='e0795dc6c9fc652d82b5353f1de18711adffc053920928f2d4687fd195031852':raise ValueError('Frozen metric/source differs')
    os.environ['CUDA_VISIBLE_DEVICES']=''
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='4'
    out=folder/'common_support';out.mkdir(exist_ok=True);started=time.time();poses={'native':r14pose,'hybrid':a.r21_pose,'fixed':r22pose}
    with Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for t in (.3,.5):
            command=[sys.executable,str(tool),'--source',str(source),'--confidence',str(t),'--output',str(out/f'three_arm_{t}.json')]
            for name,p in poses.items():command+=['--run',name+'='+str(p)]
            for w in ('50:65','69:81','80:92','99:111','0:46','47:67','68:140','112:140','0:140'):command+=['--window',w]
            done=subprocess.run(command,capture_output=True,text=True)
            (out/f'three_arm_{t}.log').write_text(done.stdout+'\n'+done.stderr)
            if done.returncode:raise RuntimeError('Frozen common-support metric failed')
    result={'status':'complete','pose_inventory':{k:{'path':str(p),'sha256':sha(p)} for k,p in poses.items()},'CPU_seconds':time.time()-started,'NFE_added':0,'unknowns_preserved':True,'scope':'Same exact arm-set joint intersection and minimum-confidence weights; R21 actual controlled output, not historical native future endpoints.'}
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
