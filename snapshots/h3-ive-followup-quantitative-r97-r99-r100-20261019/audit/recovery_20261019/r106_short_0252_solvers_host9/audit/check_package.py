from pathlib import Path
import sys,json
r=Path(sys.argv[1]).resolve();sys.path.insert(0,str(r/'scripts'));import common as c
c.verify_seal();c.verify_runtime();case=next((r/'cases').iterdir());s=c.read(case/'SPEC.json');m=c.read(case/'INPUTS.json');assert not s.get('source_cache_reuse');c.validate_gate(s,c.read(case/s['gate']['file']))
assert m['valid_frames']==98 and set(m['roles'])=={'source','euler','res_multistep'}
for v in m['roles'].values():assert c.sha(case/v['full_file'])==v['full_sha256'] and c.sha(case/v['score_file'])==v['score_sha256']
assert 'torch' not in sys.modules;assert not (r/'audit/run_authorized.py').exists();print(json.dumps({'passed':True,'CUDA_started':False,'frame_count':98,'roles':list(m['roles']),'input_sha256':c.sha(case/'INPUTS.json')}))
