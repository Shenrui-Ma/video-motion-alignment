import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import hashlib,importlib.util,json
import torch
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
source=ROOT/'extensions/H3FeedbackRouter/observer.py'
spec=importlib.util.spec_from_file_location('reviewed_observer',source);module=importlib.util.module_from_spec(spec)
env=dict(os.environ);rng=torch.random.get_rng_state().clone()
spec.loader.exec_module(module)
assert env==dict(os.environ) and torch.equal(rng,torch.random.get_rng_state())
torch.set_num_threads(1)
p=json.loads((HERE/'PROTOCOL.json').read_text());results=json.loads((HERE/'RESULTS.json').read_text())
reference=torch.load(p['reference']['path'],map_location='cpu',weights_only=True,mmap=True)
observer=module.FrozenGap5Observer(reference)
rows=[]
for entry in results['rows']:
 video=torch.load(HERE/'inputs'/entry['file'],map_location='cpu',weights_only=True,mmap=True)['video']
 observed=observer(video);expected=dict(entry['windows'][0])
 for k in ('independent_final_pose','both_pose_thresholds_known','within_two_frames_both_thresholds'):expected.pop(k,None)
 assert observed==expected,entry['file']
 rows.append({'file':entry['file'],'full_49_point_observation_equal':True,'lag':observed['best']['lag_frames']})
assert not torch.cuda.is_initialized()
report={'passed':True,'observer_py_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows,'import_environment_unchanged':True,'import_cpu_rng_unchanged':True,'CUDA_initialized':False,'scope':'actual existing R4 snapshot main-window outputs equal all49 curves from frozen offline implementation; no feedback sampler invoked'}
with (HERE/'builder_observer_equivalence.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report,indent=2))
