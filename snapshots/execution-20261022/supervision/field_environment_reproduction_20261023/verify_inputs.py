from pathlib import Path
import subprocess,json,shlex
from check_science import D,R
code=r'''
from pathlib import Path
import json,hashlib,sys,time
r=Path(ROOT);old=r.parent/'live_phase_pair_20261023';g=json.loads((r/'graphs/temporal_gain_field_graph.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();records=[]
manifest=Path(g['5']['inputs']['cache_manifest']);assert sha(manifest)==g['5']['inputs']['manifest_sha256'];m=json.loads(manifest.read_text())
for x in [m['conditioning']]+m['tensors']:
 p=Path(x['file']);h=sha(p);assert h==x['sha256'];records.append({'path':str(p),'sha256':h,'bytes':p.stat().st_size,'tensor_signature':x.get('tensor_signature')})
n=Path(g['6']['inputs']['noise_file']);assert sha(n)==g['6']['inputs']['noise_sha256']
contract=json.loads((old/'contracts/global_weak_contract.json').read_text());assert contract['noise_file_sha256']==sha(n)
core={}
for p,h in m['CPU_compatibility_sources'].items():
 actual=sha(r.parent/'core'/p);assert actual==h,p;core[p]=actual
model=json.loads((r/'MODEL_REHASH.json').read_text());st=Path(model['path']).stat();assert (st.st_ino,st.st_mtime_ns,st.st_size)==(model['inode'],model['mtime_ns'],model['bytes'])
assert hashlib.sha256(json.loads((r/'jobs.json').read_text())['jobs'][0]['metadata']['prompt'].encode()).hexdigest()==m['prompt_sha256']
out={'time':time.time(),'passed':True,'cache_manifest_sha256':sha(manifest),'payloads':records,'noise_file_sha256':sha(n),'noise_tensor_sha256':contract['noise_tensor_sha256'],'noise_contract_sha256':sha(old/'contracts/global_weak_contract.json'),'core_source_shas':core,'model_current_stat_matches_full_sha':model,'prompt_sha256':m['prompt_sha256'],'geometry':m['geometry'],'original_graph_inputs_identical_to_live_weak':True}
(r/'INPUT_IDENTITY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
'''.replace('ROOT',repr(R))
p=subprocess.run(['ssh','H3_HOST_RTX4090','python3 -c '+shlex.quote(code)],text=True,capture_output=True,timeout=90);assert p.returncode==0,p.stderr;o=json.loads(p.stdout);(D/'INPUT_IDENTITY.json').write_text(json.dumps(o,indent=2)+'\n');print({'passed':o['passed'],'payloads':len(o['payloads']),'core_files':len(o['core_source_shas'])})
