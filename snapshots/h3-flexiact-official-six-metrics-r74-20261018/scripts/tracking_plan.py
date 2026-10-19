"""Print commands only; root owns all GPU execution and pre-CUDA go decisions."""
import argparse,shlex
from common import *
def command(key,method,gpu,python):
 verify_runtime();require(method in ('reference',)+METHODS,'unsupported role')
 if method=='reference':
  action=key;source_item(action);manifest=METRIC/'SOURCE_INPUTS.json';directory=action
 else:
  p=pair_info(key);action=p['motion_source_id'];manifest=ROOT/'prepared'/key/method/'TRACK_INPUTS.json';require(manifest.is_file(),'generated49 intake pending');directory=key
 control=ROOT/'controls'/f'{method}_{directory}';output=ROOT/'tracks'/method/directory;require(not control.exists() and not output.exists(),'existing tracking attempt')
 return ['env','CUDA_VISIBLE_DEVICES='+gpu,'OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','PYTHONDONTWRITEBYTECODE=1',python,str(ROOT/'scripts/track_shared.py'),'--control',str(control),'--','--input-manifest',str(manifest),'--case',source_item(action)['id'],'--gpu-uuid',gpu,'--output',str(output)]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--key',required=True,help='motion source for reference; pair key for generated');p.add_argument('--method',choices=('reference',)+METHODS,required=True);p.add_argument('--gpu-uuid',required=True);p.add_argument('--python',default='/data3/researcher/ComfyUI/.venv/bin/python');a=p.parse_args();argv=command(a.key,a.method,a.gpu_uuid,a.python)
 print(json.dumps({'argv':argv,'shell':shlex.join(argv),'CUDA_started':False,'root_action':'launch; inspect exact ready PID; register peer; copy ready to go; verify process exit and release','required_current_free_bytes':40*1024**3},indent=2))
