"""Download two public source-only candidates and render contact sheets."""
from pathlib import Path
import hashlib, io, json, subprocess, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT.parents[1]
REV = '1e6cb655c0a537f6093edcf18e2607fb03e76734'
IDS = ['long_0035', 'long_0115']


def save(name, value):
    (ROOT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def main():
    metadata=PROJECTS/'h3-timing-ive-generic-retention-r122-20261020/configs/source_selection/ivebenchdb_prompt_long.json'
    tasks=[r for r in json.loads(metadata.read_text()) if r['src_video_name'][:-4] in IDS]
    save('METADATA_PREFILTER.json', {'source_only':True, 'generated_outputs_seen':False, 'ids':IDS, 'tasks':tasks, 'created_unix':time.time(), 'rationale':'Screen for removable subject attributes or contact-surface color edits with visible discrete actions.'})
    request=urllib.request.Request(f'https://huggingface.co/api/datasets/Coraxor/IVEBench/paths-info/{REV}',data=json.dumps({'paths':[f'ivebenchdb_mp4_long/{s}.mp4' for s in IDS],'expand':True}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=90) as response:info=json.load(response)
    save('OFFICIAL_FILES_INFO.json',info)
    (ROOT/'sources').mkdir(exist_ok=True)
    rows=[]
    for entry in info:
        sid=Path(entry['path']).stem;path=ROOT/'sources'/f'{sid}.mp4'
        url=f'https://huggingface.co/datasets/Coraxor/IVEBench/resolve/{REV}/{entry["path"]}'
        if not path.exists():
            temp=path.with_suffix('.partial')
            with urllib.request.urlopen(url,timeout=120) as response,temp.open('wb') as output:
                while block:=response.read(1024*1024):output.write(block)
            assert hashlib.sha256(temp.read_bytes()).hexdigest()==entry['lfs']['oid']
            temp.replace(path)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['lfs']['oid']
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',str(path)]))
        frames=probe['frames'];stream=probe['streams'][0];indices=sorted({round(i*(len(frames)-1)/23) for i in range(24)})
        vf='select='+'+'.join(f'eq(n\\,{i})' for i in indices)+',scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2:black,tile=4x6'
        raw=subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(path),'-vf',vf,'-fps_mode','vfr','-frames:v','1','-threads','1','-f','image2pipe','-c:v','png','pipe:1'])
        tiled=Image.open(io.BytesIO(raw)).convert('RGB');image=Image.new('RGB',(1536,1500),'black');draw=ImageDraw.Draw(image);font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',16)
        for j,index in enumerate(indices):
            x=j%4*384;y=j//4*250;image.paste(tiled.crop((x,j//4*216,x+384,j//4*216+216)),(x,y));pts=frames[index]['best_effort_timestamp_time'];draw.text((x+5,y+220),f'{sid} f{index} {float(pts):.3f}s',font=font,fill='white')
        contact=ROOT/f'{sid}_contact.jpg';image.save(contact,quality=89)
        rows.append({'source_id':sid,'source_path':str(path),'sha256':entry['lfs']['oid'],'url':url,'frames':len(frames),'fps':stream['avg_frame_rate'],'contact':str(contact),'contact_sha256':hashlib.sha256(contact.read_bytes()).hexdigest(),'sampled_frame_indices':indices})
        save('CONTACTS.json',rows)
    print(json.dumps(rows,ensure_ascii=False))


if __name__=='__main__':main()
