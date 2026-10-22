# Execute only AFTER paired finalization and root review. This uploads and performs CPU verification only.
set -eu
R141B_PACKAGE=/Users/researcher/DevProjects/h3-oxygen-generic-retention-mf-r141b-20261020
R141B_REMOTE=/data4/researcher/h3_runs/ive_oxygen_generic_retention_mf_r141b_20261020
python3 - "$R141B_PACKAGE" <<'CHECK'
from pathlib import Path
import json,hashlib,sys
p=Path(sys.argv[1]); h=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
s=json.loads((p/'SEAL.json').read_text()); r=json.loads((p/'ROOT_REVIEW.json').read_text())
assert s['final_inputs_bound'] is True
assert r['passed'] is True and r['GPU_execution_authorized'] is True
assert r['seal_sha256']==h(p/'SEAL.json')
assert r['gpu']==json.loads((p/'configs/RUNTIME.json').read_text())['gpu']
assert [j['role'] for j in json.loads((p/'configs/PLAN.json').read_text())['jobs']]==['native','forced']
files=(p/'audit/DEPLOY_FILES_AFTER_FINALIZE.txt').read_text().splitlines()
assert len(files)==len(set(files))
reuse=json.loads((p/'audit/REMOTE_REUSE_PLAN.json').read_text())
for rel in files:
 assert not Path(rel).is_absolute() and '..' not in Path(rel).parts
 assert rel not in reuse and not rel.startswith('runtime/')
 assert (p/rel).is_file()
 if rel in s['files']: assert h(p/rel)==s['files'][rel]
assert all(h(p/rel)==expected for rel,expected in s['files'].items())
print(json.dumps({'passed':True,'upload_files':len(files),'bytes':sum((p/r).stat().st_size for r in files),'root_review_sha256':h(p/'ROOT_REVIEW.json')}))
CHECK
ssh H3_SERVER_B "mkdir -p '$R141B_REMOTE'"
rsync -a --files-from="$R141B_PACKAGE/audit/DEPLOY_FILES_AFTER_FINALIZE.txt" \
 "$R141B_PACKAGE/" "H3_SERVER_B:$R141B_REMOTE/"
rsync -a "$R141B_PACKAGE/ROOT_REVIEW.json" "H3_SERVER_B:$R141B_REMOTE/ROOT_REVIEW.json"
ssh H3_SERVER_B "cd '$R141B_REMOTE' && PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/materialize_existing.py && PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/verify_inputs.py"
# Stop here. Fresh resource admission and the GPU runner are separate commands in RUNBOOK.md.
