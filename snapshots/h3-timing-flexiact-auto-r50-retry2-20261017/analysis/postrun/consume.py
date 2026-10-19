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
MAX_LOCAL_ORIGINAL_BYTES=20*1024*1024

def local_original(inventory):
 return {rel:row for rel,row in inventory.items() if not rel.endswith('.pt') and row['bytes']<=MAX_LOCAL_ORIGINAL_BYTES}

def retained_original(inventory,remote_archive):
 selected=local_original(inventory)
 return [{'file':remote_archive+'/'+rel,'relative_file':rel,**row} for rel,row in inventory.items() if rel not in selected]

def fetch_archive(remote_relative,destination):
 source=HOST+':'+REMOTE+'/'+remote_relative+'/'
 subprocess.run(['rsync','-a','--max-size=20m','--exclude=*.pt','-e',shlex.join(SSH),source,str(destination)+'/'],check=True,timeout=600)
 derived=destination/'DERIVED_FILES.json'
 if derived.exists():
  # Derived reports, decision ledgers and presentation media are always fetched.
  rows=read(derived);listing=HERE/'download_receipts'/remote_relative/'derived.list';listing.parent.mkdir(parents=True,exist_ok=True)
  for rel in rows:safe(destination,rel)
  listing.write_text('\n'.join(sorted(rows))+'\n')
  subprocess.run(['rsync','-a','--files-from='+str(listing),'-e',shlex.join(SSH),source,str(destination)+'/'],check=True,timeout=600)
 inventory=read(destination/'FILE_INVENTORY.json')
 save(HERE/'download_receipts'/remote_relative/'REMOTE_RETAINED.json',{'file_inventory_sha256':sha(destination/'FILE_INVENTORY.json'),'all_originals_hash_verified_at_remote_archive':True,'download_limit_bytes':MAX_LOCAL_ORIGINAL_BYTES,'retained':retained_original(inventory,REMOTE+'/'+remote_relative),'decision_summary':'final/{run}/DECISION_LEDGER.json when case evaluation completes'})

def check_download(arc):
 inv=read(arc/'FILE_INVENTORY.json');original=local_original(inv);allowed={'FILE_INVENTORY.json'}|({'ADMIN_RELEASE_ACCEPTANCE.json'} if (arc/'ADMIN_RELEASE_ACCEPTANCE.json').exists() else set())
 if (arc/'DERIVED_FILES.json').exists():
  derived=read(arc/'DERIVED_FILES.json');done=read(arc/'CPU_COMPLETE.json');require(done['passed'] is True and set(done['derived_outputs'])|{'CPU_COMPLETE.json'}==set(derived),'local completion omitted output');allowed.add('DERIVED_FILES.json')
 else:derived={x:sha(arc/x) for x in ('RUN_GATE.json','RUNTIME_GATE.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json')}
 require({str(x.relative_to(arc)) for x in arc.rglob('*') if x.is_file()}==set(original)|set(derived)|allowed,'local exact non-PT inventory')
 for rel,row in original.items():require(sha(safe(arc,rel))==row['sha256'],'original download SHA')
 for rel,d in derived.items():require(sha(safe(arc,rel))==d,'derived download SHA')
def download():
 dest=HERE/'captured/batch';dest.mkdir(parents=True,exist_ok=True);fetch_archive('captured/batch',dest);check_download(dest);save(HERE/'DOWNLOAD.json',{'file_inventory_sha256':sha(dest/'FILE_INVENTORY.json'),'all_PT_retained_and_verified_remote':True,'time':time.time()})
def main():
 print('Prepared only; execute one_phase.py with root BINDING for one bounded phase')
if __name__=='__main__':
 raise SystemExit('Use one_phase.py --execute with root BINDING; no resident consumer')
