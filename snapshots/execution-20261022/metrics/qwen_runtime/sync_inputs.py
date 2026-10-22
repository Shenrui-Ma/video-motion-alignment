"""Stream a hashed .81 frame/metadata snapshot to .60; store no media on Mac."""
import argparse
import fcntl
import hashlib
import json
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_HOST = 'H3_SERVER'
SOURCE_ROOT = '/data/researcher/h3_metrics_20261022'
TARGET_HOST = 'H3_SERVER'
TARGET_ROOT = '/data3/researcher/h3_metrics_20261022/qwen_runtime'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3']
PROXY_ENV = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')

SNAPSHOT_CODE = r'''
import hashlib,json,sys,time
from pathlib import Path
root=Path(sys.argv[1]); files=[]; folders=[]
# PREPARED.json marks atomically published frame sets. Exclude active .partial builds.
for receipt in sorted((root/'frames').rglob('PREPARED.json')):
 if any(part.endswith('.partial') for part in receipt.relative_to(root).parts): continue
 folder=receipt.parent; prepared=json.loads(receipt.read_text()); frames=sorted(folder.glob('*.png'))
 if len(frames)!=prepared['frames']: raise RuntimeError('Incomplete published set: '+str(folder))
 folders.append({'path':str(folder.relative_to(root)),'prepared':prepared,'frame_count':len(frames)})
 for file in frames+[receipt]:
  before=file.stat(); h=hashlib.sha256()
  with file.open('rb') as f:
   for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
  after=file.stat()
  if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns): raise RuntimeError('Source changed during hashing: '+str(file))
  files.append({'path':str(file.relative_to(root)),'size':after.st_size,'mtime_ns':after.st_mtime_ns,'sha256':h.hexdigest()})
for file in sorted((root/'metadata').glob('*.json')):
 data=file.read_bytes(); json.loads(data)
 files.append({'path':str(file.relative_to(root)),'size':len(data),'mtime_ns':file.stat().st_mtime_ns,'sha256':hashlib.sha256(data).hexdigest()})
print(json.dumps({'captured_at':time.time(),'source_root':str(root),'folders':folders,'files':files,'bytes':sum(x['size'] for x in files)}))
'''
CHECK_CODE = r'''
import hashlib,json,sys,shutil
from pathlib import Path
request=json.load(sys.stdin); root=Path(request['target']); missing=[]; good=0
root.mkdir(parents=True,exist_ok=True)
for item in request['snapshot']['files']:
 p=root/item['path']; matches=False
 if p.is_file() and not p.is_symlink() and p.stat().st_size==item['size']:
  h=hashlib.sha256()
  with p.open('rb') as f:
   for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
  matches=h.hexdigest()==item['sha256']
 if matches:good+=1
 else:missing.append(item)
free=shutil.disk_usage(root).free; needed=sum(x['size'] for x in missing)
if free<needed+1024**3:raise RuntimeError('Insufficient destination capacity')
print(json.dumps({'verified_existing':good,'missing':missing,'missing_bytes':needed,'free_bytes':free}))
'''
ARCHIVE_CODE = r'''
import json,sys,tarfile
from pathlib import Path
request=json.load(sys.stdin); root=Path(request['source_root'])
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
 for item in request['files']:
  file=root/item['path']
  if file.stat().st_size!=item['size']:raise RuntimeError('Source size changed: '+str(file))
  archive.add(str(file),arcname=item['path'],recursive=False)
'''
RECEIVE_CODE = r'''
import hashlib,json,os,sys,tarfile,time
from pathlib import Path
request=json.loads(Path(sys.argv[1]).read_text()); root=Path(request['target']); expected={x['path']:x for x in request['files']}; completed=[]
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
 for member in archive:
  if member.name not in expected or not member.isfile():raise RuntimeError('Unexpected tar member')
  item=expected[member.name]; relative=Path(member.name)
  if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('Unsafe member path')
  path=root/relative; path.parent.mkdir(parents=True,exist_ok=True)
  if root.resolve() not in path.resolve().parents:raise RuntimeError('Destination escapes staging root')
  temp=path.with_name(path.name+'.qwen-sync-partial'); h=hashlib.sha256(); total=0
  with archive.extractfile(member) as source,temp.open('wb') as dest:
   for chunk in iter(lambda:source.read(8*1024*1024),b''):
    dest.write(chunk);h.update(chunk);total+=len(chunk)
  if total!=item['size'] or h.hexdigest()!=item['sha256']:raise RuntimeError('SHA256 mismatch: '+member.name)
  os.utime(temp,ns=(item['mtime_ns'],item['mtime_ns']));temp.replace(path);completed.append(member.name)
  if len(completed)%250==0:print('verified '+str(len(completed))+'/'+str(len(expected)),file=sys.stderr,flush=True)
if set(completed)!=set(expected):raise RuntimeError('Archive incomplete')
print(json.dumps({'received_verified':len(completed),'received_bytes':sum(x['size'] for x in expected.values()),'finished_at':time.time()}))
'''


