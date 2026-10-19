"""CPU ffprobe of actual source bytes and physical PTS; no float decoder expectations."""
import json,subprocess
from fractions import Fraction
from r101_contract import ROOT,registry,require,sha
from execution_gate import atomic

def inspect(path,count,fps,width=None,height=None):
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=120)
 data=json.loads(result.stdout);stream=data['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in data['frames']]
 require(len(data['streams'])==1 and len(pts)==count and Fraction(stream['avg_frame_rate'])==fps,'source count/fps differs')
 require(all(abs(t-i/fps)<0.000002 for i,t in enumerate(pts)),'source PTS is not the declared zero-origin physical grid')
 if width is not None:require((stream['width'],stream['height'])==(width,height),'source geometry differs')
 return {'file':str(path),'sha256':sha(path),'frames':len(pts),'fps':fps,'first_pts':pts[0],'last_pts':pts[-1],'max_grid_error_seconds':max(abs(t-i/fps) for i,t in enumerate(pts)),'stream':stream}

def main():
 from r101_contract import read
 jobs,order=registry();case=jobs[order[0]]['case'];source=read(ROOT/'design/ORIGINAL_SOURCE.json')
 original=ROOT/'inputs'/source['original'];prepared=ROOT/'inputs'/case['video']
 require(sha(original)==source['original_sha256'] and sha(prepared)==case['video_sha256'],'original/prepared input changed')
 p=read(ROOT/'inputs'/case['provenance']);require(p['frames']==158 and p['valid_frame_count']==147,'physical support differs')
 require(p['input_to_original']==[i//3 for i in range(147)]+[48]*11,'original8fps repeat3 mapping differs')
 report={'passed':True,'original':inspect(original,49,8),'prepared':inspect(prepared,158,24,1152,768),'valid_frames':147,'score_indices':list(range(0,147,3)),'GPU_started':False}
 atomic(ROOT/'audit/INPUT_TIMELINE_ACTUAL.json',report);print(json.dumps({'passed':True,'sources':1}))
if __name__=='__main__':main()
