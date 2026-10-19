"""Execute unchanged author MF on fresh same-runtime source/target tracks."""
import argparse,os,subprocess,sys,time
from common import *
def run(source,method):
 verify_runtime();source_dir=ROOT/'tracks/reference'/source;target_dir=ROOT/'tracks'/method/source;s=read(source_dir/'REPORT.json');t=read(target_dir/'REPORT.json')
 require(s['passed'] is True and t['passed'] is True and s['case']['id']==t['case']['id']==f'human/{source}/000','actual tracking pair incomplete')
 for k in ['torch_version','cuda_version','checkpoint_sha256','metric_functions_sha256','vendor_manifest_sha256','grid_size','mask','tracks_dtype']:require(s[k]==t[k],'fresh source/target runtime differs: '+k)
 for k in ['hostname','gpu_name']:require(s['admission_before_cuda'][k]==t['admission_before_cuda'][k],'fresh source/target hardware differs: '+k)
 for directory in [source_dir,target_dir]:
  binding=read(directory/'R65_BINDING.json');require(binding['report']['sha256']==sha(directory/'REPORT.json') and binding['frozen_numerical_tracker']['sha256']==sha(METRIC/'run_tracks.py') and binding['administrative_wrapper']['sha256']==sha(ROOT/'scripts/track_shared.py'),'tracking wrapper/report binding differs')
 manifest=ROOT/'prepared'/source/method/'TRACK_INPUTS.json';require(t['case']==read(manifest)['inputs'][0] and t['manifest_sha256']==sha(manifest),'target tracker binding differs')
 destination=ROOT/'scores'/method/source;require(not destination.exists(),'existing score attempt');command=[sys.executable,str(METRIC/'score_pair.py'),'--reference',str(source_dir),'--edited',str(target_dir),'--output',str(destination)];started=time.monotonic()
 completed=subprocess.run(command,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=180)
 save(ROOT/'audit'/f'{source}_{method}_score.json',{'command':command,'returncode':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr,'wall_seconds':time.monotonic()-started,'reference_report':bound(source_dir/'REPORT.json'),'target_report':bound(target_dir/'REPORT.json')})
 require(completed.returncode==0,'official score failed; inspect receipt');return read(destination/'SCORE.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--method',choices=METHODS,required=True);a=p.parse_args()
 with cpu_lock():print(json.dumps(run(a.source,a.method)))
