"""Print an exact root-owned pre-CUDA ready/go command; no GPU initialization."""
import argparse,shlex
from common import *
def command(method,gpu,python):
 verify_runtime();require(method in ['reference','native','guided'],'unknown method')
 if method=='guided':require((ROOT/'prepared/guided/MATCHED_GATE_BINDING.json').is_file(),'R101 actual paired result and independent binding still PENDING')
 manifest=METRIC/'SOURCE_INPUTS.json' if method=='reference' else ROOT/'prepared'/method/'TRACK_INPUTS.json';require(manifest.is_file(),'actual input not prepared')
 control=ROOT/'controls'/method;output=ROOT/'tracks'/method;require(not control.exists() and not output.exists(),'existing attempt preserved')
 return ['env','CUDA_VISIBLE_DEVICES='+gpu,'OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','PYTHONDONTWRITEBYTECODE=1',python,str(ROOT/'scripts/track_shared.py'),'--control',str(control),'--','--input-manifest',str(manifest),'--case',CASE,'--gpu-uuid',gpu,'--output',str(output)]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--method',choices=['reference','native','guided'],required=True);p.add_argument('--gpu-uuid',required=True);p.add_argument('--python',default='/data3/researcher/ComfyUI/.venv/bin/python');a=p.parse_args();argv=command(a.method,a.gpu_uuid,a.python);print(json.dumps({'argv':argv,'shell':shlex.join(argv),'CUDA_started':False,'required_current_free_bytes':40*1024**3,'root_action':'check host cgroup; start; verify exact ready PID/UID/start/cmdSHA; register current own peer; copy ready to go; verify tracker exit/CUDA release'},indent=2))
