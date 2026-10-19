"""One source28289/Musk transfer; exact R42 graph and actual loader input binding."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REMOTE=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def audit_dir(value):
    p=Path(value)
    if not p.is_absolute() or p.is_symlink() or p.resolve()!=REMOTE/'audit':raise ValueError('audit root outside frozen R53 root')
    return p.resolve()
def expected_graph(parent,case):
    g=json.loads(json.dumps(parent))
    for node in g.values():
        for k,v in node['inputs'].items():
            if isinstance(v,str) and case['parent_root'] in v:node['inputs'][k]=v.replace(case['parent_root'],str(REMOTE))
    run=case['run_id']
    for key in ('6','51','52'):g[key]['inputs']['run_id']=run
    g['5']['inputs']['run_id']='r53_source_6980766_shared';g['51']['inputs']['source_run_id']='r53_source_6980766_shared'
    g['6']['inputs']['pair_id']=run+'_noise';g['14']['inputs']['filename_prefix']=run
    g['50']={'class_type':'H3AutomaticWindowRouter','inputs':{'model':['41',0],'positive':['51',0],'run_id':run,'audit_dir':str(REMOTE)+'/audit/counterfactual'}}
    return g

def validate_job(run,root=ROOT,inputs=True):
    root=Path(root);cases=read(root/'configs/protocol.json')['cases'];items=[x for x in cases if x['run_id']==run]
    if len(items)!=1:raise ValueError('run outside frozen registry')
    case=items[0];path=root/'configs'/f'{run}.json';g=read(path)
    if g!=expected_graph(read(root/case['parent_graph']),case):raise ValueError('graph differs from exact frozen parent transformation')
    if g['6']['inputs']['noise_seed']!=case['seed']:raise ValueError('actual graph seed mismatch')
    if inputs:
        for name,digest in read(root/'configs/input_hashes.json').items():
            src=root/'inputs'/name;dst=root/'input'/name
            if sha(src)!=digest:raise ValueError('immutable input mismatch: '+name)
            if dst.is_symlink():raise ValueError('loader input symlink')
            if not dst.exists():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
            if sha(dst)!=digest:raise ValueError('actual loader input mismatch: '+name)
    return {'case':case,'graph_sha256':sha(path)}
