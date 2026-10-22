"""CPU ffprobe of actual source bytes and physical PTS; no float decoder expectations."""
import json,subprocess
from fractions import Fraction
from r123_contract import ROOT,read,require,sha
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
 for source,count,valid in [('short_0358',109,105)]:
  case=next(c for c in read(ROOT/'configs/scientific_contract.json')['cases'] if c['source_id']==source)
  p=read(ROOT/'inputs'/case['provenance']);original=ROOT/'inputs'/case['original_source'];prepared=ROOT/'inputs'/case['video']
  require(sha(original)==p['source_sha256'] and sha(prepared)==p['video_sha256']==case['video_sha256'],'source bytes differ')
  require(p['effective_frame_count']==valid and p['evaluate_indices']==list(range(valid)) and p['padding_indices']==list(range(valid,107)), 'valid/padding time scope differs')
  mapping=p['input_to_original_frame']
  require(len(mapping)==107 and all(0<=v<count for v in mapping) and mapping==sorted(mapping),'source mapping invalid')
  require(p['decoded_pixel_mapping_exact'] is True and all(p['input_frame_md5'][i]==p['original_transformed_frame_md5'][j] for i,j in enumerate(mapping)), 'frozen input pixel mapping differs')
  require(all(abs(t-i/25)<0.000002 for i,t in enumerate(p['original_pts'])) and len(p['original_pts'])==count,'original provenance PTS differs')
  rows.append({'source_id':source,'original':inspect(original,count,25),'prepared':inspect(prepared,107,24,1312,736),'valid_frames':valid,'evaluation_indices':list(range(valid)),'frozen_decoded_pixel_mapping_exact':True})
 report={'passed':True,'rows':rows,'GPU_started':False,'policy':'Each source retains the prepared bytes and valid physical timeline of its parent experiment. Only the minimal task/reference envelope changes the official edit sentence input.'}
 atomic(ROOT/'audit/INPUT_TIMELINE_ACTUAL.json',report);print(json.dumps({'passed':True,'sources':len(rows),'valid_frames':[105]}))

if __name__=='__main__':main()
