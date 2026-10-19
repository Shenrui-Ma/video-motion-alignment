"""Only prepare an explicit command; never launch or reuse a tracking attempt."""
import argparse,shlex
from common import *
def command(gpu,python):
 verify_runtime();validate_cache();require((ROOT/'prepared/guided/MATCHED_GATE_BINDING.json').is_file(),'actual R101 matched input pending')
 manifest=ROOT/'prepared/guided/TRACK_INPUTS.json';require(manifest.is_file(),'actual guided manifest pending');control=ROOT/'controls/guided';output=ROOT/'tracks/guided';require(not control.exists() and not output.exists(),'existing attempt retained')
 return ['env','CUDA_VISIBLE_DEVICES='+gpu,'OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','PYTHONDONTWRITEBYTECODE=1',python,str(ROOT/'scripts/track_shared.py'),'--control',str(control),'--','--input-manifest',str(manifest),'--case',CASE,'--gpu-uuid',gpu,'--output',str(output)]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--gpu-uuid',required=True);p.add_argument('--python',default='/data3/researcher/ComfyUI/.venv/bin/python');a=p.parse_args();argv=command(a.gpu_uuid,a.python);print(json.dumps({'argv':argv,'shell':shlex.join(argv),'CUDA_started':False,'minimum_current_free_bytes':40*1024**3,'root_action':'fresh cgroup>=8GiB, exact ready identity+peer+GO, release exact child/CUDA then remove own peer'},indent=2))
