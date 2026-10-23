"""Export the requested historical source/native/alpha=.25 video comparisons."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
from PIL import Image,ImageDraw,ImageFont

E=Path(__file__).resolve().parents[1]
manifest=json.loads((E/'metrics/manifest.json').read_text())
out=Path('/workspace/research-user/Downloads')
records=[]
with tempfile.TemporaryDirectory(prefix='h3-triplets-') as tmp:
    tmp=Path(tmp)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',32)
    caption=Image.new('RGB',(2880,64),'black');draw=ImageDraw.Draw(caption)
    for i,label in enumerate(['参考视频','Baseline','α = 0.25']):
        box=draw.textbbox((0,0),label,font=font)
        draw.text((i*960+(960-(box[2]-box[0]))/2,14-box[1]),label,font=font,fill='white')
    caption.save(tmp/'caption.png')
    for sid,name in [('short_0252','机舱氧气罩'),('short_0358','饮酒男子')]:
        inputs=[];hashes=[]
        for method in ['source','native','global_weak']:
            j=next(j for j in manifest['jobs'] if j['task_id']==sid and j['method']==method)
            path=tmp/(sid+'_'+method+'.mp4')
            subprocess.run(['scp','-q','H3_HOST_CONFIGURE_LOCALLY:'+j['video'],str(path)],check=True,timeout=180)
            digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==j['sha256']
            inputs.extend(['-i',str(path)]);hashes.append(digest)
        n=j['valid_frames'];fps=j['fps'];x,y,w,h=j['crop_xywh']
        filters=[]
        for i in range(3):
            filters.append(f'[{i}:v]trim=end_frame={n},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},scale=960:540:flags=lanczos,setsar=1[v{i}]')
        filters+=['[v0][v1][v2]hstack=inputs=3[top]','[top][3:v]vstack=inputs=2:shortest=1[out]']
        target=out/f'H3_{name}_参考视频_Baseline_Alpha0.25_三列对比.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-threads','2',*inputs,'-loop','1','-framerate',str(fps),'-i',str(tmp/'caption.png'),'-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map','[out]','-an','-frames:v',str(n),'-r',str(fps),'-c:v','libx264','-threads','4','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True,timeout=180)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate,duration','-of','json',str(target)]))['streams'][0]
        assert probe['width']==2880 and probe['height']==604 and int(probe['nb_frames'])==n
        records.append({'task_id':sid,'output':str(target),'input_sha256':hashes,'probe':probe,'bytes':target.stat().st_size,'captions':['参考视频','Baseline','α = 0.25']})
        print(json.dumps(records[-1],ensure_ascii=False),flush=True)
(E/'prompt_format_five/requested_triplets_export.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
