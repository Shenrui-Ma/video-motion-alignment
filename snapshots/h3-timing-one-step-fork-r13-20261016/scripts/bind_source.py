"""Bind completed R10 files; reads source only, writes only this R13 root."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
RUN='r10_s05_fixed_full_probe'


def bind(source_root, output_root=ROOT):
    src=Path(source_root).resolve();out=Path(output_root).resolve()
    assert out==ROOT, 'writes restricted to this R13 checkout'
    destination=out/'configs/source_manifest.json'
    previous=json.loads(destination.read_text())
    assert previous['status']=='pending','source binding is already sealed'
    raw=json.loads((src/f'audit/counterfactual/{RUN}.json').read_text())
    assert raw['status']=='complete'
    c=raw['counterfactual']
    rows={(r['physical_index'],r['branch']):r for r in c['branches']}
    inputs={r['physical_index']:r for r in c['inputs']}
    files=[f'audit/counterfactual/{RUN}.json','analysis/parent_pair_check.json',
           f'audit/{RUN}_conditioning.json','configs/runtime_provenance.json','configs/protocol.json',
           'configs/r10_s05_fixed_full_probe.json','extensions/H3CounterfactualRouter/core.py']
    for n in [6,10,14]:
        for row in [inputs[n],rows[n,'native'],rows[n,'full'],rows[n+1,'native']]:
            rel=f'audit/counterfactual/{RUN}_snapshots/'+Path(row['file']).name
            assert hashlib.sha256((src/rel).read_bytes()).hexdigest()==row['file_sha256']
            files.append(rel)
    protocol=json.loads((src/'configs/protocol.json').read_text())
    assert protocol['resources']['gpu_uuid']=='GPU-REDACTED'
    assert protocol['resources']['remote_root']=='/data5/researcher/h3_runs/timing_counterfactual_r10_20261016'
    assert hashlib.sha256((src/'extensions/H3CounterfactualRouter/core.py').read_bytes()).hexdigest()==\
        hashlib.sha256((out/'extensions/H3CounterfactualRouter/core.py').read_bytes()).hexdigest()
    runtime=json.loads((src/'configs/runtime_provenance.json').read_text())
    assert all(runtime['core_matches'].values()), 'source runtime core verification failed'
    manifest={'schema':'h3-r13-source-binding-v1','status':'bound','source_root':str(src),'source_run':RUN,
        'bound_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_uuid':protocol['resources']['gpu_uuid'],
        'files':{rel:hashlib.sha256((src/rel).read_bytes()).hexdigest() for rel in sorted(set(files))},
        'selection_unchanged':True,'source_indices':[6,10,14]}
    temporary=out/'configs/source_manifest_candidate.json'
    assert not temporary.exists(),'retain prior candidate evidence before retry'
    temporary.write_text(json.dumps(manifest,indent=2)+'\n')
    sys.path.insert(0,str(out/'extensions'))
    from H3OneStepForkAudit.core import Source
    bound=Source(temporary)
    for n in [6,10,14]:
        bound.input(n)
        for step,branch in [(n,'native'),(n,'full'),(n+1,'native')]:bound.endpoint(step,branch)
    (out/'audit/source_binding_pending_original.json').write_text(destination.read_text())
    temporary.replace(destination)
    return {'bound':True,'files':len(files),'source_manifest_sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',required=True)
    print(json.dumps(bind(p.parse_args().source_root),indent=2))
