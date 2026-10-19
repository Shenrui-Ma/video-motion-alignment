"""Per-case data adapter around byte-identical official numerical tracking."""
import argparse,resource,sys
from common import *
sys.path.insert(0,str(ROOT/'runtime/metric_runtime'))
import ive_mf_adapter as adapter
import run_tracks

def bind_inputs(c):
 s=read(c/'SPEC.json');m=read(c/'INPUTS.json');require(m['spec_sha256']==sha(c/'SPEC.json'),'prepared spec changed');selection=m.get('tracking_selection_sha256',sha(c/'INPUTS.json'));prov=read(c/s['source']['provenance_file']);count=m['valid_frames']
 row={'pair_id':m['source_id'],'selection_sha256':selection,'source_original':bound(c/s['source']['original_file']),'source_prepared_video':bound(c/m['roles']['source']['full_file']),'source_preparation_record':bound(c/s['source']['provenance_file']),'source_score_video':bound(c/m['roles']['source']['score_file']),'score_frame_indices':list(range(count)),'input_to_original_frame':prov['input_to_original_frame'],'edited':{}}
 for role,r in s['targets'].items():row['edited'][role]={'score_video':bound(c/m['roles'][role]['score_file']),'full_video':bound(c/r['full_file']),'generation_record':bound(c/r['history_file']),'release_record':bound(c/s['gate']['file'])}
 def validate(*args):
  require(sha(c/s['gate']['file'])==m['gate_sha256'],'actual gate changed');validate_gate(s,read(c/s['gate']['file']))
  for role,r in m['roles'].items():
   require(sha(c/r['full_file'])==r['full_sha256'] and sha(c/r['score_file'])==r['score_sha256'],'actual media changed');adapter.validate_time_view(adapter.media_info(c/r['score_file'],'ffprobe'),count);require(adapter.frame_hashes(c/r['score_file'],'ffmpeg')==r['score_frame_md5'],'score decoded pixels changed')
  if s.get('source_cache_reuse'):validate_reuse(s,m,read(c/'tracks/source/REPORT.json'),sha(c/'tracks/source/REPORT.json'),sha(c/'tracks/source/tracks.npz'))
 run_tracks.select_pair=lambda manifest,pair,selection_file:(row,{'pair_id':m['source_id'],'input_protocol':{'effective_frame_count':count}})
 run_tracks.validate_source_row=validate;run_tracks.validate_edited_entry=lambda e,n,p,f:adapter.validate_time_view(adapter.media_info(adapter.bound_file(e['score_video']),p),n)
 run_tracks.LITERATURE=Path(read(ROOT/'configs/RUNTIME.json')['checkpoint']).parent.parent;run_tracks.SELECTION_SHA=selection;run_tracks.check_gpu=resource_check
 return s,m

def main():
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--role',required=True);p.add_argument('--gpu-uuid');p.add_argument('--check-only',action='store_true');a=p.parse_args();verify_seal();c=case_root(a.case);s,m=bind_inputs(c);require(a.role in m['roles'],'unknown role');out=c/('preflight' if a.check_only else 'tracks')/a.role
 if not a.check_only:
  require(not(s.get('source_cache_reuse') and a.role=='source'),'source cache is frozen for reuse');require(a.gpu_uuid and os.environ.get('CUDA_VISIBLE_DEVICES')==a.gpu_uuid,'explicit exact GPU required');control=c/'controls'/a.role;control.mkdir(parents=True,exist_ok=False)
  ready={'identity':identity(os.getpid()),'case':a.case,'role':a.role,'gpu_uuid':a.gpu_uuid,'input_manifest_sha256':sha(c/'INPUTS.json'),'seal_sha256':sha(ROOT/'SEAL.json'),'CUDA_started':False};save(control/'ready.json',ready);print(json.dumps(ready),flush=True);deadline=time.monotonic()+300
  while not(control/'go.json').exists():require(time.monotonic()<deadline,'preCUDA GO deadline');time.sleep(.2)
  require(read(control/'go.json')==ready and identity(os.getpid())==ready['identity'],'GO/identity mismatch');verify_seal()
 try:
  run_tracks.main(argparse.Namespace(input_manifest=str(c/'INPUTS.json'),selection=str(c/'INPUTS.json'),pair=m['source_id'],method=a.role,gpu_uuid=a.gpu_uuid,check_only=a.check_only,output=str(out),ffmpeg='ffmpeg',ffprobe='ffprobe'))
 finally:
  if not a.check_only:save(control/'PROCESS_USAGE.json',{'maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'identity':identity(os.getpid()),'unix':time.time()})
if __name__=='__main__':main()
