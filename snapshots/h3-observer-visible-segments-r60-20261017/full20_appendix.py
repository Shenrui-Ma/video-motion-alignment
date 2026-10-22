"""Same frozen replay, with a separately bound later R50 observation export."""
import argparse
import copy
from pathlib import Path
import shutil
import diagnose as d

ROOT=Path(__file__).resolve().parent
HERE=ROOT/'appendix_r50_full20'
INDEX=ROOT.parent/'h3-timing-flexiact-auto-r50-retry-20261017/analysis/postrun/audit/live_pose_export/1792246528856601000/INDEX.json'
EXPECTED='3c00995222803e38f69393469712969078614e1d157cc9b4e2a2614cf0efb646'


def freeze():
    protocol=d.verified()
    assert d.sha(INDEX)==EXPECTED
    new=d.read(INDEX);old=d.read(protocol['existing_trajectories']['r50'])
    assert len(new['rows'])==20 and len(old['rows'])==17
    assert new['case']==old['case'] and new['source_pose']['sha256']==old['source_pose']['sha256']
    for a,b in zip(old['rows'],new['rows']):
        for field in ('denoising_index','run_id','original_decision_committed','original_decision','endpoint_file_sha256','observer'):
            assert a[field]==b[field],field
        for field in ('target_pose','request','response'):
            assert a[field]['sha256']==b[field]['sha256'],field
    HERE.mkdir(exist_ok=False)
    shutil.copytree(ROOT/'frozen',HERE/'frozen')
    p=copy.deepcopy(protocol)
    p['schema']='r60-full20-existing-pose-appendix-v1'
    p['parent_protocol_sha256']=d.sha(ROOT/'PROTOCOL.json')
    p['existing_trajectories']['r50']=str(INDEX)
    p['prefix17_exact_inheritance']=True
    for path in (INDEX,Path(__file__),*sorted((HERE/'frozen').rglob('*.py'))):
        p['bindings'].append({'original':str(path),'path':str(path),'sha256':d.sha(path)})
    for relative,record in new['files'].items():
        path=INDEX.parent/relative
        assert d.sha(path)==record['sha256']
        p['bindings'].append({'original':str(path),'path':str(path),'sha256':d.sha(path)})
    d.write(HERE/'PROTOCOL.json',p)
    print(d.sha(HERE/'PROTOCOL.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--family',choices=['upper','forearm']);a=p.parse_args()
    if a.freeze:freeze()
    else:
        # Reuse the byte-frozen implementation; only its documented audit/input root changes.
        # Each invocation is a fresh process; original prefix17 and main protocol remain intact.
        d.HERE=HERE
        d.replay('r50',a.family)
