"""Fixed-index inspection of existing videos. No inference or temporal alignment."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
SOURCE='short_0135'
parser=argparse.ArgumentParser()
parser.add_argument('--pair',action='store_true')
args=parser.parse_args()
names=['source']+(['native','forced'] if args.pair else [])
if args.pair:
    ready=json.loads((ROOT/'prepared'/SOURCE/'READY.json').read_text())
    assert ready['passed'] is True
frames=list(range(0,112,4))
if frames[-1]!=111:frames.append(111)
ledger=[]
loaded={}
for name in names:
    path=ROOT/'prepared'/SOURCE/(name+'_score.mp4')
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(path)]))
    pts=[float(x['best_effort_timestamp_time']) for x in info['frames']]
    assert len(pts)==112 and all(abs(t-i/24)<1e-6 for i,t in enumerate(pts))
    expression='+'.join(f'eq(n\\,{i})' for i in frames)
    raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),
        '-vf','select='+expression+',scale=640:360:flags=lanczos','-fps_mode','vfr',
        '-pix_fmt','rgb24','-f','rawvideo','-'])
    size=640*360*3
    assert len(raw)==len(frames)*size
    loaded[name]=[Image.frombytes('RGB',(640,360),raw[i*size:(i+1)*size]) for i in range(len(frames))]
    ledger.append(dict(name=name,file=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                       frames=frames,pts=pts))
for page,start in enumerate(range(0,len(frames),7)):
    indices=list(range(start,min(start+7,len(frames))))
    sheet=Image.new('RGB',(640*len(names),390*len(indices)))
    draw=ImageDraw.Draw(sheet)
    for row,i in enumerate(indices):
        for col,name in enumerate(names):
            sheet.paste(loaded[name][i],(col*640,row*390))
            draw.text((col*640+8,row*390+365),f'{name} | frame {frames[i]:03d} | {frames[i]/24:.3f}s',fill='white')
    sheet.save(OUT/(('pair' if args.pair else 'source')+f'_page{page+1:02d}.jpg'),quality=95)
(OUT/(('PAIR' if args.pair else 'SOURCE')+'_FIXED_FRAMES.json')).write_text(json.dumps(ledger,indent=2)+'\n')
print(json.dumps(dict(names=names,frames=frames,pages=(len(frames)+6)//7)))
