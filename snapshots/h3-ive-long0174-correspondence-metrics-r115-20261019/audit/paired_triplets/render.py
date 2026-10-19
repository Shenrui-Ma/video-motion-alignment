from pathlib import Path
import sys,json,subprocess,argparse
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from common import verify_collection,bound,save,sha
from media import make_comparison,FFMPEG,FFPROBE,info,check_time
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--frame',type=int,required=True);args=a.parse_args();assert 0<=args.frame<145
 incoming=ROOT/'incoming/long_0174';receipt=verify_collection(incoming);out=Path(__file__).parent
 rows={}
 for role,label in [('fixed_one_bin','3.原位置时序引导'),('matched_one_bin','3.匹配位置时序引导')]:
  dest=out/role;dest.mkdir(exist_ok=True)
  if not (dest/'comparison.mp4').exists():make_comparison([incoming/(x+'.mp4')for x in ['source','native',role]],dest,('1.参考视频','2.普通编辑',label))
  check_time(info(dest/'comparison.mp4'),145,3840,808)
  still=dest/('same_frame_%03d.png'%args.frame)
  if not still.exists():subprocess.run([FFMPEG,'-v','error','-i',str(dest/'comparison.mp4'),'-vf',fr'select=eq(n\,{args.frame})','-frames:v','1',str(still)],check=True)
  rows[role]={'video':bound(dest/'comparison.mp4'),'still':bound(still),'still_frame':args.frame,'roles':['source','native',role],'valid_frames':145,'fps':24,'crop_xywh':[16,8,1280,720],'caption':label,'inputs':{x:bound(incoming/(x+'.mp4'))for x in ['source','native',role]}}
 manifest=out/('MEDIA_%03d.json'%args.frame);save(manifest,{'collection':bound(incoming/'COLLECTION.json'),'pair_gate':bound(incoming/'PAIR_RUNTIME_GATE.json'),'versions':rows,'primary':'matched_one_bin','same_physical_frame':True})
 print(manifest)
