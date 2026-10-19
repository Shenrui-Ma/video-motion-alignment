"""Fixed-frame provisional review. Formal batch acceptance remains separate."""
import fcntl
import json
import shlex
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAC_LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
REMOTE_LOCK = '/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock'


def main():
    with MAC_LOCK.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('LOCAL_CPU_BUSY')
            return 75
        code = ('import fcntl,sys,select; '
                f'f=open({REMOTE_LOCK!r},"a"); '
                'fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); '
                'print("LOCKED",flush=True); select.select([sys.stdin],[],[],35)')
        remote = subprocess.Popen(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
             'H3_SERVER_A', shlex.join(['python3', '-c', code])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            if remote.stdout.readline().strip() != 'LOCKED':
                print('REMOTE_CPU_BUSY')
                return 75
            video = HERE / 'r29_source_40372_seed2026101701_global_full_6to14_00001_.mp4'
            for frame in (0, 35, 70, 105, 140):
                subprocess.run(
                    ['/opt/homebrew/bin/ffmpeg', '-nostdin', '-hide_banner',
                     '-loglevel', 'error', '-y', '-threads', '2', '-i', str(video),
                     '-vf', f'select=eq(n\\,{frame})', '-frames:v', '1',
                     '-threads', '2', '-filter_threads', '1',
                     str(HERE / f'frame{frame:03d}.png')], check=True, timeout=6)
            (HERE / 'EXTRACTION.json').write_text(json.dumps({
                'unix': time.time(), 'frames': [0, 35, 70, 105, 140],
                'same_frames_as_frozen_R29_postrun': True,
                'scope': 'provisional visual review only; no pose/effect conclusion',
                'cpu_threads': 2, 'locks': 'Mac then remote, nonblocking'
            }, indent=2) + '\n')
            return 0
        finally:
            remote.stdin.close()
            try:
                remote.wait(timeout=5)
            except subprocess.TimeoutExpired:
                remote.terminate()


if __name__ == '__main__':
    raise SystemExit(main())
