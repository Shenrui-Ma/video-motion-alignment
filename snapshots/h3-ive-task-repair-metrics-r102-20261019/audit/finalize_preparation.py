from pathlib import Path
import sys,json,re,base64,hashlib,time
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import *
from remote import read_paths
import render_native,render_pair
validate_static();c=config();remote=Path(c['producer_remote'])
paths=[str(remote/x) for x in ['deploy_manifest.json','configs/scientific_contract.json','configs/runtime.json']];actual=read_paths(paths)
for path,digest in zip(paths,[c['producer_seal_sha256'],c['producer_contract_sha256'],c['producer_runtime_sha256']]):require(actual[path]['sha256']==digest,'actual target producer differs')
save(R/'audit/ACTUAL_REMOTE_STATIC_BINDING.json',{'passed':True,'records':actual,'GPU_started':False,'execution_binding_created':False})
checks=[]
for name,module,mode,columns in [('synthetic_media_fixture',render_native,'Native-only',['source','native']),('synthetic_paired_media_fixture',render_pair,'Native+fixed guidance',['source','native','forced'])]:
 dest=R/'audit'/name;result=read(dest/'FIXTURE_RESULT.json')
 save(dest/'PRESENTATION.json',{'scope':'Synthetic display fixture only, not an experiment result','mode':mode,'columns':columns,**result['media']})
 p={'display_task':'合成色块展示校验','original_task':{'edit_prompt':'Synthetic fixture'},'prompt':'Synthetic fixture only.','valid_frames':18,'geometry':{'frames':20}}
 out=dest/'SYNTHETIC_FIXTURE.html'
 with patch.object(module,'info',return_value=p):module.publish('SYNTHETIC_FIXTURE',dest,out)
 encoded=re.findall(r'data:(?:video/mp4|image/jpeg);base64,([A-Za-z0-9+/=]+)',out.read_text());decoded=[hashlib.sha256(base64.b64decode(x,validate=True)).hexdigest() for x in encoded]
 expected=[x['sha256'] for x in result['media']['videos']+result['media']['contact_sheets']];require(decoded==expected,'embedded media differ')
 checks.append({'fixture':name,'passed':True,'embedded_assets':len(decoded),'html':bound(out),'asset_sha256':decoded})
save(R/'audit/HTML_EMBEDDING_VERIFIED.json',{'passed':True,'checks':checks,'scope':'Synthetic media only','UI_visual_verdict':'not_assessed: browser disabled in Work settings; no UI automation attempted'})
log=(R/'audit/CPU_TESTS_FINAL.txt').read_text();require('Ran 49 tests' in log and log.rstrip().endswith('OK'),'CPU regression evidence differs')
freeze=read(R/'CONSUMER_FREEZE.json')
save(R/'audit/FINAL_PREPARATION.json',{'schema':'r102-cpu-consumer-preparation-v1','passed':True,'consumer_freeze':bound(R/'CONSUMER_FREEZE.json'),'frozen_files':len(freeze['files']),'producer_seal_sha256':c['producer_seal_sha256'],'tests':{'passed':49,'log':bound(R/'audit/CPU_TESTS_FINAL.txt')},'actual_remote_static':bound(R/'audit/ACTUAL_REMOTE_STATIC_BINDING.json'),'fixture_html':bound(R/'audit/HTML_EMBEDDING_VERIFIED.json'),'scope':'Single CPU invocation only; no watcher/service/CUDA/producer verifier started. Actual execution binding awaits root STARTED. Official MF manifests bind media inputs only; scores pending.','created_unix':time.time()})
print(json.dumps({'freeze':bound(R/'CONSUMER_FREEZE.json'),'frozen_files':len(freeze['files']),'tests':49,'actual_remote_static_passed':True}))
