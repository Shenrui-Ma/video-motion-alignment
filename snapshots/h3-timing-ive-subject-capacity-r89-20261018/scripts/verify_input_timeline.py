"""Actual CPU media PTS verification; no cross-host float tensor hash expectation."""
import json,subprocess
from fractions import Fraction
from r89_contract import ROOT,read,require,sha,SOURCES,SOURCE_LENGTHS
from input_contract import nearest_map
from execution_gate import atomic

def probe(path):
 p=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,time_base:frame=best_effort_timestamp','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=120)
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
 mapping=nearest_map(pts,valid);require(mapping+[mapping[-1]]*(total-valid)==provenance['input_to_original_frame'],'nearest physical mapping differs')
 require(mapping[0]==0 and mapping[-1]==len(pts)-1,'source first/last frame omitted')
 return {'source_id':source,'original_sha256':sha(original),'prepared_sha256':sha(prepared),'original_frames':len(pts),'prepared_frames':total,'valid_frames':valid,'original_pts_rational':[str(x) for x in pts],'prepared_first_pts':str(newpts[0]),'prepared_last_pts':str(newpts[-1]),'max_selected_time_distance_seconds':max(abs(float(pts[k]-Fraction(i,24))) for i,k in enumerate(mapping)),'input_to_original_frame_exact':True}

def main():
 rows={r['pair_id']:r for r in read(ROOT/'design/INPUT_PLAN.json')['pairs']}
 result={'passed':True,'rows':[verify_source(ROOT,s,rows[s]) for s in SOURCES],'float_tensor_policy':'Actual same-host Native/forced clean tensors must equal each other; no host41 gbrpf32le or VAE latent expected SHA is imported.','GPU_started':False}
 atomic(ROOT/'audit/INPUT_TIMELINE_ACTUAL.json',result);print(json.dumps({'passed':True,'sources':len(result['rows']),'same_original_source_physical_grid':True}))

if __name__=='__main__':main()
