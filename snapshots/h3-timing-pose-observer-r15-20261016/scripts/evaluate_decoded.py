"""One bounded CPU-only evaluator for the seven already-complete R15 decodes.

No waiting and no GPU. Missing/incomplete producer output fails admission. This
script does not tune or replace the frozen pose thresholds, windows or gates.
"""
import argparse
import fcntl
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import decode_endpoint as adapter

ROOT = Path(__file__).resolve().parents[1]
OLD = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
SOURCE = OLD/'analysis/pose/old_sam/05_real_megumi_v.pose.json'
PROTOCOL = ROOT/'analysis/intermediate_observer_protocol.txt'
PROTOCOL_SHA = '92c093d6896a1eab563d69a33a707c23d7ade491c614fbf84ae123e89f10f3e2'
FROZEN = {
    'scripts/pose_probe.py':'04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f',
    'scripts/timing_metrics.py':'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e',
    'analysis/pose/compare_runs.py':'1e725cd5063ae9e9e770f94c54c91dfa5d0473e951e92dfcebaa56619c844b33',
    'analysis/pose/evaluate_x0.py':'3ec61c9c2e1fc0eb250b3428a3414cba5a897ad74450b0b70c633d388473dadf',
    'analysis/pose/old_sam/05_real_megumi_v.pose.json':'e0795dc6c9fc652d82b5353f1de18711adffc053920928f2d4687fd195031852',
}
VAE_SHA='7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522'
WINDOWS=('50:65','69:81','80:92','99:111')

def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def video_gate(path):
    command=['ffprobe','-v','error','-select_streams','v:0','-show_entries',
             'stream=width,height,avg_frame_rate,nb_frames,time_base:frame=best_effort_timestamp_time',
             '-show_frames','-of','json',str(path)]
    result=json.loads(subprocess.check_output(command,text=True));s=result['streams'][0]
    adapter.require([s['width'],s['height'],s['avg_frame_rate'],int(s['nb_frames'])]==[1312,736,'24/1',141], 'Decoded MP4 stream geometry differs')
    pts=[float(f['best_effort_timestamp_time']) for f in result['frames']]
    adapter.require(len(pts)==141 and all(abs(p-i/24)<2e-6 for i,p in enumerate(pts)), 'Decoded MP4 PTS shifted/resampled')
    return {'stream':s,'frames':len(pts),'uniform_pts':True,'first_pts':pts[0],'last_pts':pts[-1]}

def command_run(command,log,env):
    started=time.time()
    with log.open('w') as handle:
        subprocess.run(command,stdout=handle,stderr=subprocess.STDOUT,env=env,check=True)
    return time.time()-started

