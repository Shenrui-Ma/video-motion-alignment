"""CPU-only detail crops of frozen event neighborhoods; does not modify annotations."""
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont
from common import ROOT, FFMPEG, FONT, bound, read, write, verify_record

folder = ROOT / 'review/short_0252/early'
case = next(x for x in read(ROOT / 'EVALUATION_MANIFEST.json')['cases'] if x['source_id'] == 'short_0252')
media = {k: case['media'][k] for k in ('source','fixed')}
media['early'] = bound(ROOT / 'actual/short_0252/early/video.mp4')
frames = list(range(36, 52)) + list(range(66, 78))
groups = [frames[i:i+4] for i in range(0, len(frames), 4)]
out = folder / 'event_details'
out.mkdir(exist_ok=True)
records = []
for role, video in media.items():
    verify_record(video)
    sub = out / role
    sub.mkdir(exist_ok=True)
    command = [FFMPEG, '-v','error','-nostdin','-n','-threads','1','-i',video['file'],
       '-vf', "select='between(n,36,51)+between(n,66,77)',crop=600:400:550:320", '-fps_mode','passthrough',
       '-start_number','0', str(sub / 'selected_%03d.png')]
    subprocess.run(command,check=True)
font = ImageFont.truetype(FONT, 22)
labels = ['参考视频', '时序引导 7–15', '时序引导 早段 1–9']
for group in groups:
    sheet = Image.new('RGB',(1800,432 * len(group)), 'black')
    d = ImageDraw.Draw(sheet)
    for row, f in enumerate(group):
        for col,role in enumerate(media):
            im = Image.open(out / role / f'selected_{frames.index(f):03d}.png')
            sheet.paste(im,(col*600,row*432))
            d.text((col*600+12,row*432+402),f'{labels[col]} · 帧 {f:03d}',font=font,fill='white')
    p = out / f'frames_{group[0]:03d}_{group[-1]:03d}.jpg'
    sheet.save(p,quality=95,subsampling=0)
    records.append({**bound(p),'frames':group})
write(out / 'INDEX.json', {'scope':'Frozen event neighborhoods, original-resolution spatial crop only',
  'original_crop_xywh':[550,320,600,400], 'frame_indexing':'zero-based original video frames',
  'sources':media,'sheets':records,'script':bound(Path(__file__))})
print(out)
