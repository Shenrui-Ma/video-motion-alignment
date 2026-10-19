from pathlib import Path
import tarfile,hashlib,json,subprocess,os
r=Path('/data5/researcher/h3_runs/timing_attention_observer_r46_20261017');bundle=Path('/tmp/h3_r46_runtime_ba629baf.tar.gz')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not r.exists()
assert sha(bundle)=='ba629baf985c4ca21c75f5afd606ca328b6ba9485b691619bcda11be2044860e'
with tarfile.open(bundle) as t:
 members=t.getmembers();assert len([x for x in members if x.isfile()])==76
 for x in members:assert not x.name.startswith('/') and '..' not in Path(x.name).parts and(x.isfile() or x.isdir()),x.name
 r.mkdir();t.extractall(r)
assert sha(r/'deploy_manifest.json')=='0731435c2e007739d4747eaa9a5a2f25c68d48494c29dff2be0d8259090d709a'
for n,e in json.loads((r/'deploy_manifest.json').read_text())['files'].items():assert (r/n).stat().st_size==e['bytes'] and sha(r/n)==e['sha256'],n
proc=Path('/proc/48194');identity={'uid':proc.stat().st_uid,'start_ticks':proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],'cmdline_sha256':sha(proc/'cmdline')}
assert identity=={'uid':1016,'start_ticks':'2624449931','cmdline_sha256':'76e8c92ea11fbcf408bab8e29bbe623be0470c8bf0101c430249cb0e4606fa4e'}
admission={'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[{'pid':48194,'identity':identity}]}
(r/'configs/admission.json').write_text(json.dumps(admission,indent=2)+'\n')
result=subprocess.run(['python3',str(r/'scripts/preflight.py')],capture_output=True,text=True,env=dict(os.environ,LC_ALL='C',LANG='C'))
(r/'audit/root_metadata_preflight.log').write_text(result.stdout+result.stderr)
print(json.dumps({'immutable_verified':75,'preflight_exit':result.returncode,'peer':48194,'admission_ready':False}));print(result.stdout+result.stderr);raise SystemExit(result.returncode)
