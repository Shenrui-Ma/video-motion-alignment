from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
assert not (root/'CONSUMER_FREEZE.json').exists()
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['scripts','tests','configs'] for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
c=json.loads((root/'configs/contract.json').read_text())
(root/'CONSUMER_FREEZE.json').write_text(json.dumps({'schema':'r101-cpu-consumer-freeze-v1','producer_seal_sha256':c['producer_seal_sha256'],'files':files},ensure_ascii=False,indent=2)+'\n')
print(len(files),hashlib.sha256((root/'CONSUMER_FREEZE.json').read_bytes()).hexdigest())
