"""CPU ffprobe of actual source bytes and physical PTS; no float decoder expectations."""
import json,subprocess
from fractions import Fraction
from r94_contract import ROOT,definitions,require,sha
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
  rows.append({'pair_key':pair['pair_key'],'original':inspect(original,49,8),'prepared':inspect(prepared,158,24,1152,768),'valid_frames':147,'official_score_indices':list(range(0,147,3))})
 report={'passed':True,'rows':rows,'float_tensor_policy':'No expected .41 gbrpf32le or VAE tensor hash. Native/forced actual host9 tensors are compared within each pair.','GPU_started':False}
 atomic(ROOT/'audit/INPUT_TIMELINE_ACTUAL.json',report);print(json.dumps({'passed':True,'sources':len(rows),'frames_per_prepared':158,'valid_frames':147}))

if __name__=='__main__':main()
