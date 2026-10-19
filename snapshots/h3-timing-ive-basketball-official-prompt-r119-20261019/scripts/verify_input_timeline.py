"""CPU ffprobe of actual source bytes and physical PTS; no float decoder expectations."""
import json,subprocess
from fractions import Fraction
from r119_contract import ROOT,definitions,require,sha
from execution_gate import atomic

def inspect(path,count,fps,width=None,height=None):
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=120)
 data=json.loads(result.stdout);stream=data['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in data['frames']]
 require(len(data['streams'])==1 and len(pts)==count and Fraction(stream['avg_frame_rate'])==fps,'source count/fps differs')
 require(all(abs(t-i/fps)<0.000002 for i,t in enumerate(pts)),'source PTS is not the declared zero-origin physical grid')
 if width is not None:require((stream['width'],stream['height'])==(width,height),'source geometry differs')
 return {'file':str(path),'sha256':sha(path),'frames':len(pts),'fps':fps,'first_pts':pts[0],'last_pts':pts[-1],'max_grid_error_seconds':max(abs(t-i/fps) for i,t in enumerate(pts)),'stream':stream}

def main():
 rows=[]
 for pair in definitions():
  source=pair['source'];original=ROOT/'inputs'/source['original'];prepared=ROOT/'inputs'/source['video']
  require(sha(original)==source['original_sha256'] and sha(prepared)==source['video_sha256'],'source bytes differ')
  rows.append({'pair_key':pair['pair_key'],'original':inspect(original,109,25),'prepared':inspect(prepared,107,24,1312,736),'valid_frames':105,'evaluation_indices':list(range(105))})
 report={'passed':True,'rows':rows,'float_tensor_policy':'Actual prepared RGB and clean video reference reuse R110 input; prompt-conditioned embedding may change.','GPU_started':False}
 atomic(ROOT/'audit/INPUT_TIMELINE_ACTUAL.json',report);print(json.dumps({'passed':True,'sources':len(rows),'frames_per_prepared':107,'valid_frames':105}))

if __name__=='__main__':main()
