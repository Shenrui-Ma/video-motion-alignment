from pathlib import Path
import hashlib,json,shutil
r=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
s=Path('/data5/researcher/h3_runs/r53_root_stage')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(r/'deploy_manifest.json')=='d7ce599207e1be4842b4428edb8222ac03540160e041bf5283500c208f6e0734'
assert sha(s/'deploy_manifest.json')=='6576342c90a281bb59be584987a222b4dd3ad0affeb673ca8a21bf86915c5527'
assert not (r/'processes/service.json').exists()
assert not Path('/proc/38332').exists()
backup=r/'audit/root_admin_revision2_before';backup.mkdir()
for name in ['admission_template.json','observer_bindings.json','PARENT_CLOSURE.json']:
 shutil.copyfile(r/'configs'/name,backup/name)
 shutil.copyfile(s/name,r/'configs'/name)
shutil.copyfile(r/'deploy_manifest.json',backup/'deploy_manifest.json')
shutil.copyfile(s/'deploy_manifest.json',r/'deploy_manifest.json')
a=json.loads((r/'configs/admission.json').read_text());shutil.copyfile(r/'configs/admission.json',backup/'admission.json');a['existing_comfy_port']=None;(r/'configs/admission.json').write_text(json.dumps(a,indent=2)+'\n')
m=json.loads((r/'deploy_manifest.json').read_text())
for name,e in m['files'].items():assert sha(r/name)==e['sha256'],name
print(json.dumps(dict(files=len(m['files']),existing_comfy_port=a['existing_comfy_port'],prior_supervisor_absent=True,scientific_change=False)))
