"""Stage SHA-checked new nodes/graphs; only the existing boundary guard activates."""
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

P=Path(__file__).resolve().parent
REMOTE='/data4/research-user/h3_runs/benchmark_schedule_20261022'
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_HOST_CONFIGURE_LOCALLY']
req=json.loads((P/'handoff_request.json').read_text())
assert req['status']=='ready' and req['cpu_tests']['passed']
assert len(req['base']['jobs'])==56 and len(req['pilots']['jobs']) in (4,8)
archive=io.BytesIO()
with tarfile.open(fileobj=archive,mode='w:gz') as tar:
    for asset in req['assets']:
        src=Path(asset['local'])
        assert hashlib.sha256(src.read_bytes()).hexdigest()==asset['sha256']
        relative=str(Path(asset['path']).relative_to(REMOTE))
        tar.add(src,arcname=relative,recursive=False)
    data=json.dumps(req,ensure_ascii=False,indent=2).encode()
    info=tarfile.TarInfo('request.staged.json');info.size=len(data)
    tar.addfile(info,io.BytesIO(data))
stage=REMOTE+'/innovation_handoff/overnight_20261023/stage'
subprocess.run(SSH+['mkdir -p '+shlex.quote(stage)+' && tar -xzf - -C '+shlex.quote(stage)],
               input=archive.getvalue(),check=True,timeout=90)
remote=r'''
import hashlib,importlib,json,os,shutil,sys,time
from pathlib import Path
r=Path(ROOT);d=r/'innovation_handoff/overnight_20261023';s=d/'stage'
req=json.loads((s/'request.staged.json').read_text())
receipt=json.loads((d/'activation.json').read_text()) if (d/'activation.json').exists() else {}
assert receipt.get('phase') not in ('armed','activated'), 'Already activated; do not change live files'
current=json.loads((r/'jobs.json').read_text());assert current==req['base']
states=json.loads((r/'queue_state/state.json').read_text())['jobs']
assert all(j['id'] not in states for j in req['pilots']['jobs']), 'New job already seen'
for a in req['assets']:
    relative=Path(a['path']).relative_to(r);source=s/relative;target=r/relative
    assert hashlib.sha256(source.read_bytes()).hexdigest()==a['sha256']
    if source.suffix=='.py':compile(source.read_bytes(),str(source),'exec')
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.stage_tmp');shutil.copyfile(source,tmp);os.replace(tmp,target)
sys.path.insert(0,str(r/'custom_nodes'))
classes={}
for name in ('H3FeatureGuidance','H3TemporalCoverageBlend'):
    classes.update(importlib.import_module(name).NODE_CLASS_MAPPINGS)
for job in req['pilots']['jobs']:
    graph=json.loads((r/job['graph']).read_text());node=graph['50'];cls=classes[node['class_type']]
    spec=cls.INPUT_TYPES()['required'];assert set(node['inputs'])==set(spec)
    for key,value in node['inputs'].items():
        declared=spec[key][0]
        if isinstance(declared,list):assert value in declared,(key,value)
    model=object();assert cls().apply(model,None,enabled=False)[0] is model
record={'status':'staged_validated','unix':time.time(),'assets':len(req['assets']),
        'job_ids':[j['id'] for j in req['pilots']['jobs']],
        'active_manifest_unchanged':json.loads((r/'jobs.json').read_text())==req['base']}
tmp=d/'request.json.tmp';tmp.write_text(json.dumps(req,ensure_ascii=False,indent=2));os.replace(tmp,d/'request.json')
(d/'package_validated.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
'''.replace('ROOT',repr(REMOTE))
out=subprocess.check_output(SSH+[shlex.join(['/data3/research-user/ComfyUI/.venv/bin/python','-c',remote])],timeout=120,text=True)
result=json.loads(out);(P/'PUBLISHED.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
