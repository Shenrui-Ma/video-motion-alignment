import os,sys
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import *
sys.path.insert(0,str(ROOT/'runtime/metric_runtime'))
import score_cached_tracks as score
def main():
 verify_seal();score.SELECTION_SHA=sha(ROOT/'INPUTS.json');rows={}
 source=read(ROOT/'tracks/source/REPORT.json')
 for role in ('native','forced'):
  target=read(ROOT/'tracks'/role/'REPORT.json')
  for k in ('torch_version','cuda_version','checkpoint_sha256','tracker','selection_sha256','effective_frame_count','score_frame_indices'):require(source[k]==target[k],'tracking runtime differs: '+k)
  for k in ('hostname','gpu_name'):require(source['admission_before_cuda'][k]==target['admission_before_cuda'][k],'tracking host differs: '+k)
  result=score.score(ROOT/'tracks/source',ROOT/'tracks'/role);require(result['cuda_initialized'] is False,'score initialized CUDA');save(ROOT/'results'/f'{role}.json',result);rows[role]=result['motion_fidelity']
 result={'source_id':'short_0358','ordinary':rows['native'],'guided':rows['forced'],'guided_minus_ordinary':rows['forced']-rows['native'],'input_sha256':sha(ROOT/'INPUTS.json'),'same_host_fresh_tracks':True,'scope':'105 effective frames, unchanged official MF; separate event review retains physical timing'}
 save(ROOT/'results/SUMMARY.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
