"""Admit three newly saved decoded R9 hold2 snapshots and measure frozen pose on CPU.

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

import consumer_r9 as common

HERE=Path(__file__).resolve().parent
RUN='r9_s05_hold2'
STEMS=('x0_step006','x0_step007','x0_step008')
REMOTE=PurePosixPath('/data3/researcher/h3_runs/timing_hold_control_r9_20261016')
PRODUCER='H3_SERVER_B'
CPU=PurePosixPath('/data5/researcher/h3_runs/timing_hold_control_r9_20261016/analysis/pose/early')
OLD=Path(common.OLD_ROOT)
PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
EXTRA_FROZEN={'analysis/pose/evaluate_x0.py':'3ec61c9c2e1fc0eb250b3428a3414cba5a897ad74450b0b70c633d388473dadf'}
PROTOCOL_SHA='92c093d6896a1eab563d69a33a707c23d7ade491c614fbf84ae123e89f10f3e2'
SHARED_LOCAL=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def admit(stem, record, capture):
    if stem not in STEMS:raise ValueError('Only authorized hold2 transition snapshots6/7/8')
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
                    subprocess.run([sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(out),'--threads','4','--overlay-frame','55'],stdout=log,stderr=subprocess.STDOUT,check=True)
            command=[sys.executable,str(OLD/'analysis/pose/evaluate_x0.py'),'--source',common.SOURCE_POSE,'--pose',str(pose),'--checkpoint',RUN+'/'+stem,'--protocol',str(protocol),'--output',str(out/(stem+'.observer.json'))]
            result=subprocess.run(command,capture_output=True,text=True,check=True)
            (out/(stem+'.observer.stdout.json')).write_text(result.stdout)
        common.save(root/'cpu_complete.json',{'status':'complete','run_id':RUN,'snapshots':list(STEMS),'no_gpu':True,'new_threshold_or_window_selection':False,'bundle_sha256':common.digest(bundle_path)})


def inherit_prefix_pose(root):
    old=Path('/Users/researcher/DevProjects/h3-timing-feedback-r6-20261016/analysis/pose')
    prefix=json.loads((HERE/'replication/preintervention_gate.json').read_text())
    record_path=old/'early/records/x0_step005.json'
    reference=json.loads(record_path.read_text())
    pose_path=old/'early/results/x0_step005.pose.json'
    metric_path=old/'early/results/x0_step005.observer.json'
    pose=json.loads(pose_path.read_text());metrics=json.loads(metric_path.read_text())
    video=old/'early/raw/x0_step005.mp4'
    keys=['vae_sha256','core','vae_dtype','fps','runtime_flags','processing','preencode_quantization']
    checks={'actual_prefix_video_audio_bitwise_equal':prefix['passed'] and prefix['actual_video_audio_bitwise_equal'],
            'r6_decode_complete':reference['status']=='complete',
            'r6_decode_video_bound':common.digest(video)==reference['output_sha256']==pose['video']['sha256']==metrics['edited_video']['sha256']}
    for stem in STEMS:
        new=json.loads((root/'records'/(stem+'.json')).read_text())
        checks[stem+'_same_vae_and_recipe']=all(new[k]==reference[k] for k in keys)
    result={'passed':all(checks.values()),'checks':checks,'inherited_index_zero_based':5,
            'source_run':'r6_s05_feedback_retry1','destination_run':RUN,
            'source_observer_report':str(metric_path),'source_observability':metrics['observability'],
            'source_sha256':{str(f):common.digest(f) for f in [record_path,pose_path,metric_path,video]},
            'scope':'Reuse of existing independent pose on the same preintervention tensor, same host and validated VAE/normalization/encoding recipe; no fresh R9 index5 video was decoded, and no additional sample is claimed.'}
    common.save(root/'inherited_index005_pose_gate.json',result)
    if not result['passed']:raise ValueError('Index5 inheritance failed; do not substitute pose truth')


def main():
    p=argparse.ArgumentParser();p.add_argument('--decoded-root');p.add_argument('--cpu-worker');p.add_argument('--cpu-dir',default=str(CPU));args=p.parse_args()
    if args.cpu_worker:return cpu_worker(args.cpu_worker,args.cpu_dir)
    if not args.decoded_root:p.error('Explicit completed decoded-root required; this never waits for or launches a decoder')
    root=HERE/'early';root.mkdir(exist_ok=True)
    with (root/'coordinator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        capture_path=REMOTE/'audit/x0'/RUN/'manifest.json'
        capture_raw=common.remote_read(PRODUCER,capture_path);capture=json.loads(capture_raw)
        (root/'capture_manifest.json').write_bytes(capture_raw)
        rows=[]
        for stem in STEMS:
            src=PurePosixPath(args.decoded_root)/stem
            record_path=root/'records'/(stem+'.json');common.copy_from(PRODUCER,str(src)+'.json',record_path)
            record=json.loads(record_path.read_text());row=admit(stem,record,capture)
            actual_snapshot_sha=common.shell(PRODUCER,['python3','-c','import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())',record['snapshot']]).strip()
            if actual_snapshot_sha!=row['snapshot_sha256']:
                raise ValueError('Decode does not bind the actual producer snapshot SHA')
            video=root/'raw'/(stem+'.mp4');common.copy_from(PRODUCER,str(src)+'.mp4',video)
            if common.digest(video)!=row['video_sha256']:raise ValueError('Downloaded decoded-video SHA mismatch')
            row.update(decoded_video=str(src)+'.mp4',decode_record_sha256=common.digest(record_path));rows.append(row)
        bundle={'run_id':RUN,'rows':rows,'capture_manifest_sha256':common.digest(root/'capture_manifest.json'),
                'source_pose_sha256':common.FROZEN['analysis/pose/old_sam/05_real_megumi_v.pose.json'],
                'scope':'Independent frozen pose measurement of decoded early estimates. Feedback observer output does not set independent pose truth. Indices6/7 are guided endpoint predictions, index8 is a native prediction after guidance stops. Index5 may be inherited only after exact prefix and VAE controls. Output is an endpoint estimate, not the latent trajectory. This exploratory check is not a preregistered efficacy endpoint.'}
        common.save(root/'intake_manifest.json',bundle)
        inherit_prefix_pose(root)
        with SHARED_LOCAL.open('a') as heavy:
            fcntl.flock(heavy,fcntl.LOCK_EX)
            common.shell('H3_SERVER_A',['mkdir','-p',str(CPU/'raw'),str(CPU/'results')])
            protocol=Path('/Users/researcher/DevProjects/h3-timing-autoresearch-20261016/configs/intermediate_observer_protocol.txt')
            if common.digest(protocol)!=PROTOCOL_SHA:raise ValueError('Local frozen protocol changed')
            for file in (HERE/'evaluate_early.py',HERE/'consumer_r9.py',root/'intake_manifest.json',protocol):
                subprocess.run(['scp','-q',str(file),f'H3_SERVER_A:{CPU}/{file.name}'],check=True)
            for stem in STEMS:subprocess.run(['scp','-q',str(root/'raw'/(stem+'.mp4')),f'H3_SERVER_A:{CPU}/raw/{stem}.mp4'],check=True)
            print(common.shell('H3_SERVER_A',[PYTHON,str(CPU/'evaluate_early.py'),'--cpu-worker',str(CPU/'intake_manifest.json'),'--cpu-dir',str(CPU)]),flush=True)
            subprocess.run(['scp','-qr',f'H3_SERVER_A:{CPU}/results',str(root)],check=True)
            common.copy_from('H3_SERVER_A',CPU/'cpu_complete.json',root/'cpu_complete.json')
        summary={}
        for stem in STEMS:
            data=json.loads((root/'results'/(stem+'.observer.json')).read_text())
            if data['edited_video']['sha256']!=next(r['video_sha256'] for r in rows if r['checkpoint']==stem):raise ValueError('Pose binds wrong early video')
            summary[stem]={'observability':data['observability'],'diagnostics_sha256':common.digest(root/'results'/(stem+'.observer.json'))}
        common.save(root/'compact_summary.json',summary)
        print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
