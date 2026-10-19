"""Extract source-only contact sheets while respecting the shared CPU locks."""
from pathlib import Path
import fcntl
import json
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parent
MAC_LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
REMOTE_LOCK = '/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock'


def main():
    with MAC_LOCK.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('LOCAL_CPU_BUSY')
            return 75
        code = (
            'import fcntl,sys,select; '
            f'f=open({REMOTE_LOCK!r},"a"); '
            'fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); '
            'print("LOCKED",flush=True); select.select([sys.stdin],[],[],40)'
        )
        remote = subprocess.Popen(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
             'H3_SERVER_A', shlex.join(['python3', '-c', code])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            if remote.stdout.readline().strip() != 'LOCKED':
                print('REMOTE_CPU_BUSY')
                return 75
            for source in sorted(ROOT.glob('*/source720.mp4')):
                output = source.parent / 'source_contact_sheet.jpg'
                vf = ("select='not(mod(n,12))',scale=320:180,"
                      'tile=6x5:padding=4:margin=4:color=black')
                subprocess.run(
                    ['/opt/homebrew/bin/ffmpeg', '-nostdin', '-hide_banner',
                     '-loglevel', 'error', '-y', '-threads', '2', '-i', str(source),
                     '-vf', vf, '-frames:v', '1', '-threads', '2',
                     '-filter_threads', '1', str(output)], check=True, timeout=10)
                print(output)
            (ROOT / 'SOURCE_CONTACTS.json').write_text(json.dumps({
                'created_unix': time.time(), 'frame_stride': 12,
                'inputs_only': True, 'generated_results_seen': False,
                'threads': 2, 'locks': 'Mac then remote; source extraction only',
                'grid': '6 columns x 5 rows, row-major frame indices 0,12,...,348; trailing cells black after EOF',
                'label_rendering': 'frame index mapping in this sidecar; local ffmpeg lacks drawtext'
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
