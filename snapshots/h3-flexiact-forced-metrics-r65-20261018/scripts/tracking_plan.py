"""Print a concrete root-run command; this tool never starts CUDA or a child."""
import argparse,shlex
from common import *
def command(source,method,gpu,python):
 verify_runtime();require(source in SOURCES and method in ('reference',)+METHODS,'unsupported case')
 if method=='reference':manifest=METRIC/'SOURCE_INPUTS.json'
 else:
  manifest=ROOT/'prepared'/source/method/'TRACK_INPUTS.json';require(manifest.is_file(),'generated49 intake pending')
 control=ROOT/'controls'/f'{method}_{source}';output=ROOT/'tracks'/method/source;require(not control.exists() and not output.exists(),'existing tracking attempt')
 return ['env','CUDA_VISIBLE_DEVICES='+gpu,'OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','PYTHONDONTWRITEBYTECODE=1',python,str(ROOT/'scripts/track_shared.py'),'--control',str(control),'--','--input-manifest',str(manifest),'--case',f'human/{source}/000','--gpu-uuid',gpu,'--output',str(output)]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--method',choices=('reference',)+METHODS,required=True);p.add_argument('--gpu-uuid',default='GPU-REDACTED');p.add_argument('--python',default='/data3/researcher/ComfyUI/.venv/bin/python');a=p.parse_args();argv=command(a.source,a.method,a.gpu_uuid,a.python)
 print(json.dumps({'argv':argv,'shell':shlex.join(argv),'CUDA_started':False,'root_action':'launch, inspect exact ready.json PID identity, register own peer resources, copy exact ready to go, then confirm child exit and GPU release','measured_r49_peak_reserved_bytes':39363543040,'fresh_source_required':True},indent=2))
