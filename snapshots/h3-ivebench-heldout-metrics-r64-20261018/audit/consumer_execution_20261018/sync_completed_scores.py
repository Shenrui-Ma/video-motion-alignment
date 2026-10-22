"""Pull only completed small score/tracker/audit evidence; preserve local reviews."""
from pathlib import Path
import hashlib
import json
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
REMOTE = '/data3/researcher/h3_runs/ivebench_heldout_metrics_r64_20261018'
code = '''
from pathlib import Path
import hashlib, io, json, sys, tarfile
r=Path(REMOTE)
paths=[]
for base in ('tracks','results','audit/root_finish_remaining_attempt1','audit/root_remaining_targets_attempt1'):
 for p in (r/base).rglob('*'):
  if p.is_file() and p.name != 'HUMAN_REVIEW.json' and p.suffix in ('.json','.npz','.log'):
   assert p.stat().st_size < 2000000
   paths.append(p)
manifest=[{'path':str(p.relative_to(r)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths)]
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as t:
 for p in sorted(paths): t.add(p,arcname=str(p.relative_to(r)))
 raw=(json.dumps(manifest,indent=2)+'\\n').encode()
 info=tarfile.TarInfo('REMOTE_SMALL_EVIDENCE_MANIFEST.json'); info.size=len(raw)
 t.addfile(info,io.BytesIO(raw))
'''.replace('Path(REMOTE)', 'Path(' + repr(REMOTE) + ')')
archive = Path(__file__).with_name('all_four_completed_scores_receipts.tar')
with archive.open('wb') as out:
    subprocess.run(['ssh', 'H3_SERVER_B', 'python3 -c ' + shlex.quote(code)], stdout=out, check=True)
with tarfile.open(archive) as t:
    manifest=json.load(t.extractfile('REMOTE_SMALL_EVIDENCE_MANIFEST.json'))
    for item in manifest:
        name=item['path']; assert not name.startswith('/') and '..' not in Path(name).parts
        data=t.extractfile(name).read()
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
        dst=ROOT/name
        if dst.exists(): assert dst.read_bytes()==data, 'Refusing changed archived evidence: '+name
        else: dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(data)
record={'archive':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(), 'files':manifest}
Path(__file__).with_name('ALL_FOUR_SCORE_SYNC.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'files':len(manifest),'archive_bytes':archive.stat().st_size,'sha256':record['archive_sha256']}))
