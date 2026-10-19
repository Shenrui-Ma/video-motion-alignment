"""Exact-history intake on Mac; optional serial CPU evaluation on existing .9 tools.

Never contacts a Comfy port, submits jobs, installs packages, or starts a GPU.
Prepare only until the parent confirms sampling. Benchmarks are rejected.
"""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import time

OLD_ROOT = '/data5/researcher/h3_runs/timing_autoresearch_20261016'
SOURCE_POSE = OLD_ROOT + '/analysis/pose/old_sam/05_real_megumi_v.pose.json'
FROZEN = {
    'scripts/pose_probe.py': '04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f',
    'scripts/timing_metrics.py': 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e',
    'analysis/pose/old_sam/05_real_megumi_v.pose.json': 'e0795dc6c9fc652d82b5353f1de18711adffc053920928f2d4687fd195031852',
}
SOURCE_VIDEO_SHA = 'c80a126374966191cf87eebb8b8952d84fc88a7d6a56ca4c8be01a099ca2a857'
WINDOWS = ['50:65', '69:81', '80:92', '99:111']


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def formal_run(run):
    if run != 'r8_s05_normal_feedback':
        raise ValueError('Only registered formal R8 normal feedback run; benchmarks are excluded')
    return run


def validate_history(run, history, config):
    formal_run(run)
    if history.get('status', {}).get('status_str') != 'success' or not history['status'].get('completed'):
        raise ValueError('Actual history is not complete success')
    graph = history['prompt'][2]
    if graph != config:
        raise ValueError('Actual executed graph differs from archived producer config')
    routers = [n for n in graph.values() if n['class_type'] in ('H3FeedbackRouter',)]
    if len(routers) != 1 or routers[0]['inputs']['run_id'] != run:
        raise ValueError('Actual history router/run identity mismatch')
    refs = [n['inputs'] for n in graph.values() if n['class_type'] == 'H3EventAuditReference']
    creators = [n['inputs'] for n in graph.values() if n['class_type'] == 'CreateVideo']
    if len(refs) != 1 or len(creators) != 1:
        raise ValueError('Expected one reference encoder and one CreateVideo')
    items = [item for k,n in graph.items() if n['class_type'] == 'SaveVideo'
             for item in history.get('outputs', {}).get(k, {}).get('images', [])
             if item.get('type') == 'output' and item.get('filename', '').endswith('.mp4')]
    if len(items) != 1:
        raise ValueError('Expected one exact SaveVideo MP4')
    item = items[0]
    relative = PurePosixPath(item.get('subfolder', '')) / item['filename']
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe output path')
    return {'run_id': run, 'prompt_id': history['prompt'][1], 'history_output': item,
            'relative_video': str(relative), 'expected_geometry': {
                'width': refs[0]['width'], 'height': refs[0]['height'],
                'frames': refs[0]['length'], 'fps': creators[0]['fps']},
            'router_inputs': routers[0]['inputs']}


def remote_read(host, path):
    return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2', host, 'cat ' + shlex.quote(str(path))])


def copy_from(host, src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['scp', '-q', f'{host}:{src}', str(dst)], check=True)


def shell(host, argv):
    return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2', host, shlex.join(argv)], text=True)


