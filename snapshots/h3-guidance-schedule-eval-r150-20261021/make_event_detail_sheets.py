"""CPU original-resolution spatial crops for reviewing existing event definitions."""
import argparse
import subprocess
from PIL import Image, ImageDraw, ImageFont
from common import ROOT, FFMPEG, FONT, bound, read, write, verify_record, require, resolve_controls


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--schedule', required=True)
    p.add_argument('--ranges', required=True, help='Inclusive zero-based ranges, e.g. 52:67,80:91')
    p.add_argument('--crop', default='550,320,600,400')
    p.add_argument('--historical-roles', default='source,fixed')
    a = p.parse_args()
    case = resolve_controls(next(x for x in read(ROOT / 'EVALUATION_MANIFEST.json')['cases'] if x['source_id'] == a.case))
    folder = ROOT / 'review' / a.case / a.schedule
    pres = read(folder / 'PRESENTATION.json')
    frames = []
    for pair in a.ranges.split(','):
        start, end = map(int, pair.split(':'))
        require(0 <= start <= end < case['geometry']['valid_frames'], 'Invalid frame domain')
        frames.extend(range(start, end + 1))
    require(frames == sorted(set(frames)), 'Ranges overlap or are not ordered')
    x,y,w,h = map(int, a.crop.split(','))
    require(0 <= x < x+w <= case['geometry']['width'] and 0 <= y < y+h <= case['geometry']['height'], 'Invalid crop')
    roles = a.historical_roles.split(',')
    media = {role: case['media'][role] for role in roles}
    media[a.schedule] = pres['new_video']
    labels = {'source':'参考视频','native':'普通编辑','fixed':'时序引导 7–15',a.schedule:pres['labels'][-1]}
    out = folder / 'event_details'
    require(not out.exists(), 'Preserve existing details')
    out.mkdir()
    selection = '+'.join(f'eq(n,{f})' for f in frames)
    for role, video in media.items():
        verify_record(video)
        sub = out / role
        sub.mkdir()
        subprocess.run([FFMPEG,'-v','error','-nostdin','-n','-threads','1','-i',video['file'],
            '-vf',f"select='{selection}',crop={w}:{h}:{x}:{y}",'-fps_mode','passthrough',
            '-start_number','0',str(sub/'selected_%03d.png')],check=True,timeout=90)
    font = ImageFont.truetype(FONT,22)
    sheets=[]
    for start in range(0,len(frames),4):
        group=frames[start:start+4]
        image=Image.new('RGB',(w*len(media),(h+32)*len(group)),'black')
        draw=ImageDraw.Draw(image)
        for row,frame in enumerate(group):
            for col,role in enumerate(media):
                image.paste(Image.open(out/role/f'selected_{start+row:03d}.png'),(col*w,row*(h+32)))
                draw.text((col*w+12,row*(h+32)+h+2),f'{labels[role]} · 帧 {frame:03d}',font=font,fill='white')
        dest=out/f'frames_{group[0]:03d}_{group[-1]:03d}.jpg'
        image.save(dest,quality=95,subsampling=0)
        sheets.append({**bound(dest),'frames':group})
    write(out/'INDEX.json',{'presentation':bound(folder/'PRESENTATION.json'),'sources':media,
        'crop_xywh':[x,y,w,h],'frames':frames,'sheets':sheets,
        'scope':'Original-resolution spatial crop only. Frozen event definitions unchanged; timing measured wherever the same event actually occurs in the valid sequence.'})
    print(out)

if __name__=='__main__':
    main()
