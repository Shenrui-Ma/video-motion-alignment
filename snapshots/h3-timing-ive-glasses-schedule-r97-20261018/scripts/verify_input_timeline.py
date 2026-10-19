"""CPU ffprobe of actual source bytes and physical PTS; no float decoder expectations."""
import json,subprocess
from fractions import Fraction
from r97_contract import ROOT,registry,require,sha
from execution_gate import atomic

def inspect(path,count,fps,width=None,height=None):
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=120)
 data=json.loads(result.stdout);stream=data['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in data['frames']]
 require(len(data['streams'])==1 and len(pts)==count and Fraction(stream['avg_frame_rate'])==fps,'source count/fps differs')
 require(all(abs(t-i/fps)<0.000002 for i,t in enumerate(pts)),'source PTS is not the declared zero-origin physical grid')
 if width is not None:require((stream['width'],stream['height'])==(width,height),'source geometry differs')
 return {'file':str(path),'sha256':sha(path),'frames':len(pts),'fps':fps,'first_pts':pts[0],'last_pts':pts[-1],'max_grid_error_seconds':max(abs(t-i/fps) for i,t in enumerate(pts)),'stream':stream}

def main():
 jobs,order=registry();case=jobs[order[0]]['case'];p=json.loads((ROOT/'inputs'/case['provenance']).read_text())
 original=ROOT/'inputs/short_0358_original.mp4';prepared=ROOT/'inputs'/case['video']
 require(sha(original)==p['source_sha256'] and sha(prepared)==p['video_sha256'],'source bytes differ')
 require(p['frames']==107 and p['effective_frame_count']==105 and p['padding_indices']==[105,106],'valid domain changed')
 # Frozen original mapping is nearest25fps input at each24fps output; half-open source duration109/25.
 indices=[min(range(109),key=lambda j:abs(Fraction(j,25)-Fraction(i,24))) for i in range(105)]+[108,108]
 require(p['input_to_original_frame']==indices,'frozen physical frame map differs')
 report={'passed':True,'original':inspect(original,109,25),'prepared':inspect(prepared,107,24,1312,736),'valid_frames':105,'padding':[105,106],'input_to_original_frame':indices,'original_pixels_policy':'Exact inherited R89 MP4/provenance; actual new RGB/cleanVAE/Qwen/conditioning must equal actual R89 fixed at postrun.','GPU_started':False}
 atomic(ROOT/'audit/INPUT_TIMELINE_ACTUAL.json',report);print(json.dumps({'passed':True,'prepared_frames':107,'valid_frames':105}))
if __name__=='__main__':main()
