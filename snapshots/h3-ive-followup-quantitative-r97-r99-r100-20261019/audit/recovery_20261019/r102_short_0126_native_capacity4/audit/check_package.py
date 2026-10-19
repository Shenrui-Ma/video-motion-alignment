"""Bounded CPU package validation; no imports initialize CUDA."""
import ast,copy,json,sys
from pathlib import Path
r=Path(sys.argv[1]).resolve();sys.path.insert(0,str(r/'scripts'));import common as c
c.verify_seal();c.verify_runtime();cases=list((r/'cases').iterdir());assert len(cases)==1
case=cases[0];s=c.read(case/'SPEC.json');m=c.read(case/'INPUTS.json');g=c.read(case/s['gate']['file']);c.validate_gate(s,g)
assert set(m['roles'])=={'source',*s['targets']}
assert c.sha(case/'SPEC.json')==m['spec_sha256'] and m['gate_sha256']==c.sha(case/s['gate']['file'])
for row in m['roles'].values():
 assert c.sha(case/row['full_file'])==row['full_sha256'] and c.sha(case/row['score_file'])==row['score_sha256']
 assert len(row['score_frame_md5'])==m['valid_frames']
def setvalue(q,path,value):
 for k in path[:-1]:q=q[k]
 q[path[-1]]=value
first=next(iter(s['targets'].values()))
for path,value in [(['passed'],False),(first['gate_video_keys']+['sha256'],'0'*64),(s['gate'].get('valid_frame_keys',['valid_frames']),-1),(first.get('gate_run_keys',['run_id']),'other')]:
 q=copy.deepcopy(g);setvalue(q,path,value)
 try:c.validate_gate(s,q)
 except ValueError:pass
 else:raise AssertionError('invalid gate accepted '+str(path))
if s.get('source_cache_reuse'):
 c.validate_reuse(s,m,c.read(case/'tracks/source/REPORT.json'),c.sha(case/'tracks/source/REPORT.json'),c.sha(case/'tracks/source/tracks.npz'))
 assert c.read(case/'SOURCE_REUSE_RECEIPT.json')['passed'] is True
w=(r/'audit/run_authorized.py').read_text();ast.parse(w)
assert c.sha(case/'INPUTS.json') in w and f'[1,{m["valid_frames"]},100,2]' in w
assert 'check_mf_capacity(12)' in w and '+600' in w and '1251962' in w and '15965864' in w
assert 'torch' not in sys.modules
print(json.dumps({'passed':True,'case':case.name,'valid_frames':m['valid_frames'],'negative_gate_checks':4,'source_cache_reuse':bool(s.get('source_cache_reuse')),'CUDA_started':False}))
