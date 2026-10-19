"""Admit two explicitly decoded R12 snapshots and measure frozen pose on CPU.

No VAE/DiT or GPU execution. Producer decode must be complete before admission.
"""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

import consumer_r12 as common

HERE=Path(__file__).resolve().parent
RUN='r12_s05_native_observer'
STEMS=('x0_step010','x0_step015')
REMOTE=PurePosixPath('/data5/researcher/h3_runs/timing_native_observer_r12_20261016')
CPU=REMOTE/'analysis/pose/early'
OLD=Path(common.OLD_ROOT)
PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
EXTRA_FROZEN={'analysis/pose/evaluate_x0.py':'3ec61c9c2e1fc0eb250b3428a3414cba5a897ad74450b0b70c633d388473dadf'}
PROTOCOL_SHA='92c093d6896a1eab563d69a33a707c23d7ade491c614fbf84ae123e89f10f3e2'
SHARED_LOCAL=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def admit(stem, record, capture):
    if stem not in STEMS:raise ValueError('Only authorized existing snapshots10/15')
    m=record['snapshot_metadata']
    if record['status']!='complete' or capture['status']!='complete':raise ValueError('Incomplete decode/capture')
    if m['run_id']!=RUN or capture['run_id']!=RUN:raise ValueError('Wrong run')
    if m['snapshot_kind']!='x0_estimate' or m['step_zero_based']!=int(stem[-3:]):raise ValueError('Wrong checkpoint')
    if m['normalization_stage']!='after_process_latent_out' or m['total_steps']!=20:raise ValueError('Wrong normalization/steps')
    if m['geometry']!={'width':1312,'height':736,'frames':141,'fps':24}:raise ValueError('Wrong geometry')
    if record['fps']!=24 or record['decoded_shape']!=[141,736,1312,3]:raise ValueError('Wrong decoded geometry')
    if record['snapshot']!=str(REMOTE/'audit/x0'/RUN/(stem+'.pt')):raise ValueError('Wrong decoded tensor path')
    entries=[r for r in capture['captures'] if r['file']==stem+'.pt']
    if len(entries)!=1 or any(entries[0].get(k)!=v for k,v in m.items()):raise ValueError('Metadata differs from actual capture')
    return {'run_id':RUN,'checkpoint':stem,'zero_based_forward_index':m['step_zero_based'],
            'video_sha256':record['output_sha256'],'snapshot_sha256':record['snapshot_sha256'],
            'decoded_record_complete':True,'capture_metadata_equal':True,'vae_sha256':record['vae_sha256']}


def cpu_worker(bundle_path, cpu_dir):
    root=Path(cpu_dir);bundle=json.loads(Path(bundle_path).read_text())
    with ExitStack() as stack:
        for lock_path in (Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock'),root/'worker.lock'):
            lock=stack.enter_context(lock_path.open('a'));fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for rel,wanted in {**common.FROZEN,**EXTRA_FROZEN}.items():
            if common.digest(OLD/rel)!=wanted:raise ValueError('Frozen source/protocol changed: '+rel)
        protocol=root/'intermediate_observer_protocol.txt'
        if common.digest(protocol)!=PROTOCOL_SHA:raise ValueError('Copied frozen intermediate protocol changed')
        processes=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','pid=,args='],text=True)
        if any(any(n in line for n in ('pose_probe.py','timing_metrics.py','evaluate_x0.py')) for line in processes.splitlines()):
            raise RuntimeError('Another pose/metric worker is active')
        os.environ['CUDA_VISIBLE_DEVICES']=''
        for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='4'
        import cv2
        cv2.setNumThreads(1)
        out=root/'results';out.mkdir(exist_ok=True)
        for row in bundle['rows']:
            stem=row['checkpoint'];video=root/'raw'/(stem+'.mp4')
            if common.digest(video)!=row['video_sha256']:raise ValueError('Raw early-video SHA mismatch')
            cap=cv2.VideoCapture(str(video));geometry=[int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),cap.get(cv2.CAP_PROP_FPS)];cap.release()
            if geometry!=[141,736,1312,24.0]:raise ValueError('Actual early-video geometry mismatch')
            pose=out/(stem+'.pose.json')
            if not pose.is_file() or json.loads(pose.read_text())['video']['sha256']!=row['video_sha256']:
                with (out/(stem+'.extract.log')).open('w') as log:
                    subprocess.run([sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(out),'--threads','4','--overlay-frame','55','--overlay-frame','86','--overlay-frame','105'],stdout=log,stderr=subprocess.STDOUT,check=True)
            command=[sys.executable,str(OLD/'analysis/pose/evaluate_x0.py'),'--source',common.SOURCE_POSE,'--pose',str(pose),'--checkpoint',RUN+'/'+stem,'--protocol',str(protocol),'--output',str(out/(stem+'.observer.json'))]
            result=subprocess.run(command,capture_output=True,text=True,check=True)
            (out/(stem+'.observer.stdout.json')).write_text(result.stdout)
        if common.digest(OLD/'analysis/pose/compare_runs.py')!='1e725cd5063ae9e9e770f94c54c91dfa5d0473e951e92dfcebaa56619c844b33':raise ValueError('Frozen common-support script changed')
        final=root.parent/'pilot/r12_s05_native_observer_00001_.pose.json'
        if json.loads(final.read_text())['video']['sha256']!='f9599f1f90daba73076c06ba8076a512f69c132e5587cdf5417ec91b720726f0':raise ValueError('Wrong frozen final pose')
        for threshold in (0.3,0.5):
            command=[sys.executable,str(OLD/'analysis/pose/compare_runs.py'),'--source',common.SOURCE_POSE,'--confidence',str(threshold),'--output',str(out/f'common_support_threshold{threshold}.json')]
            for stem in STEMS:command+=['--run',stem+'='+str(out/(stem+'.pose.json'))]
            command+=['--run','final='+str(final)]
            for window in ('50:65','69:81','80:92','99:111','0:46','47:67','68:140','112:140'):command+=['--window',window]
            result=subprocess.run(command,capture_output=True,text=True,check=True)
            (out/f'common_support_threshold{threshold}.stdout.json').write_text(result.stdout)
        common.save(root/'cpu_complete.json',{'status':'complete','run_id':RUN,'snapshots':list(STEMS),'no_gpu':True,'new_threshold_or_window_selection':False,'bundle_sha256':common.digest(bundle_path)})


