"""Strict host-specific CPU replay verification; preserve the original host41 gate."""
import argparse,json,sys,time
from pathlib import Path
import verify_native as original
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from r80_contract import read,sha,require,SOURCES
from execution_gate import atomic

def validate_expectation(root,source):
 path=root/'configs/expected_input_pixels_host9_v2.json';all_rows=read(path);e=all_rows[source];runtime=read(root/'configs/runtime.json')
 require(all_rows['schema']=='r80-independent-host9-input-expectation-v2' and all_rows['runtime_sha256']==sha(root/'configs/runtime.json'),'host9 expectation runtime changed')
 require(runtime['host']=='H3_SERVER_A' and e['CUDA_initialized'] is False,'wrong runtime or replay initialized CUDA')
 require(e['input_file_sha256']==sha(root/'inputs'/(source+'_video.mp4')),'replay video bytes changed')
 require(sha(Path(e['replay_file']))==e['replay_sha256'],'independent replay evidence changed')
 require(sha(Path(e['core_video_types']['path']))==e['core_video_types']['sha256'] and sha(root/'scripts/compatibility_bootstrap.py')==e['compatibility_sha256'],'actual decoder source changed')
 require(e['frame_count']==90 and len(e['pts_seconds'])==90 and all(abs(t-i/24)<1e-6 for i,t in enumerate(e['pts_seconds'])),'replay time mapping changed')
 provenance=read(root/'inputs'/(source+'_provenance.json'))
 require(e['yuv420p_md5']==provenance['input_frame_md5'],'replay YUV differs from source preparation')
 require(e['input_video']['shape']==[90,736,1312,3] and e['input_video']['dtype']=='torch.float32','replay tensor contract differs')
 if source=='short_0352':require(e['phase']=='before generation' and e['generation_job_absent_at_freeze'] is True,'0352 expectation was not frozen before generation')
 return path

def verify(root,source):
 path=validate_expectation(root,source)
 result=original.verify(root,source,expected_input_file=path)
 result['schema']='r80-native-host9-decode-runtime-gate-v2'
 result['strict_decode_replay']={'passed':result['checks']['actual_original_input_pixels'],'expectation_file':str(path),'expectation_sha256':sha(path),'equality':'exact shape/dtype/tensor-byte SHA; zero tolerance','source':source}
 old=root/'analysis/postrun'/source/'NATIVE_RUNTIME_GATE.json'
 if old.exists():result['legacy_gate']={'file':str(old),'sha256':sha(old),'passed':read(old)['passed'],'preserved':True}
 else:result['legacy_gate']=None
 result['comparison_scope']='Same host9 decoder expectation independently reconstructed from fixed source bytes. Original host41 expectation and failed receipt retained; historical cross-host output remains descriptive.'
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);a=p.parse_args();dest=ROOT/'analysis/postrun'/a.source/'NATIVE_RUNTIME_GATE_HOST9_v2.json'
 require(not dest.exists(),'existing v2 receipt must be preserved')
 value=verify(ROOT,a.source);atomic(dest,value);print(json.dumps({'passed':value['passed'],'checks':value['checks'],'receipt':str(dest),'sha256':sha(dest)},indent=2))
 if not value['passed']:raise SystemExit(2)
