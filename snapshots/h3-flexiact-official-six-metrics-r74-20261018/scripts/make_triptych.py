"""Display same-frame full valid sequence and the predefined first-two-second view."""
import argparse,shutil,subprocess
from common import *
def build(inputs,font,output,count):
 labels=['1.参考视频','2.编辑后视频','3.编辑＋时序引导后视频'];filters=[]
 for i,label in enumerate(labels):
  extra=f',drawtext=fontfile={font}:text=角色替换:fontcolor=white:fontsize=23:x=12:y=h-71' if i==0 else ''
  filters.append(f'[{i}:v]trim=start_frame=0:end_frame={count},setpts=PTS-STARTPTS,setsar=1,pad=iw:ih+88:0:0:black,drawtext=fontfile={font}:text={label}:fontcolor=white:fontsize=30:x=(w-text_w)/2:y=h-42{extra}[v{i}]')
 filters.append('[v0][v1][v2]hstack=inputs=3:shortest=1[out]');cmd=[shutil.which('ffmpeg'),'-v','error','-nostdin','-n']
 for path in inputs:cmd+=['-threads','2','-i',str(path)]
 return cmd+['-filter_complex',';'.join(filters),'-map','[out]','-an','-vsync','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(output)]
def run(source,font=None):
 verify_runtime()
 incoming=ROOT/'incoming'/source;g=verify_gate(read(incoming/'PAIR_RUNTIME_GATE.json'),source);action=pair_info(source)['motion_source_id'];inputs=[ROOT/'runtime/source_videos'/f'source_{action}_video.mp4',incoming/'native.mp4',incoming/'forced.mp4']
 case=next(c for c in read(ROOT/'configs/producer_scientific_contract.json')['cases'] if c['source_id']==source)
 require(sha(inputs[0])==case['video_sha256'],'presentation reference video changed')
 for m,path in zip(METHODS,inputs[1:]):require(sha(path)==g['runs'][m]['video']['sha256'],'presentation source differs')
 fonts=[Path(font)] if font else [Path('/System/Library/Fonts/PingFang.ttc'),Path('/System/Library/Fonts/STHeiti Light.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')];font=next((f for f in fonts if f.is_file()),None);require(font is not None,'supply Chinese font --font');output=ROOT/'showcase';output.mkdir(exist_ok=True)
 receipts=[]
 for name,count in [('first2seconds',48),('full_valid',147)]:
  dest=output/f'{source}_{name}.mp4';cmd=build(inputs,str(font),dest,count);subprocess.run(cmd,check=True,timeout=240);receipts.append({'video':bound(dest),'physical_frame_interval':[0,count-1],'fps':24,'columns':['reference','native','fixed ON'],'command':cmd})
 save(output/f'{source}_PRESENTATION.json',{'source':source,'input_gate':bound(incoming/'PAIR_RUNTIME_GATE.json'),'videos':receipts});return output
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pair','--source',dest='source',choices=PAIR_KEYS,required=True);p.add_argument('--font');a=p.parse_args()
 with cpu_lock():print(run(a.source,a.font))
