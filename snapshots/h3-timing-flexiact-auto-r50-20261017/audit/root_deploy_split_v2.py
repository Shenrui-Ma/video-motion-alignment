"""Install the preserved engineering revision into an inactive R50 producer."""
from pathlib import Path
import hashlib,json,os,tarfile,time
R=Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017')
STAGE=Path('/data5/researcher/h3_runs/r53_root_stage')
OLD='4f1b4fbf3a30ea5baa27e9cd4feff3ac163628a61c66db14f5eb525a5c66e3f0'
NEW='13d2842849143f4d30122e51a8dd1ab05e3b083f9f1af7de8777f4ec35798b93'
BUNDLE='2a74c5196938195d60415fe50807737ade5dffa73843fdc32bd6354d21cae988'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
assert sha(R/'deploy_manifest.json')==OLD
for rel,row in read(R/'deploy_manifest.json')['files'].items():
    assert sha(R/rel)==row['sha256'],rel
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit() or proc.stat().st_uid!=os.getuid():continue
    try:command=proc.joinpath('cmdline').read_bytes()
    except FileNotFoundError:continue
    assert not (b'compatibility_bootstrap.py' in command and str(R).encode() in command),proc.name
bundle=STAGE/'r50_runtime_bundle_v2.tar.gz'
assert sha(bundle)==BUNDLE
backup=R/'audit/root_before_split_v2'
backup.mkdir(exist_ok=False)
(backup/'deploy_manifest.json').write_bytes((R/'deploy_manifest.json').read_bytes())
(backup/'admission.json').write_bytes((R/'configs/admission.json').read_bytes())
with tarfile.open(bundle) as tf:
    for m in tf.getmembers():
        assert not m.name.startswith('/') and '..' not in Path(m.name).parts
        assert m.isfile() or m.isdir()
        assert not (R/m.name).is_symlink(),m.name
    tf.extractall(R)
assert sha(R/'deploy_manifest.json')==NEW
for rel,row in read(R/'deploy_manifest.json')['files'].items():assert sha(R/rel)==row['sha256'],rel
record={'passed':True,'old_manifest':OLD,'new_manifest':NEW,'bundle_sha256':BUNDLE,'files':len(read(R/'deploy_manifest.json')['files']),'time':time.time(),'GPU_started':False}
(R/'audit/root_deployed_split_v2.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