def intake(args, run):
    formal_run(run)
    local = Path(args.local_dir)
    producer = PurePosixPath(args.producer_root)
    dest = local/'pilot'/f'{run}_provenance'
    history_raw = remote_read(args.producer_host, producer/'logs'/f'{run}_history.json')
    config_raw = remote_read(args.producer_host, producer/'configs'/f'{run}.json')
    history, config = json.loads(history_raw), json.loads(config_raw)
    dest.mkdir(parents=True, exist_ok=True)
    # Preserve the actual history even when success/geometry/extraction later fails.
    (dest/'history.json').write_bytes(history_raw)
    (dest/'config.json').write_bytes(config_raw)
    admission = validate_history(run, history, config)
    remote_video = producer/'output'/admission['relative_video']
    # Producer is read-only. Hash before and after download to reject mutable output.
    code = 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())'
    before = shell(args.producer_host, ['python3', '-c', code, str(remote_video)]).strip()
    video = local/'raw'/admission['relative_video']
    if not video.exists() or digest(video) != before:
        copy_from(args.producer_host, remote_video, video)
    after = shell(args.producer_host, ['python3', '-c', code, str(remote_video)]).strip()
    if not before == after == digest(video):
        raise ValueError('MP4 hash changed or download mismatch')
    audits = [('conditioning.json', producer/'audit'/f'{run}_conditioning.json'),
              ('noise.json', producer/'audit'/f'{run}_noise.json'),
              ('router_audit.json', producer/'audit/feedback'/f'{run}.json')]
    for name, remote in audits:
        copy_from(args.producer_host, remote, dest/name)
    admission.update({'video_sha256': before, 'producer_host': args.producer_host,
        'producer_root': args.producer_root, 'producer_video': str(remote_video),
        'config_sha256': hashlib.sha256(config_raw).hexdigest(),
        'history_sha256': hashlib.sha256(history_raw).hexdigest(),
        'cpu_tool_root': OLD_ROOT, 'source_pose_sha256': FROZEN['analysis/pose/old_sam/05_real_megumi_v.pose.json'],
        'source_video_sha256': SOURCE_VIDEO_SHA, 'formal_case_retained': True,
        'hardware_anchor_required': True, 'interpretation': 'Compare .9 R7 normal native after actual condition/noise pairing, full RGB and common snapshot equality. No new final pose if exact; otherwise retain and independently evaluate.'})
    save(dest/'intake_manifest.json', admission)
    return admission, video, dest