def main():
    p=argparse.ArgumentParser();p.add_argument('--decoded-root');p.add_argument('--cpu-worker');p.add_argument('--cpu-dir',default=str(CPU));args=p.parse_args()
    if args.cpu_worker:return cpu_worker(args.cpu_worker,args.cpu_dir)
    if not args.decoded_root:p.error('Explicit completed decoded-root required; this never waits for or launches a decoder')
    root=HERE/'early';root.mkdir(exist_ok=True)
    with (root/'coordinator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        capture_path=REMOTE/'audit/x0'/RUN/'manifest.json'
        capture_raw=common.remote_read('H3_SERVER_A',capture_path);capture=json.loads(capture_raw)
        (root/'capture_manifest.json').write_bytes(capture_raw)
        rows=[]
        for stem in STEMS:
            src=PurePosixPath(args.decoded_root)/stem
            record_path=root/'records'/(stem+'.json');common.copy_from('H3_SERVER_A',str(src)+'.json',record_path)
            record=json.loads(record_path.read_text());row=admit(stem,record,capture)
            inventory=json.loads((HERE/'replication'/RUN/'capture_inventory.json').read_text())
            entries=[e for e in inventory['rows'] if e['file']==stem+'.pt']
            if not inventory['passed'] or len(entries)!=1 or entries[0]['file_sha256']!=row['snapshot_sha256']:
                raise ValueError('Decode does not bind the independently verified actual snapshot')
            wanted_vae='7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522'
            if row['vae_sha256']!=wanted_vae:raise ValueError('Unregistered VAE checkpoint')
            video=root/'raw'/(stem+'.mp4');common.copy_from('H3_SERVER_A',str(src)+'.mp4',video)
            if common.digest(video)!=row['video_sha256']:raise ValueError('Downloaded decoded-video SHA mismatch')
            row.update(decoded_video=str(src)+'.mp4',decode_record_sha256=common.digest(record_path));rows.append(row)
        bundle={'run_id':RUN,'rows':rows,'capture_manifest_sha256':common.digest(root/'capture_manifest.json'),
                'source_pose_sha256':common.FROZEN['analysis/pose/old_sam/05_real_megumi_v.pose.json'],
                'scope':'Independent frozen pose measurement of decoded early estimates. R12 stop-point estimates are independently measured; internal readout is not a target label. No new DiT execution.'}
        common.save(root/'intake_manifest.json',bundle)
        with SHARED_LOCAL.open('a') as heavy:
            fcntl.flock(heavy,fcntl.LOCK_EX)
            common.shell('H3_SERVER_A',['mkdir','-p',str(CPU/'raw'),str(CPU/'results')])
            protocol=Path('/Users/researcher/DevProjects/h3-timing-autoresearch-20261016/configs/intermediate_observer_protocol.txt')
            if common.digest(protocol)!=PROTOCOL_SHA:raise ValueError('Local frozen protocol changed')
            for file in (HERE/'evaluate_early.py',HERE/'consumer_r12.py',root/'intake_manifest.json',protocol):
                subprocess.run(['scp',*common.jump_options('H3_SERVER_A'),'-q',str(file),f'H3_SERVER_A:{CPU}/{file.name}'],check=True)
            for stem in STEMS:subprocess.run(['scp',*common.jump_options('H3_SERVER_A'),'-q',str(root/'raw'/(stem+'.mp4')),f'H3_SERVER_A:{CPU}/raw/{stem}.mp4'],check=True)
            print(common.shell('H3_SERVER_A',[PYTHON,str(CPU/'evaluate_early.py'),'--cpu-worker',str(CPU/'intake_manifest.json'),'--cpu-dir',str(CPU)]),flush=True)
            subprocess.run(['scp',*common.jump_options('H3_SERVER_A'),'-qr',f'H3_SERVER_A:{CPU}/results',str(root)],check=True)
            common.copy_from('H3_SERVER_A',CPU/'cpu_complete.json',root/'cpu_complete.json')
        summary={}
        for stem in STEMS:
            data=json.loads((root/'results'/(stem+'.observer.json')).read_text())
            if data['edited_video']['sha256']!=next(r['video_sha256'] for r in rows if r['checkpoint']==stem):raise ValueError('Pose binds wrong early video')
            summary[stem]={'observability':data['observability'],'diagnostics_sha256':common.digest(root/'results'/(stem+'.observer.json'))}
        common.save(root/'compact_summary.json',summary)
        print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
