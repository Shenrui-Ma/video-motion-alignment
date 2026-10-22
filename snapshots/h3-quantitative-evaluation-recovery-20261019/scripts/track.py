"""Bind one completed case to unchanged official run_tracks numerical code."""
import argparse,sys,resource
from common import *
sys.path.insert(0,str(ROOT/'runtime/metric_runtime'))
import ive_mf_adapter as adapter
import run_tracks
def bind_inputs():
 m=read(ROOT/'INPUTS.json');prov=read(ROOT/'inputs/source_provenance.json')
 def bound(name):return {'file':str(ROOT/name),'sha256':sha(ROOT/name)}
 row={'pair_id':'short_0358','selection_sha256':sha(ROOT/'INPUTS.json'),'source_original':bound('inputs/source_original.mp4'),'source_prepared_video':bound('inputs/source_full.mp4'),'source_preparation_record':bound('inputs/source_provenance.json'),'source_score_video':bound('inputs/source_score.mp4'),'score_frame_indices':list(range(105)),'input_to_original_frame':prov['input_to_original_frame'],'edited':{}}
 for role in ('native','forced'):row['edited'][role]={'score_video':bound(f'inputs/{role}_score.mp4'),'full_video':bound(f'inputs/{role}_full.mp4'),'generation_record':bound(f'inputs/{role}_history.json'),'release_record':bound('inputs/PAIR_RUNTIME_GATE.json')}
 entry={'pair_id':'short_0358','input_protocol':{'effective_frame_count':105}}
 def source_validate(*args):
  require(m['gate_sha256']==sha(ROOT/'inputs/PAIR_RUNTIME_GATE.json'),'actual gate changed')
  for role,d in m['roles'].items():
   require(sha(ROOT/d['full_file'])==d['full_sha256'] and sha(ROOT/d['score_file'])==d['score_sha256'],'fixed media changed')
   info=adapter.media_info(ROOT/d['score_file'],'ffprobe');adapter.validate_time_view(info,105)
   require(adapter.frame_hashes(ROOT/d['score_file'],'ffmpeg')==d['score_frame_md5'],'decoded scoring input changed')
  require(sha(ROOT/'inputs/source_provenance.json')==m['source_provenance_sha256'],'provenance changed')
 run_tracks.select_pair=lambda manifest,pair,selection:(row,entry)
 run_tracks.validate_source_row=source_validate
 run_tracks.validate_edited_entry=lambda target,count,probe,ff:adapter.validate_time_view(adapter.media_info(adapter.bound_file(target['score_video']),probe),count)
 run_tracks.LITERATURE=CHECKPOINT.parent.parent
 run_tracks.SELECTION_SHA=sha(ROOT/'INPUTS.json');run_tracks.check_gpu=resource_check
 return m
def main():
 p=argparse.ArgumentParser();p.add_argument('--role',choices=('source','native','forced'),required=True);p.add_argument('--check-only',action='store_true');a=p.parse_args();verify_seal();bind_inputs()
 control=ROOT/'controls'/a.role;out=ROOT/('preflight' if a.check_only else 'tracks')/a.role
 if not a.check_only:
  require(os.getuid()==1004,'target UID differs');control.mkdir(parents=True,exist_ok=False)
  ready={'identity':identity(os.getpid()),'role':a.role,'gpu_uuid':GPU,'input_manifest_sha256':sha(ROOT/'INPUTS.json'),'seal_sha256':sha(ROOT/'SEAL.json'),'CUDA_started':False};save(control/'ready.json',ready);print(json.dumps(ready),flush=True)
  deadline=time.monotonic()+300
  while not (control/'go.json').exists():
   require(time.monotonic()<deadline,'preCUDA registration timeout');time.sleep(.2)
  require(read(control/'go.json')==ready and identity(os.getpid())==ready['identity'],'GO/identity differs');verify_seal()
 try:
  run_tracks.main(argparse.Namespace(input_manifest=str(ROOT/'INPUTS.json'),selection=str(ROOT/'INPUTS.json'),pair='short_0358',method=a.role,gpu_uuid=GPU,check_only=a.check_only,output=str(out),ffmpeg='ffmpeg',ffprobe='ffprobe'))
 finally:
  if not a.check_only:save(control/'PROCESS_USAGE.json',{'maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'identity':identity(os.getpid()),'unix':time.time()})
if __name__=='__main__':main()
