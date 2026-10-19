"""CPU ffprobe of actual source bytes and physical PTS; no float decoder expectations."""
import json,subprocess
from fractions import Fraction
from r115_contract import ROOT,registry,require,sha
from execution_gate import atomic

def inspect(path,count,fps,width=None,height=None):
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=120)
 data=json.loads(result.stdout);stream=data['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in data['frames']]
 require(len(data['streams'])==1 and len(pts)==count and Fraction(stream['avg_frame_rate'])==fps,'source count/fps differs')
 require(all(abs(t-i/fps)<0.000002 for i,t in enumerate(pts)),'source PTS is not the declared zero-origin physical grid')
 if width is not None:require((stream['width'],stream['height'])==(width,height),'source geometry differs')
 return {'file':str(path),'sha256':sha(path),'frames':len(pts),'fps':fps,'first_pts':pts[0],'last_pts':pts[-1],'max_grid_error_seconds':max(abs(t-i/fps) for i,t in enumerate(pts)),'stream':stream}

def main():
 jobs,order=registry();reports=[]
 for run in order:
  case=jobs[run]['case'];p=json.loads((ROOT/'inputs'/case['provenance']).read_text());prepared=ROOT/'inputs'/case['video']
  require(sha(prepared)==p['video_sha256']==case['video_sha256'],'prepared source bytes differ')
  require(p['frames']==158 and p['effective_frame_count']==case['valid_frame_count'],'valid domain changed')
  require(p['padding_indices']==list(range(case['valid_frame_count'],158)),'padding domain changed')
  reports.append({'source_id':case['source_id'],'prepared':inspect(prepared,158,24,1312,736),'valid_frames':case['valid_frame_count'],'padding':p['padding_indices'],'input_to_original_frame':p['input_to_original_frame'],'provenance_sha256':sha(ROOT/'inputs'/case['provenance'])})
 report={'passed':True,'sources':reports,'original_pixels_policy':'Inherited actual parent MP4/provenance exact bytes; new arms must share pre-DiT conditioning. Historical Native environment is recorded separately.','GPU_started':False}
 atomic(ROOT/'audit/INPUT_TIMELINE_ACTUAL.json',report);print(json.dumps({'passed':True,'sources':len(reports)}))
if __name__=='__main__':main()
