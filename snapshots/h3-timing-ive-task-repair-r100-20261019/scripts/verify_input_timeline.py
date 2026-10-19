"""Actual CPU media PTS verification; no cross-host float tensor hash expectation."""
import json,subprocess
from fractions import Fraction
from r100_contract import ROOT,read,require,sha,SOURCES,SOURCE_LENGTHS
from input_contract import clip_nearest_map,clip_valid_count
from execution_gate import atomic

def probe(path):
 p=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,time_base,start_pts,duration_ts:frame=best_effort_timestamp','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=120)
 d=json.loads(p.stdout);require(len(d['streams'])==1,'ambiguous video stream');s=d['streams'][0];tb=Fraction(s['time_base']);pts=[Fraction(x['best_effort_timestamp'])*tb for x in d['frames']]
 return s,pts

def verify_source(root,source,row):
 prepared=root/'inputs'/(source+'_video.mp4');original=root/'inputs'/(source+'_original.mp4');provenance=read(root/'inputs'/(source+'_provenance.json'))
 require(sha(original)==row['source']['sha256'] and sha(prepared)==provenance['video_sha256'],'source file bytes differ')
 orig,pts=probe(original);stream,newpts=probe(prepared);total,valid=SOURCE_LENGTHS[source]
 expected=[Fraction(x) for x in row['source']['actual_pts_rational']]
 require(pts==expected,'original physical time changed')
 require(len(newpts)==total and newpts==[Fraction(i,24) for i in range(total)],'prepared zero-origin24fps grid differs')
 require((stream['width'],stream['height'],Fraction(stream['avg_frame_rate']))==(1312,736,Fraction(24)),'prepared geometry/fps differs')
 clip=row['clip'];a=clip['start_frame'];b=clip['end_frame_inclusive'];start=Fraction(clip['start_pts_rational']);end=Fraction(clip['end_exclusive_rational'])
 require(pts[a]==start and pts[b]==Fraction(clip['end_pts_rational_inclusive']),'clip endpoint PTS differs')
 actual_end=pts[b+1] if b+1<len(pts) else (int(orig['start_pts'])+int(orig['duration_ts']))*Fraction(orig['time_base'])
 require(actual_end==end,'half-open clip endpoint differs from next original frame or actual stream end')
 require(valid==clip_valid_count(start,end),'valid timestamp count differs')
 require(start+Fraction(valid-1,24)<end<=start+Fraction(valid,24),'valid/padding time boundary differs')
 mapping=clip_nearest_map(pts,a,b,valid);require(mapping+[b]*(total-valid)==provenance['input_to_original_frame'],'nearest physical mapping differs')
 require(mapping[0]==a and mapping[-1]==b,'clip first/last frame omitted')
 require(provenance['evaluate_indices']==list(range(valid)) and provenance['padding_indices']==list(range(valid,total)),'evaluation includes padding')
 return {'source_id':source,'scope':'IVEBench source clip exploration','original_sha256':sha(original),'prepared_sha256':sha(prepared),'original_frames':len(pts),'prepared_frames':total,'valid_frames':valid,'clip':clip,'original_pts_rational':[str(x) for x in pts],'prepared_first_pts':str(newpts[0]),'prepared_last_pts':str(newpts[-1]),'valid_last_relative_pts':str(Fraction(valid-1,24)),'max_selected_time_distance_seconds':max(abs(float(pts[k]-start-Fraction(i,24))) for i,k in enumerate(mapping)),'input_to_original_frame_exact':True,'padding_excluded':True}

def main():
 rows={r['pair_id']:r for r in read(ROOT/'design/INPUT_PLAN.json')['pairs']}
 result={'passed':True,'rows':[verify_source(ROOT,s,rows[s]) for s in SOURCES],'float_tensor_policy':'Actual same-host Native/forced clean tensors must equal each other; no host41 gbrpf32le or VAE latent expected SHA is imported.','GPU_started':False}
 atomic(ROOT/'audit/INPUT_TIMELINE_ACTUAL.json',result);print(json.dumps({'passed':True,'sources':len(result['rows']),'same_original_source_physical_grid':True}))

if __name__=='__main__':main()