def remote(host, code, *args, data=None):
    return subprocess.run(SSH + [host, shlex.join(['python3', '-c', code, *args])],
                          input=data, text=True, capture_output=True, check=True).stdout


def save(path, value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temp.replace(path)


def main(args):
    import os
    lock = (ROOT / 'sync.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for key in PROXY_ENV:os.environ.pop(key,None)
    run=ROOT/'sync_runs'/time.strftime('%Y%m%d-%H%M%S')
    run.mkdir(parents=True)
    manifest_path=Path(args.manifest)
    manifest_bytes=manifest_path.read_bytes()
    manifest=json.loads(manifest_bytes)
    (run/'manifest.input.json').write_bytes(manifest_bytes)
    print('Hashing source snapshot...',flush=True)
    snapshot=json.loads(remote(SOURCE_HOST,SNAPSHOT_CODE,SOURCE_ROOT))
    save(run/'source_snapshot.json',snapshot)
    request={'target':TARGET_ROOT+'/staged','snapshot':snapshot}
    check=json.loads(remote(TARGET_HOST,CHECK_CODE,data=json.dumps(request)))
    save(run/'destination_before.json',check)
    transfer={'source_root':SOURCE_ROOT,'target':request['target'],'files':check['missing']}
    transfer_path=TARGET_ROOT+'/sync_transfer_request.json'
    remote(TARGET_HOST,'import sys;from pathlib import Path;Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())',transfer_path,data=json.dumps(transfer))
    print(f"Streaming {len(check['missing'])} files / {check['missing_bytes']} bytes; {check['verified_existing']} already verified",flush=True)
    if check['missing']:
        with (run/'transfer.log').open('w') as log:
            receiver=subprocess.Popen(SSH+[TARGET_HOST,shlex.join(['python3','-c',RECEIVE_CODE,transfer_path])],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
            sender=subprocess.Popen(SSH+[SOURCE_HOST,shlex.join(['python3','-c',ARCHIVE_CODE])],stdin=subprocess.PIPE,stdout=receiver.stdin,stderr=log)
            receiver.stdin.close()
            sender.communicate(json.dumps(transfer).encode())
            receiver_output=receiver.stdout.read()
            receiver.wait()
            if sender.returncode or receiver.returncode:raise RuntimeError(f'Transfer failed: sender={sender.returncode}, receiver={receiver.returncode}; rerun safely resumes verified files')
            transferred=json.loads(receiver_output)
    else:transferred={'received_verified':0,'received_bytes':0}
    print('Rechecking every destination SHA256...',flush=True)
    after=json.loads(remote(TARGET_HOST,CHECK_CODE,data=json.dumps(request)))
    save(run/'destination_after.json',after)
    if after['missing']:raise RuntimeError('Final verification incomplete')
    # Publish manifest only after the selected snapshot verifies completely.
    (ROOT/'manifest.input.json').write_bytes(manifest_bytes)
    remote(TARGET_HOST,'import sys;from pathlib import Path;p=Path(sys.argv[1]);t=p.with_suffix(".tmp");t.write_bytes(sys.stdin.buffer.read());t.replace(p)',TARGET_ROOT+'/manifest.input.json',data=manifest_bytes.decode())
    summary={'status':'verified','started_snapshot_at':snapshot['captured_at'],'finished_at':time.time(),
             'source_host':SOURCE_HOST,'source_root':SOURCE_ROOT,'target_host':TARGET_HOST,'target_root':request['target'],
             'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),'manifest_jobs':len(manifest['jobs']),
             'manifest_job_ids':[x['id'] for x in manifest['jobs']], 'source_files':len(snapshot['files']),
             'source_frame_sets':len(snapshot['folders']),'source_bytes':snapshot['bytes'],
             'verified_destination_files':after['verified_existing'],**transferred,
             'transport':'two SSH streams piped in memory on Mac; internal network hosts; no proxy; no local media files',
             'snapshot_scope':'Only published frame folders with PREPARED.json plus metadata present at snapshot; later arrivals require another run'}
    save(run/'SYNC_RESULT.json',summary);save(ROOT/'SYNC_RESULT.json',summary)
    remote(TARGET_HOST,'import sys;from pathlib import Path;Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())',TARGET_ROOT+'/SYNC_RESULT.json',data=json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',default=str(ROOT.parent/'manifest.json'))
    main(p.parse_args())
