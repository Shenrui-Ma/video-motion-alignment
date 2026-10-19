"""Fixed archived-final frames. Final numerical evaluation remains separate."""
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
                'print("LOCKED",flush=True); select.select([sys.stdin],[],[],55)')
        remote = subprocess.Popen(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
             'H3_SERVER_A', shlex.join(['python3', '-c', code])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            if remote.stdout.readline().strip() != 'LOCKED':
                print('REMOTE_CPU_BUSY')
                return 75
            from PIL import Image, ImageDraw, ImageFont
            base=Path('/Users/researcher/DevProjects/h3-timing-spatial-r3-20261016')
            videos={
                'SOURCE':base/'inputs/05_real_megumi_v.mp4',
                'NATIVE':base/'analysis/pose/raw/r3_s05_native_00001_.mp4',
                'FIXED FULL':base/'analysis/pose/raw/r3_s05_full_6to14_00001_.mp4',
                'AUTO':HERE.parent/'postrun/captured/r27_s05_bad1311_auto/output/r27_s05_bad1311_auto_00001_.mp4'}
            for name,video in videos.items():
                folder=HERE/name.replace(' ','_');folder.mkdir(exist_ok=True)
                subprocess.run(['/opt/homebrew/bin/ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-threads','2','-i',str(video),'-vf','select=eq(n\\,55)+eq(n\\,86)+eq(n\\,105),scale=656:368','-vsync','0','-frames:v','3','-threads','2','-filter_threads','1',str(folder/'frame%02d.png')],check=True,timeout=10)
            font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',20)
            for k,frame in enumerate([55,86,105],1):
                board=Image.new('RGB',(1312,800),'black');draw=ImageDraw.Draw(board)
                for j,name in enumerate(videos):
                    x=(j%2)*656;y=(j//2)*400
                    board.paste(Image.open(HERE/name.replace(' ','_')/f'frame{k:02d}.png'),(x,y))
                    draw.text((x+10,y+371),f'{name} | frame {frame} | {frame/24:.3f}s',fill='white',font=font)
                board.save(HERE/f'comparison_{frame:03d}.png')
            (HERE / 'EXTRACTION.json').write_text(json.dumps({
                'unix': time.time(), 'frames': [55,86,105],
                'same_frames_as_frozen_R27_postrun': True,
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
