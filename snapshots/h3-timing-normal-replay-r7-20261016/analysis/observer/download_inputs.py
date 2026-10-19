"""Read-only remote capture download after sampler completion; no GPU imports."""
from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent
ROOT='/data5/researcher/h3_runs/timing_normal_replay_r7_20261016'
REMOTE_CODE=r'''
from pathlib import Path
import hashlib,json
root=Path('/data5/researcher/h3_runs/timing_normal_replay_r7_20261016')
run='r7_s05_normal_native_x0';xroot=root/'audit/x0'/run
manifest=json.loads((xroot/'manifest.json').read_text())
if manifest['status']!='complete':
 print(json.dumps({'complete':False,'callback_count':manifest['callback_count'],'captures':[r['file'] for r in manifest['captures']]}));raise SystemExit(0)
condition_path=root/'audit'/f'{run}_conditioning.json'
condition=json.loads(condition_path.read_text())
refs=[x['latent'] for x in condition['native_vae_calls'] if x['latent']['shape']==[1,24,42,36,64]]
if len(refs)!=1:raise RuntimeError('expected one actualvideo reference')
ref=(root/'audit'/refs[0]['tensor_file']).resolve();ref.relative_to(root/'audit/tensor_blobs')
paths=[xroot/'manifest.json',condition_path,root/'configs'/f'{run}.json',ref]
paths += [xroot/r['file'] for r in manifest['captures']]+[xroot/manifest['final_sampler_result']['file']]
records=[]
for path in paths:
 relative=str(path.resolve().relative_to(root));data=path.read_bytes();records.append({'relative':relative,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
print(json.dumps({'complete':True,'remote_root':str(root),'run_id':run,'reference_relative':str(ref.relative_to(root)),'files':records}))
'''

def main():
 p=subprocess.run(['ssh','-o','BatchMode=yes','H3_SERVER_A','python3','-'],input=REMOTE_CODE,text=True,capture_output=True,check=True)
 data=json.loads(p.stdout)
 if not data['complete']:
  print(json.dumps(data));return
 manifest_path=HERE/'download_manifest.json'
 if manifest_path.exists():
  if json.loads(manifest_path.read_text())!=data:raise RuntimeError('remote input inventory changed')
 else:manifest_path.write_text(json.dumps(data,indent=2)+'\n')
 paths=[x['relative'] for x in data['files']]
 if any(Path(x).is_absolute() or '..' in Path(x).parts for x in paths):raise RuntimeError('unsafe source path')
 listing=HERE/'download_files.txt';listing.write_text('\n'.join(paths)+'\n')
 target=HERE/'inputs';target.mkdir(exist_ok=True)
 subprocess.run(['rsync','-a','--files-from='+str(listing),'H3_SERVER_A:'+ROOT+'/',str(target)+'/'],check=True)
 for x in data['files']:
  path=target/x['relative']
  if path.stat().st_size!=x['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=x['sha256']:raise RuntimeError('download checksum mismatch '+x['relative'])
 print(json.dumps({'downloaded_verified':len(paths),'bytes':sum(x['bytes'] for x in data['files']),'no_remote_writes':True,'remote_stderr':p.stderr},indent=2))
if __name__=='__main__':main()
