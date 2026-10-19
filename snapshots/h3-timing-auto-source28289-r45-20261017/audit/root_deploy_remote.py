from pathlib import Path
import tarfile,hashlib,json,shutil,subprocess
r=Path('/data5/researcher/h3_runs/timing_auto_source28289_r45_20261017'); p=Path('/tmp/h3_r45_runtime_34971180.tar.gz')
assert not r.exists()
assert hashlib.sha256(p.read_bytes()).hexdigest()=='34971180a0bc592a659a07edc7f9ee74d69db7274da0b1a9133248991b9298e8'
with tarfile.open(p) as t:
 members=t.getmembers(); assert len([x for x in members if x.isfile()])==238
 for x in members: assert not x.name.startswith('/') and '..' not in Path(x.name).parts and (x.isfile() or x.isdir()),x.name
 r.mkdir();t.extractall(r)
m=json.loads((r/'deploy_manifest.json').read_text()); assert hashlib.sha256((r/'deploy_manifest.json').read_bytes()).hexdigest()=='674f5a90ab758a701aafdb3178c0e40807a1c23840d53b8c6074e831417746f7'
for name,e in m['files'].items():
 b=(r/name).read_bytes();assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256'],name
for name,h in json.loads((r/'configs/input_hashes.json').read_text()).items():
 src=Path('/data5/researcher/h3_runs/timing_source28289_native_r42_20261017/inputs')/name
 assert hashlib.sha256(src.read_bytes()).hexdigest()==h
 dest=r/'inputs'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(src,dest);assert hashlib.sha256(dest.read_bytes()).hexdigest()==h
p=subprocess.run(['python3',str(r/'scripts/preflight.py'),'--metadata-only'],capture_output=True,text=True)
(r/'audit/root_metadata_preflight.log').write_text(p.stdout+p.stderr)
print(json.dumps(dict(immutable_verified=len(m['files']),input_verified=3,preflight_exit=p.returncode)))
print((p.stdout+p.stderr)[-1500:]);raise SystemExit(p.returncode)
