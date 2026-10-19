"""CPU admission checks for copied evaluation contracts and failure guards."""
import ast, copy, importlib.util, json, sys
from pathlib import Path

r = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(r/'scripts'))
import common as c
c.verify_seal()
c.verify_runtime()
cases = list((r/'cases').iterdir())
assert len(cases) == 1
case = cases[0]
s = c.read(case/'SPEC.json')
g = c.read(case/s['gate']['file'])
m = c.read(case/'INPUTS.json')
c.validate_gate(s,g)
assert set(m['roles']) == {'source','native'}
assert c.sha(case/'SPEC.json') == m['spec_sha256']
assert m['gate_sha256'] == c.sha(case/s['gate']['file'])
for row in m['roles'].values():
    assert c.sha(case/row['full_file']) == row['full_sha256']
    assert c.sha(case/row['score_file']) == row['score_sha256']
    assert len(row['score_frame_md5']) == m['valid_frames']
for mutation in ('failed','sha','frames','run'):
    q=copy.deepcopy(g)
    if mutation=='failed': q['passed']=False
    if mutation=='sha': q['runs']['native']['video']['sha256']='0'*64
    if mutation=='frames': q['runs']['native']['valid_frames']+=1
    if mutation=='run': q['runs']['native']['run_id']='other'
    try:c.validate_gate(s,q)
    except ValueError:pass
    else:raise AssertionError(mutation+' was accepted')
wrapper=(r/'audit/run_authorized.py').read_text()
ast.parse(wrapper)
assert c.sha(case/'INPUTS.json') in wrapper
assert f'[1,{m["valid_frames"]},100,2]' in wrapper
assert '>=12*1024**3' in wrapper
assert "['source','native']" in wrapper
assert 'timeout=600' in wrapper
assert 'torch' not in sys.modules
print(json.dumps({'passed':True,'case':case.name,'files':len(c.read(r/'SEAL.json')['files']),'negative_gate_checks':4,'full_input_hashes':True,'numeric_runtime_unchanged':True,'preload_margin_GiB':12,'CUDA_started':False}))
