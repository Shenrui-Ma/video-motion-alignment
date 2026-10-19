"""CPU score with unchanged official matcher and exact cached-source binding."""
import argparse,sys
from common import *
os.environ['CUDA_VISIBLE_DEVICES']='';sys.path.insert(0,str(ROOT/'runtime/metric_runtime'))
import score_cached_tracks as score

def run(name,role):
 verify_seal();c=case_root(name);s=read(c/'SPEC.json');m=read(c/'INPUTS.json');require(role in s['targets'],'unknown target');score.SELECTION_SHA=m.get('tracking_selection_sha256',sha(c/'INPUTS.json'));source=read(c/'tracks/source/REPORT.json');target=read(c/'tracks'/role/'REPORT.json')
 if s.get('source_cache_reuse'):validate_reuse(s,m,source,sha(c/'tracks/source/REPORT.json'),sha(c/'tracks/source/tracks.npz'))
 require(target['input_manifest']['sha256']==sha(c/'INPUTS.json') and target['score_video']['sha256']==m['roles'][role]['score_sha256'],'target output binding differs')
 for k in ('torch_version','cuda_version','checkpoint_sha256','tracker','selection_sha256','effective_frame_count','score_frame_indices'):require(source[k]==target[k],'tracking runtime differs: '+k)
 for k in ('hostname','gpu_name'):require(source['admission_before_cuda'][k]==target['admission_before_cuda'][k],'tracking host differs: '+k)
 result=score.score(c/'tracks/source',c/'tracks'/role);require(result['cuda_initialized'] is False,'unexpected CUDA score');result['actual_generated_video_sha256']=m['roles'][role]['full_sha256'];result['actual_gate_sha256']=m['gate_sha256'];result['case_inputs_sha256']=sha(c/'INPUTS.json');result['source_reused']=bool(s.get('source_cache_reuse'));result['valid_frames']=m['valid_frames'];result['fps']=24
 dest=c/'results'/f'{role}.json';require(not dest.exists(),'prior score exists; preserve it');save(dest,result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--role',required=True);a=p.parse_args();print(json.dumps(run(a.case,a.role)))
