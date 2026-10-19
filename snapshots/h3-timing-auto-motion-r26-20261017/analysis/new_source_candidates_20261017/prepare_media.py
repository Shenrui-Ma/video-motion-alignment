import argparse,fcntl,hashlib,json,os,signal,subprocess,time
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')

def run(args):
    started=time.perf_counter();dest=ROOT/'inspection'/args.id;dest.mkdir(parents=True,exist_ok=True)
    source=ROOT/'previews'/f'{args.id}_720.mp4' if args.phase=='overview' else ROOT/'originals'/f'mixkit_{args.id}_1080.mp4'
    probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)]))
    (dest/('probe.json' if args.phase=='overview' else 'fullhd_probe.json')).write_text(json.dumps(probe,indent=2)+'\n')
    if args.phase=='overview':
        duration=float(probe['format']['duration']);interval=duration/24
        subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','4','-i',str(source),'-vf',f'fps=1/{interval},scale=320:-2','-filter_threads','4','-frames:v','24',str(dest/'frame_%02d.jpg')],check=True,timeout=60)
        frames=sorted(dest.glob('frame_*.jpg'));cell_h=max(Image.open(f).height for f in frames)+24
        canvas=Image.new('RGB',(4*320,6*cell_h),'black');draw=ImageDraw.Draw(canvas)
        for i,f in enumerate(frames):
            im=Image.open(f);x=(i%4)*320;y=(i//4)*cell_h;canvas.paste(im,(x,y+24));draw.text((x+4,y+5),f'{args.id} ~{(i+.5)*interval:.2f}s',fill='white')
        canvas.save(dest/'overview.jpg',quality=92)
    else:
        out=dest/f'clip_start{args.start:04d}_141f24.mp4'
        subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','4','-i',str(source),'-vf',f'fps=24:round=near,trim=start_frame={args.start}:end_frame={args.start+141},setpts=PTS-STARTPTS','-filter_threads','4','-an','-c:v','libx264','-preset','fast','-crf','16','-threads','4','-movflags','+faststart',str(out)],check=True,timeout=60)
        subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','4','-i',str(out),'-vf','fps=4,scale=320:-2','-filter_threads','4','-frames:v','24',str(dest/'selected_%02d.jpg')],check=True,timeout=60)
        frames=sorted(dest.glob('selected_*.jpg'));cell_h=max(Image.open(f).height for f in frames)+24
        canvas=Image.new('RGB',(4*320,6*cell_h),'black');draw=ImageDraw.Draw(canvas)
        for i,f in enumerate(frames):
            im=Image.open(f);x=(i%4)*320;y=(i//4)*cell_h;canvas.paste(im,(x,y+24));draw.text((x+4,y+5),f'{args.id} clip ~{(i+.5)/4:.2f}s',fill='white')
        canvas.save(dest/'selected.jpg',quality=92)
    result={'phase':args.phase,'id':args.id,'seconds':time.perf_counter()-started,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'cpu_threads':4}
    (dest/f'{args.phase}_receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['overview','clip']);p.add_argument('--id',required=True);p.add_argument('--start',type=int,default=0);args=p.parse_args()
    with LOCK.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:print('BUSY');raise SystemExit(75)
        signal.alarm(120);run(args)
