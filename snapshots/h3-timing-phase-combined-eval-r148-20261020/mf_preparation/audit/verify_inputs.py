"""Check only this batch's actual files, reused numerical sources and source cache."""
from pathlib import Path
import sys,json,time
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import read,sha,save,validate_case,verify_seal,bound

def main():
 verify_seal();plan=read(R/'configs/PLAN.json');seen=set();cached=[]
 for key in plan['groups']:
  c=R/'cases'/key;m=validate_case(c,'source',True);assert m['benchmark']=='IVEBench' and 1<=m['valid_frames']<=145 and m['evaluation_fps']==24
  for t in m['targets']:
   validate_case(c,t['role'],True);domain=(m['source_full_sha256'],t['full_sha256'],tuple(t['evaluation_indices']));assert domain not in seen;seen.add(domain);assert t['evaluation_indices']==list(range(m['valid_frames']))
  if m['source_cache']:
   rp=c/'tracks/source/REPORT.json';v=read(rp);assert v['passed'] and sha(rp)==m['source_cache']['report_sha256'];assert sha(c/'tracks/source/tracks.npz')==v['tracks_sha256']==m['source_cache']['tracks_sha256'];assert v['official_commit']=='2dcf8900ee65197f43854c76f61c66a32bb8dbfc' and v['checkpoint_sha256']=='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df';assert v['effective_frame_count']==m['valid_frames'] and v['decoded_frame_md5']==m['source_frame_md5'] and v['source_score_sha256']==m['source_score_sha256'] and v['source_prepared_sha256']==m['source_full_sha256'] and v['selection_sha256']==m['selection_sha256'];cached.append(key)
 for rel,h in read(R/'configs/ive_NUMERIC.json')['files'].items():assert sha(R/'runtime/ive'/rel)==h
 weight=R/'runtime/ive/weights/baseline_offline.pth';assert sha(weight)=='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
 assert len(seen)==plan['unique_targets'];assert len(cached)==plan['source_cache_count'];assert 'torch'not in sys.modules
 import track,run_batch,score
 assert 'torch'not in sys.modules
 value={'passed':True,'seal':bound(R/'SEAL.json'),'targets':len(seen),'cached_sources':cached,'tracker_jobs':len(plan['jobs']),'actual_weight_path':str(weight.resolve()),'actual_weight_sha256':sha(weight),'CUDA_started':False,'unix':time.time()};save(R/'audit/TARGET_CPU_VERIFIED.json',value);print(json.dumps(value))
if __name__=='__main__':main()
