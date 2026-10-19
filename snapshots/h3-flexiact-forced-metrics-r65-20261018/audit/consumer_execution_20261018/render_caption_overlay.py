"""Actual video presentation using a Pillow caption strip when drawtext is absent."""
import argparse
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from common import verify_runtime, verify_gate, read, sha, bound, save, cpu_lock

def render(source):
    verify_runtime()
    intake=ROOT/'incoming'/source
    gate=verify_gate(read(intake/'PAIR_RUNTIME_GATE.json'),source)
    case=next(c for c in read(ROOT/'configs/producer_scientific_contract.json')['cases'] if c['source_id']==source and c['arm']=='native')
    inputs=[ROOT/'inputs'/case['video'],intake/'native.mp4',intake/'forced.mp4']
    assert sha(inputs[0])==case['video_sha256']
    for method,path in zip(('native','forced'),inputs[1:]):
        assert sha(path)==gate['runs'][method]['video']['sha256']
    output=ROOT/'showcase'; output.mkdir(exist_ok=True)
    caption=output/f'{source}_caption.png'
    image=Image.new('RGB',(3456,88),'black'); draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',30)
    small=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',23)
    for i,label in enumerate(['1.参考视频','2.编辑后视频','3.编辑＋时序引导后视频']):
        width=draw.textlength(label,font=font)
        draw.text((1152*i+(1152-width)/2,42),label,font=font,fill='white')
    draw.text((12,10),'角色替换',font=small,fill='white')
    assert not caption.exists(); image.save(caption)
    receipts=[]
    for name,count in [('first2seconds',48),('full_valid',147)]:
        dest=output/f'{source}_{name}.mp4'; assert not dest.exists()
        command=['ffmpeg','-v','error','-nostdin','-n']
        for path in inputs:command+=['-threads','2','-i',str(path)]
        command+=['-framerate','24','-loop','1','-i',str(caption)]
        filters=[f'[{i}:v]trim=start_frame=0:end_frame={count},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(3)]
        filters+=['[v0][v1][v2]hstack=inputs=3:shortest=1[images]', '[images][3:v]vstack=inputs=2:shortest=1[out]']
        command+=['-filter_complex',';'.join(filters),'-map','[out]','-frames:v',str(count),'-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(dest)]
        subprocess.run(command,check=True,timeout=240)
        probe=subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(dest)],text=True)
        import json
        properties=json.loads(probe)['streams'][0]
        assert properties['width']==3456 and properties['height']==856 and properties['avg_frame_rate']=='24/1' and int(properties['nb_read_frames'])==count
        receipts.append({'video':bound(dest),'physical_frame_interval':[0,count-1],'fps':24,'columns':['reference','native','fixed ON'],'command':command,'properties':properties})
    save(output/f'{source}_PRESENTATION.json',{'source':source,'input_gate':bound(intake/'PAIR_RUNTIME_GATE.json'),'videos':receipts,'caption':bound(caption),'renderer':bound(Path(__file__)),'engineering_reason':'Existing ffmpeg lacks drawtext; Pillow supplies only the black caption strip. Actual video frames keep their original geometry and physical timestamps.'})

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--source',choices=['fitness','one_leg'],required=True)
    args=parser.parse_args()
    with cpu_lock():render(args.source)
