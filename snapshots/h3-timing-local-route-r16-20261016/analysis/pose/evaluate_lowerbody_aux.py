"""Call the sealed auxiliary function with an explicitly loaded remote frozen metric."""
import fcntl,hashlib,importlib.util,json,os
from pathlib import Path
ROOT=Path('/data5/researcher/h3_runs/timing_local_route_r16_20261016')
OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
def load(p,name,wanted):
 assert hashlib.sha256(p.read_bytes()).hexdigest()==wanted
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 os.environ['CUDA_VISIBLE_DEVICES']=''
 for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='4'
 with Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  metric=load(OLD/'scripts/timing_metrics.py','r16frozen','eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e')
  aux=load(ROOT/'analysis/local_effects/evaluate_limb_side_effects.py','r16aux','ff7ce80a5cc9e04e670e54359c7cce6a34da686d8764559389e110175eeba7fc')
  d=json.loads((ROOT/'analysis/pose/four_arm_compact.json').read_text());out=ROOT/'analysis/pose/lowerbody_aux';out.mkdir(exist_ok=True);summary={}
  for name,item in d['pose_inventory'].items():
   p=Path(item['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
   result=aux.evaluate(OLD/'analysis/pose/old_sam/05_real_megumi_v.pose.json',p,metric=metric)
   result['support_note']='Pairwise source/this-arm support, not the four-arm common support.'
   (out/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
   summary[name]=[{k:r.get(k) for k in ('window','feature','threshold','status','reliable_lag_frames','same_frame')} for r in result['measurements']]
  (out/'summary.json').write_text(json.dumps({'pairwise_support_not_common_support':True,'runs':summary},indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
