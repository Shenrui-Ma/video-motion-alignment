import argparse, fcntl, hashlib, json, signal, subprocess, time
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def main():
    p=argparse.ArgumentParser();p.add_argument('--id',required=True);p.add_argument('--source',required=True);p.add_argument('--start',type=int);a=p.parse_args()
    with LOCK.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:print('BUSY');return 75
        signal.alarm(120);started=time.perf_counter()
        dest=ROOT/'inspection'/a.id;dest.mkdir(exist_ok=True)
        source=ROOT/a.source
        probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)]))
        (dest/'original_probe.json').write_text(json.dumps(probe,indent=2)+'\n')
        if a.start is None:
            interval=float(probe['format']['duration'])/24;vf=f'fps=1/{interval},scale=320:-2';prefix='overview';src=source
        else:
            src=dest/f'clip_start{a.start:04d}_141f24.mp4'
            vf=f'fps=24:round=near,trim=start_frame={a.start}:end_frame={a.start+141},setpts=PTS-STARTPTS'
            subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','4','-i',str(source),'-vf',vf,'-filter_threads','4','-an','-c:v','libx264','-preset','fast','-crf','16','-threads','4','-movflags','+faststart',str(src)],check=True,timeout=90)
            interval=6/24;vf='select=not(mod(n\,6)),scale=320:-2';prefix=f'selected_{a.start:04d}'
        subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','4','-i',str(src),'-vf',vf,'-filter_threads','4','-frames:v','24',str(dest/f'{prefix}_%02d.jpg')],check=True,timeout=90)
        frames=sorted(dest.glob(f'{prefix}_[0-9][0-9].jpg'));height=max(Image.open(f).height for f in frames)+24
        canvas=Image.new('RGB',(1280,6*height),'black');draw=ImageDraw.Draw(canvas)
        for i,f in enumerate(frames):
            y=i//4*height;x=i%4*320;canvas.paste(Image.open(f),(x,y+24))
            label=f'{a.id} ~{(i+.5)*interval:.2f}s' if a.start is None else f'{a.id} frame {i*6:03d} | {i*6/24:.2f}s'
            draw.text((x+4,y+5),label,fill='white')
        canvas.save(dest/f'{prefix}.jpg',quality=92)
        r={'id':a.id,'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'start_normalized_24fps_frame':a.start,'seconds':time.perf_counter()-started,'cpu_threads':4,'source_only':True}
        (dest/f'{prefix}_receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));return 0

if __name__=='__main__':raise SystemExit(main())