def cpu_worker(bundle_path, cpu_dir):
    """Runs on .9 only after explicit parent authorization; one owned lock."""
    cpu_dir = Path(cpu_dir)
    cpu_dir.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        # R2 already holds this lock for its complete extraction/metric worker.
        # Sharing that existing lock requires no modification of its running consumer.
        shared_path = Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
        shared = stack.enter_context(shared_path.open('a'))
        fcntl.flock(shared, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock = stack.enter_context((cpu_dir/'consumer.lock').open('a'))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for rel, wanted in FROZEN.items():
            if digest(Path(OLD_ROOT)/rel) != wanted:
                raise ValueError('Frozen tool/source hash mismatch: ' + rel)
        pose_processes = subprocess.check_output(['ps', '-u', str(os.getuid()), '-o', 'pid=,args='], text=True)
        if any(any(name in line for name in ('pose_probe.py', 'timing_metrics.py')) for line in pose_processes.splitlines()):
            raise RuntimeError('An existing pose extraction or timing metric process is active; do not run concurrently')
        bundle = json.loads(Path(bundle_path).read_text())
        formal_run(bundle['run_id'])
        video = cpu_dir/'raw'/bundle['relative_video']
        if digest(video) != bundle['video_sha256']:
            raise ValueError('CPU input MP4 hash mismatch')
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
            os.environ[name] = '4'
        import cv2
        cv2.setNumThreads(1)
        cap = cv2.VideoCapture(str(video))
        actual = {'frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 'fps': cap.get(cv2.CAP_PROP_FPS),
                  'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), 'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
        cap.release()
        out = cpu_dir/'pilot'
        out.mkdir(exist_ok=True)
        record = dict(bundle, measured_geometry=actual)
        save(out/(bundle['run_id']+'.history_provenance.json'), record)
        if any(abs(actual[k]-bundle['expected_geometry'][k])>1e-6 for k in actual):
            raise ValueError('Formal output geometry failed; retain output and failure')
        if json.loads(Path(SOURCE_POSE).read_text())['video']['sha256'] != SOURCE_VIDEO_SHA:
            raise ValueError('Source pose points to different source video')
        pose_path = out/(video.stem+'.pose.json')
        cached = pose_path.is_file() and json.loads(pose_path.read_text())['video']['sha256'] == bundle['video_sha256']
        if not cached:
            command = [sys.executable, OLD_ROOT+'/scripts/pose_probe.py','--video',str(video),
                       '--output-dir',str(out),'--threads','4']
            for frame in (55,63,86,105): command += ['--overlay-frame',str(frame)]
            with (out/(video.stem+'.extract.log')).open('w') as log:
                subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        for threshold in (0.3,0.5):
            command = [sys.executable, OLD_ROOT+'/scripts/timing_metrics.py','--source',SOURCE_POSE,
                       '--edited',str(pose_path),'--confidence',str(threshold),'--output-dir',str(out)]
            for window in WINDOWS: command += ['--window',window]
            result = subprocess.run(command,capture_output=True,text=True,check=True)
            (out/(video.stem+f'.threshold{threshold}.stdout.jsonl')).write_text(result.stdout)
        if digest(video) != bundle['video_sha256']:
            raise ValueError('Video changed during extraction')
        result = {'run_id':bundle['run_id'],'status':'cpu_complete','video_sha256':digest(video),
                  'source_pose_sha256':FROZEN['analysis/pose/old_sam/05_real_megumi_v.pose.json'],
                  'frozen_tools':FROZEN,'cache_reused':cached,'windows':WINDOWS,'thresholds':[.3,.5],
                  'all_outputs_retained':True,'no_gpu':True}
        save(out/(bundle['run_id']+'.cpu_complete.json'),result)
        print(json.dumps(result),flush=True)


def evaluate(args, run):
    bundle, video, provenance = intake(args,run)
    cpu = PurePosixPath(args.cpu_dir)
    shell(args.cpu_host,['mkdir','-p',str(cpu/'raw'/PurePosixPath(bundle['relative_video']).parent),str(cpu/'bundles'),str(cpu/'pilot')])
    subprocess.run(['scp','-q',str(Path(__file__).resolve()),f'{args.cpu_host}:{cpu}/consumer_r8.py'],check=True)
    subprocess.run(['scp','-q',str(provenance/'intake_manifest.json'),f'{args.cpu_host}:{cpu}/bundles/{run}.json'],check=True)
    subprocess.run(['scp','-q',str(video),f'{args.cpu_host}:{cpu}/raw/{bundle["relative_video"]}'],check=True)
    command = [args.cpu_python,str(cpu/'consumer_r8.py'),'--cpu-worker',str(cpu/'bundles'/f'{run}.json'),'--cpu-dir',str(cpu)]
    print(shell(args.cpu_host,command),flush=True)
    local = Path(args.local_dir)/'pilot'
    local.mkdir(exist_ok=True)
    # Only owned analysis products, never producer outputs/runtime.
    subprocess.run(['scp','-qr',f'{args.cpu_host}:{cpu}/pilot/.',str(local)],check=True)
    measured = json.loads((local/(video.stem+'.pose.json')).read_text())
    if measured['video']['sha256'] != bundle['video_sha256']:
        raise ValueError('Downloaded pose does not bind the raw video')
    manifest = dict(bundle, status='archived_and_measured', files=[])
    for item in sorted(local.glob(video.stem+'.*')):
        manifest['files'].append({'path':str(item),'sha256':digest(item),'bytes':item.stat().st_size})
    save(provenance/'archive_manifest.json',manifest)
    return manifest


def self_test():
    g={'1':{'class_type':'H3FeedbackRouter','inputs':{'run_id':'r8_s05_normal_feedback'}},
       '2':{'class_type':'H3EventAuditReference','inputs':{'width':1312,'height':736,'length':141}},
       '3':{'class_type':'CreateVideo','inputs':{'fps':24}},'4':{'class_type':'SaveVideo','inputs':{}}}
    h={'status':{'status_str':'success','completed':True},'prompt':[0,'actual-prompt',g],
       'outputs':{'4':{'images':[{'type':'output','filename':'actual_00003_.mp4','subfolder':''}]}}}
    assert validate_history('r8_s05_normal_feedback',h,g)['relative_video']=='actual_00003_.mp4'
    rejects=0
    for mutate in ('benchmark','not_success','path_escape','graph_mismatch','missing_output'):
        x=json.loads(json.dumps(h));c=json.loads(json.dumps(g));name='r8_s05_normal_feedback'
        if mutate=='benchmark':name='r8_s05_normal_feedback_bench2'
        elif mutate=='not_success':x['status']['completed']=False
        elif mutate=='path_escape':x['outputs']['4']['images'][0]['filename']='../escape.mp4'
        elif mutate=='graph_mismatch':c['3']['inputs']['fps']=30
        else:x['outputs']={}
        try:validate_history(name,x,c)
        except ValueError:rejects+=1
    assert rejects==5
    print(json.dumps({'self_test_passed':True,'exact_history_valid':1,'invalid_cases_rejected':rejects,'network_or_gpu_used':False}))



def transport_error(local, run, exc):
    record={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'run_id':run,
            'status':'retryable_transport_error','error':repr(exc),'method_failure':False}
    with (local/'transport_errors.jsonl').open('a') as log:log.write(json.dumps(record)+'\n')
    print(json.dumps(record),flush=True)


def cached_complete(local, run, intake_only=False):
    folder=local/'pilot'/(run+'_provenance')
    path=folder/('intake_manifest.json' if intake_only else 'archive_manifest.json')
    if not path.is_file():return False
    data=json.loads(path.read_text());video=local/'raw'/data['relative_video']
    if data['run_id']!=run or not video.is_file() or digest(video)!=data['video_sha256']:return False
    if intake_only:return True
    if data.get('status')!='archived_and_measured':return False
    pose=local/'pilot'/(video.stem+'.pose.json')
    return pose.is_file() and json.loads(pose.read_text())['video']['sha256']==data['video_sha256']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--local-dir',default='/Users/researcher/DevProjects/h3-timing-normal-feedback-r8-20261016/analysis/pose')
    p.add_argument('--producer-host',default='H3_SERVER_A')
    p.add_argument('--producer-root',default='/data5/researcher/h3_runs/timing_normal_feedback_r8_20261016')
    p.add_argument('--cpu-host',default='H3_SERVER_A')
    p.add_argument('--cpu-dir',default='/data5/researcher/h3_runs/timing_normal_feedback_r8_20261016/analysis/pose')
    p.add_argument('--cpu-python',default='/home/researcher/miniconda3/envs/comfyui/bin/python')
    p.add_argument('--run-id',action='append',default=[])
    p.add_argument('--intake-only',action='store_true',help='Download actual success and provenance only; never starts CPU evaluation')
    p.add_argument('--wait',action='store_true',help='Explicitly authorized monitoring; poll61s, never used at prepare stage')
    p.add_argument('--timeout-minutes',type=int,default=180)
    p.add_argument('--cpu-worker')
    p.add_argument('--self-test',action='store_true')
    args=p.parse_args()
    if args.self_test:return self_test()
    if args.cpu_worker:return cpu_worker(args.cpu_worker,args.cpu_dir)
    if not args.run_id:p.error('Explicit formal --run-id required; preparation starts nothing')
    for name in args.run_id:formal_run(name)
    local=Path(args.local_dir);local.mkdir(parents=True,exist_ok=True)
    with (local/'coordinator.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        complete=[run for run in args.run_id if cached_complete(local,run,args.intake_only)];failures={};start=time.monotonic()
        while True:
            for run in args.run_id:
                if run in complete:continue
                ready_code='from pathlib import Path;import sys;print(int(Path(sys.argv[1]).is_file()))'
                history_path=PurePosixPath(args.producer_root)/'logs'/f'{run}_history.json'
                try:
                    ready=shell(args.producer_host,['python3','-c',ready_code,str(history_path)]).strip()=='1'
                except (subprocess.CalledProcessError,OSError) as e:
                    transport_error(local,run,e)
                    continue
                if not ready:continue
                try:
                    if args.intake_only:intake(args,run)
                    else:
                        shared_local=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
                        with shared_local.open('a') as heavy_lock:
                            fcntl.flock(heavy_lock,fcntl.LOCK_EX)
                            evaluate(args,run)
                except Exception as e:
                    if isinstance(e,subprocess.CalledProcessError) and e.returncode==255:
                        transport_error(local,run,e)
                        continue
                    failures[run]={'error':repr(e),'retained':True}
                    save(local/'pilot'/(run+'.failure.json'),failures[run])
                    # Do not classify a failed detector or technical rejection as a successful method.
                complete.append(run)
                save(local/'consumer_state.json',{'requested':args.run_id,'completed':complete,'failures':failures,'producer_host':args.producer_host,'producer_root':args.producer_root,'intake_only':args.intake_only})
            if set(complete)==set(args.run_id):return
            if not args.wait or time.monotonic()-start>args.timeout_minutes*60:
                save(local/'consumer_state.json',{'requested':args.run_id,'completed':complete,'failures':failures,'status':'not_ready_or_timeout','intake_only':args.intake_only})
                return
            time.sleep(61)


if __name__=='__main__':main()
