"""Root-authorized device rebinding only: preserve v2, move decoder GPU2 to GPU0."""
from pathlib import Path
import hashlib,json,shutil,tarfile
R=Path(__file__).resolve().parents[1]
OLD='GPU-REDACTED';NEW='GPU-REDACTED'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
assert sha(R/'deploy_manifest.json')=='13d2842849143f4d30122e51a8dd1ab05e3b083f9f1af7de8777f4ec35798b93'
manifest=read(R/'deploy_manifest.json')
assert all(sha(R/n)==v['sha256'] for n,v in manifest['files'].items())
dest=R/'audit/revisions/producer_v2';dest.mkdir(parents=True,exist_ok=False)
shutil.copy2(R/'deploy_manifest.json',dest/'deploy_manifest.json')
with tarfile.open(dest/'sealed_producer.tar.gz','x:gz') as tar:
 for rel in manifest['files']:tar.add(R/rel,arcname=rel)
 tar.add(R/'deploy_manifest.json',arcname='deploy_manifest.json')
write(dest/'PRESERVATION.json',{'schema':'r50-producer-v2-preservation','original_manifest_sha256':sha(dest/'deploy_manifest.json'),'sealed_files_verified':len(manifest['files']),'archive_sha256':sha(dest/'sealed_producer.tar.gz'),'reason':'GPU2 acquired by another user; root reassigned dedicated decoder to idleGPU0; v2 had no GPU inference or decoder gate'})
e=R/'configs/engineering_v3';e.mkdir(exist_ok=False);shutil.copy2(R/'configs/protocol.json',e/'previous_protocol.json')
p=read(R/'configs/protocol.json');assert p['resources']['decoder_uuid']==OLD;p['resources']['decoder_uuid']=NEW;write(R/'configs/protocol.json',p);shutil.copy2(R/'configs/protocol.json',R/'PROTOCOL.json');protocol_sha=sha(R/'configs/protocol.json')
spec=read(R/'configs/engineering_revision_v2.json');spec.update(schema='r50-resource-placement-revision-v3',previous_manifest_sha256=sha(dest/'deploy_manifest.json'),previous_protocol_file='configs/engineering_v3/previous_protocol.json',previous_protocol_sha256=sha(e/'previous_protocol.json'),kernel_protocol_sha256=spec['previous_protocol_sha256'],prior_engineering_revision_file='configs/engineering_revision_v2.json',prior_engineering_revision_sha256=sha(R/'configs/engineering_revision_v2.json'),administrative_change='decoder GPU2 to GPU0 only; other user now owns GPU2',pending_runtime_proof='same final Native endpoint full158 decoded on GPU0; previous GPU3 frame RGB and tensor hashes must match')
spec['placement']['decoder_GPU']=NEW;write(R/'configs/engineering_revision_v3.json',spec)
for name in ['extensions/H3AutomaticWindowRouter/transport.py','scripts/service.py','scripts/prelaunch_gates.py']:
 f=R/name;text=f.read_text().replace(OLD,NEW)
 if name.endswith('transport.py'):text=text.replace("PROTOCOL_SHA='e8058874b94bce9673fe82773d3b75aecb3cdc92d12f9469975afc56466c6d73'",'PROTOCOL_SHA='+repr(protocol_sha))
 if name.endswith('prelaunch_gates.py'):
  text=text.replace('engineering_revision_v2.json','engineering_revision_v3.json').replace('resource_admission_v2.json','resource_admission_v3.json').replace('known_endpoint_158_split_gate.json','known_endpoint_158_split_v3_gate.json').replace("revision['previous_protocol_sha256']","revision['kernel_protocol_sha256']").replace('r50-root-two-GPU-resource-admission-v2','r50-root-two-GPU-resource-admission-v3').replace('GPU2 isolated full158','GPU0 isolated full158')
 f.write_text(text)
f=R/'scripts/known_endpoint_158_gate.py';text=f.read_text().replace('known_endpoint_158_split_v2','known_endpoint_158_split_v3').replace('dedicated GPU2','dedicated GPU0').replace('dedicated_GPU2','dedicated_GPU0');f.write_text(text)
f=R/'scripts/build_manifest.py';text=f.read_text().replace("'audit/revisions/producer_v1/PRESERVATION.json','audit/ENGINEERING_REVISION_v2_CPU_CHECK.json'","'audit/revisions/producer_v1/PRESERVATION.json',\n           'audit/revisions/producer_v2/deploy_manifest.json','audit/revisions/producer_v2/sealed_producer.tar.gz',\n           'audit/revisions/producer_v2/PRESERVATION.json','audit/ENGINEERING_REVISION_v3_CPU_CHECK.json'").replace('r50-immutable-five-case-deploy-v2-split-decoder','r50-immutable-five-case-deploy-v3-split-decoder-GPU0').replace("sha(ROOT/'configs/engineering_revision_v2.json')","sha(ROOT/'configs/engineering_revision_v3.json')").replace("'previous_deploy_manifest_sha256':sha(ROOT/'audit/revisions/producer_v1/deploy_manifest.json')","'previous_deploy_manifest_sha256':sha(ROOT/'audit/revisions/producer_v2/deploy_manifest.json')");f.write_text(text)
write(R/'FREEZE.json',{'schema':'r50-production-science-freeze-v3-resource-placement','files':{'PROTOCOL.json':protocol_sha,'configs/protocol.json':protocol_sha},'prior_manifest_sha256':sha(dest/'deploy_manifest.json'),'science_change':'none; only decoder GPU UUID changed in protocol resources'})
f=R/'README.txt';text=f.read_text().replace('Engineering revision v2:','Engineering revision v3:').replace('GPU2 executes','GPU0 executes');f.write_text(text+'\nV2 was preserved before GPU2 became occupied by another user. V3 changes only decoder device binding and versioned administrative gate paths.\n')
f=R/'audit/build_split_resource_admission_v3_proposed.py';text=(R/'audit/build_split_resource_admission_proposed.py').read_text().replace(OLD,NEW).replace('resource_admission_v2.json','resource_admission_v3.json').replace('engineering_revision_v2.json','engineering_revision_v3.json').replace('known_endpoint_158_split_gate.json','known_endpoint_158_split_v3_gate.json').replace('r50-root-two-GPU-resource-admission-v2','r50-root-two-GPU-resource-admission-v3').replace('GPU2','GPU0');f.write_text(text)
print(json.dumps({'protocol_sha256':protocol_sha,'preserved_v2_sha256':sha(dest/'sealed_producer.tar.gz')}))