def compact(data):
    result={}
    for window in WINDOWS:
        rows=data['diagnostics'][window]
        direction=[rows[t]['arm_direction'].get('reliable_lag_frames') for t in ('0.3','0.5')]
        wrist=[rows[t]['wrist_relative'].get('reliable_lag_frames') for t in ('0.3','0.5')]
        known=all(x is not None for x in direction+wrist)
        result[window]={'direction_lags':direction,'wrist_lags':wrist,
                        'frozen_observability':data['observability'][window],
                        'both_features_both_thresholds_within_two':known and all(abs(x)<=2 for x in direction+wrist),
                        'all_four_known':known}
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');args=p.parse_args()
    if not args.execute:
        print('No action. Add --execute only after seven decode records are complete.');return
    os.environ['CUDA_VISIBLE_DEVICES']=''
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='4'
    env=os.environ.copy()
    analysis=ROOT/'analysis/pose';analysis.mkdir(parents=True,exist_ok=True)
    decoded=ROOT/'analysis/x0_decoded'
    # Preflight before acquiring the shared lock; no long wait holds CPU ownership.
    inventory=json.loads((ROOT/'analysis/input_inventory.json').read_text())['inputs']
    expected_stems=[r['case']+f"_step{r['index']:03d}" for r in inventory]
    for stem in expected_stems:
        adapter.require((decoded/(stem+'.json')).exists() and json.loads((decoded/(stem+'.json')).read_text())['status']=='complete','Missing/incomplete decoded producer '+stem)
    with (analysis/'coordinator.lock').open('a') as own, Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as shared:
        fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.flock(shared,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for rel,wanted in FROZEN.items():adapter.require(adapter.sha(OLD/rel)==wanted,'Frozen evidence changed: '+rel)
        adapter.require(adapter.sha(PROTOCOL)==PROTOCOL_SHA,'Frozen intermediate protocol changed')
        processes=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','pid=,args='],text=True)
        if any(any(name in line for name in ('pose_probe.py','timing_metrics.py','evaluate_x0.py')) for line in processes.splitlines()):
            raise RuntimeError('Existing pose worker; do not duplicate')
        import torch
        torch.set_num_threads(4);torch.set_num_interop_threads(1)
        module=adapter.decoder_module();sys.path.insert(0,str(adapter.R12/'extensions'))
        core=importlib.import_module('H3X0Readout.core')
        started=time.time();records=[];summary={}
        for source,stem in zip(inventory,expected_stems):
            record=json.loads((decoded/(stem+'.json')).read_text());video=decoded/(stem+'.mp4')
            payload=adapter.build_loader(module,source)(Path(source['path']),core)
            adapter.require(record['snapshot_metadata']==payload['metadata'],'Decode metadata differs from validated source')
            adapter.require(record['snapshot']==source['path'] and record['snapshot_sha256']==source['sha256'],'Decode input binding differs')
            adapter.require(record['vae_sha256']==VAE_SHA and record['decoded_shape']==[141,736,1312,3],'Decode VAE/shape differs')
            adapter.require(record['output_sha256']==adapter.sha(video),'Decoded MP4 hash differs')
            admission={'stem':stem,'case':source['case'],'index':source['index'],'decode_record_sha256':adapter.sha(decoded/(stem+'.json')),
                       'snapshot_sha256':source['sha256'],'video_sha256':record['output_sha256'],'timebase':video_gate(video),
                       'vae_wall_seconds':record['finished_unix']-record['started_unix']}
            pose=analysis/(stem+'.pose.json')
            cached=pose.exists() and json.loads(pose.read_text())['video']['sha256']==record['output_sha256']
            admission['pose_cache_reused']=cached
            if not cached:
                adapter.require(not pose.exists(),'Existing pose binds another video; preserve and inspect')
                admission['pose_wall_seconds']=command_run([sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),
                    '--output-dir',str(analysis),'--threads','4','--overlay-frame','55','--overlay-frame','86','--overlay-frame','105'],analysis/(stem+'.pose.log'),env)
            admission['metric_wall_seconds']=command_run([sys.executable,str(OLD/'analysis/pose/evaluate_x0.py'),'--source',str(SOURCE),
                '--pose',str(pose),'--checkpoint',stem,'--protocol',str(PROTOCOL),'--output',str(analysis/(stem+'.observer.json'))],analysis/(stem+'.observer.log'),env)
            data=json.loads((analysis/(stem+'.observer.json')).read_text())
            adapter.require(data['edited_video']['sha256']==record['output_sha256'],'Frozen pose binds wrong video')
            summary[stem]=compact(data);records.append(admission)
            save(analysis/'compact_summary.json',summary);save(analysis/'intake_manifest.json',{'rows':records,'source_pose_sha256':adapter.sha(SOURCE)})
            print(json.dumps({'completed':stem,'main_window':summary[stem]['50:65']}),flush=True)
        for case in ('r10_native','r14_native'):
            selected=[s for s in expected_stems if s.startswith(case)]
            for threshold in (.3,.5):
                command=[sys.executable,str(OLD/'analysis/pose/compare_runs.py'),'--source',str(SOURCE),'--confidence',str(threshold),
                         '--output',str(analysis/(case+f'_common_support_{threshold}.json'))]
                for stem in selected:command+=['--run',stem+'='+str(analysis/(stem+'.pose.json'))]
                for window in WINDOWS+('0:46','47:67','68:140','112:140'):command+=['--window',window]
                command_run(command,analysis/(case+f'_common_support_{threshold}.log'),env)
        adapter.require(not torch.cuda.is_initialized(),'CPU evaluator initialized CUDA')
        save(analysis/'completion.json',{'status':'complete','rows':records,'started_unix':started,'finished_unix':time.time(),
             'cpu_only':True,'nfe':0,'cuda_initialized':False,'frozen_hashes':FROZEN,
             'note':'Earliest among measured points only; counterfactual native R10 endpoints do not prove stop-and-continue efficacy.'})
if __name__=='__main__':main()
