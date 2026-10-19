from pathlib import Path
import hashlib,json,subprocess,ast
R=Path(__file__).resolve().parents[1];P=R/'host41_package';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();PYTHON='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
for p in [*(P/'scripts').glob('*.py'),P/'audit/run_authorized.py',P/'audit/check_package.py']:ast.parse(p.read_text())
q=json.loads(subprocess.check_output([PYTHON,str(P/'audit/check_raw_capacity.py'),str(P)],text=True));(P/'audit/CAPACITY_BOUNDARY_CHECK.json').write_text(json.dumps(q,indent=2)+'\n')
inherit=json.loads((P/'configs/NUMERIC_INHERITANCE.json').read_text());assert all(sha(P/'runtime/official_metric'/n)==h for n,h in inherit['files'].items())
files={str(p.relative_to(P)):sha(p) for p in sorted(P.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='CONSUMER_FREEZE.json'};(P/'CONSUMER_FREEZE.json').write_text(json.dumps({'schema':'r90-flex-author-code-frozen-numerics-v1','files':files},indent=2)+'\n');print(json.dumps({'freeze_sha256':sha(P/'CONSUMER_FREEZE.json'),'files':len(files),'capacity_tests':q['test_count'],'GPU_started':False}))
