"""One CPU consumer for R50 two Native results; default is prepare-only."""
import argparse,fcntl,os,shlex,subprocess,time,traceback
from pathlib import Path
from contract import *
P=read(HERE/'PROTOCOL.json');REMOTE=P['root_remote']+'/analysis/postrun';HOST='H3_SERVER_A';PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python';CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock');SSH=['ssh','-J','H3_SERVER_B','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3']

def remote(args):
 temp=P['root_remote']+'/temp'
 return subprocess.run(SSH+[HOST,shlex.join(['env','TMPDIR='+temp,'TMP='+temp,'TEMP='+temp,'CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,REMOTE+'/remote_consume.py',*args])],capture_output=True,text=True,timeout=900)
def result(p):
 require(p.returncode==0,'remote phase failed; no automatic retry');return json.loads([x for x in p.stdout.splitlines() if x.strip()][-1])
def check_download(arc):
 inv=read(arc/'FILE_INVENTORY.json');original={k:v for k,v in inv.items() if not k.endswith('.pt')};allowed={'FILE_INVENTORY.json'}|({'ADMIN_RELEASE_ACCEPTANCE.json'} if (arc/'ADMIN_RELEASE_ACCEPTANCE.json').exists() else set())
 if (arc/'DERIVED_FILES.json').exists():
  derived=read(arc/'DERIVED_FILES.json');done=read(arc/'CPU_COMPLETE.json');require(done['passed'] is True and set(done['derived_outputs'])|{'CPU_COMPLETE.json'}==set(derived),'local completion omitted output');allowed.add('DERIVED_FILES.json')
 else:derived={x:sha(arc/x) for x in ('RUN_GATE.json','RUNTIME_GATE.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json')}
 require({str(x.relative_to(arc)) for x in arc.rglob('*') if x.is_file()}==set(original)|set(derived)|allowed,'local exact non-PT inventory')
 for rel,row in original.items():require(sha(safe(arc,rel))==row['sha256'],'original download SHA')
 for rel,d in derived.items():require(sha(safe(arc,rel))==d,'derived download SHA')
def download():
 dest=HERE/'captured/batch';dest.mkdir(parents=True,exist_ok=True);subprocess.run(['rsync','-a','--exclude=*.pt','-e',shlex.join(SSH),HOST+':'+REMOTE+'/captured/batch/',str(dest)+'/'],check=True,timeout=600);check_download(dest);save(HERE/'DOWNLOAD.json',{'file_inventory_sha256':sha(dest/'FILE_INVENTORY.json'),'all_PT_retained_and_verified_remote':True,'time':time.time()})
def main():
 print('Prepared only; execute one_phase.py with root BINDING for one bounded phase')
if __name__=='__main__':
 raise SystemExit('Use one_phase.py --execute with root BINDING; no resident consumer')
