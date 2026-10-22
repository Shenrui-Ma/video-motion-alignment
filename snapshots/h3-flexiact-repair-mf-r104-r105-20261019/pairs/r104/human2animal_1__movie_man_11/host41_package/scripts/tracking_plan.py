import argparse,shlex
from common import *
def command(method,gpu,python):
 verify_runtime();require(method in ['reference','native','guided'],'unknown method');manifest=METRIC/'SOURCE_INPUTS.json' if method=='reference' else ROOT/'prepared'/method/'TRACK_INPUTS.json';control=ROOT/'controls'/method;output=ROOT/'tracks'/method;require(not control.exists() and not output.exists(),'prior attempt retained');return ['env','CUDA_VISIBLE_DEVICES='+gpu,'OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','PYTHONDONTWRITEBYTECODE=1',python,str(ROOT/'scripts/track_shared.py'),'--control',str(control),'--','--input-manifest',str(manifest),'--case',CASE,'--gpu-uuid',gpu,'--output',str(output)]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--method',required=True);p.add_argument('--gpu-uuid',required=True);p.add_argument('--python',default='/data3/researcher/ComfyUI/.venv/bin/python');a=p.parse_args();print(json.dumps({'argv':command(a.method,a.gpu_uuid,a.python),'CUDA_started':False}))
