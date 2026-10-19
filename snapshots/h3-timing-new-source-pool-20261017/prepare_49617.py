"""Prepare the source-only held-out clip selected before any generated outcome."""
import fcntl
import hashlib
import json
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = ROOT / '49617'
MAC_LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
REMOTE_LOCK = '/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = CASE / 'source720.mp4'
    assert sha(source) == '732df115d60c9d2a7f69866d0ceaeca2a4572202faa925588856c19fd5dbc7d5'
    selected = json.loads((CASE / 'SOURCE_EVENTS_PREGEN.json').read_text())
    assert selected['planned_original_frame_interval_inclusive'] == [0, 140]
    output = CASE / 'prepared' / 'source_49617_video.mp4'
    with MAC_LOCK.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('LOCAL_CPU_BUSY')
            return 75
        code = ('import fcntl,sys,select; '
                f'f=open({REMOTE_LOCK!r},"a"); '
                'fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); '
                'print("LOCKED",flush=True); select.select([sys.stdin],[],[],40)')
        remote = subprocess.Popen(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
             'H3_SERVER_A', shlex.join(['python3', '-c', code])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            if remote.stdout.readline().strip() != 'LOCKED':
                print('REMOTE_CPU_BUSY')
                return 75
            assert not output.exists(), 'Prepared clip already exists; inspect provenance before replacing.'
            output.parent.mkdir(exist_ok=True)
            command = ['/opt/homebrew/bin/ffmpeg', '-nostdin', '-hide_banner',
                       '-loglevel', 'error', '-threads', '2', '-i', str(source),
                       '-vf', 'trim=start_frame=0:end_frame=141,settb=1/24,setpts=N,scale=1312:736:flags=lanczos,setsar=1',
                       '-an', '-r', '24', '-fps_mode', 'cfr', '-c:v', 'libx264',
                       '-crf', '18', '-preset', 'fast', '-threads', '2',
                       '-filter_threads', '1', '-pix_fmt', 'yuv420p',
                       '-movflags', '+faststart', str(output)]
            subprocess.run(command, check=True, timeout=30)
            probe = json.loads(subprocess.check_output([
                '/opt/homebrew/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_streams', '-show_frames', '-show_entries',
                'stream=width,height,nb_frames,r_frame_rate,avg_frame_rate,time_base,duration:frame=best_effort_timestamp_time',
                '-of', 'json', str(output)], timeout=5))
            stream = probe['streams'][0]
            assert [stream['width'], stream['height'], stream['nb_frames']] == [1312, 736, '141']
            assert stream['r_frame_rate'] == stream['avg_frame_rate'] == '24/1'
            assert len(probe['frames']) == 141
            assert all(abs(float(f['best_effort_timestamp_time']) - i / 24) < 1e-6
                       for i, f in enumerate(probe['frames']))
            record = {'created_unix': time.time(), 'source_id': '49617',
                      'source_sha256': sha(source), 'prepared_sha256': sha(output),
                      'script_sha256': sha(Path(__file__)),
                      'source_only_selection_sha256': sha(CASE / 'SOURCE_EVENTS_PREGEN.json'),
                      'source_frame_rate': '24000/1001',
                      'original_frame_indices': list(range(141)),
                      'mapping': 'Prepared frame i uses original frame i for i=0..140; timestamps assigned i/24. Original timestamps are i*1001/24000.',
                      'temporal_change': 'The same141 frames are played at24fps rather than23.976fps (0.1% faster). All future comparison arms must use this exact prepared input.',
                      'command': command, 'ffprobe': probe,
                      'generated_results_used_for_selection': False,
                      'control_inputs': 'Source annotations are for evaluation and must not supply intervention windows.'}
            (output.parent / 'source_provenance.json').write_text(json.dumps(record, indent=2) + '\n')
            print(json.dumps({'output': str(output), 'sha256': sha(output), 'frames': 141, 'fps': 24}))
            return 0
        finally:
            remote.stdin.close()
            try:
                remote.wait(timeout=5)
            except subprocess.TimeoutExpired:
                remote.terminate()


if __name__ == '__main__':
    raise SystemExit(main())
