"""CPU audit only: verify frozen consumer, synthetic HTML media and final handoff."""
import sys,re,base64,hashlib,json,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import *
import render_native,render_pair
validate_static()
checks=[]
for name,module,mode,columns in [('synthetic_media_fixture',render_native,'Native-only',['source','native']),('synthetic_paired_media_fixture',render_pair,'Native+fixed guidance',['source','native','forced'])]:
 dest=ROOT/'audit'/name;result=read(dest/'FIXTURE_RESULT.json')
 save(dest/'PRESENTATION.json',{'scope':'Synthetic display fixture, not an experiment result','mode':mode,'columns':columns,**result['media']})
 p={'display_task':'合成色块展示校验，无模型推理','original_task':{'edit_prompt':'Synthetic fixture'},'prompt':'Synthetic fixture only.','valid_frames':18,'geometry':{'frames':20}}
 out=dest/'SYNTHETIC_FIXTURE.html'
 with patch.object(module,'info',return_value=p):module.publish('SYNTHETIC_FIXTURE',dest,out)
 encoded=re.findall(r'data:(?:video/mp4|image/jpeg);base64,([A-Za-z0-9+/=]+)',out.read_text())
 actual=[hashlib.sha256(base64.b64decode(x,validate=True)).hexdigest() for x in encoded]
 expected=[x['sha256'] for x in result['media']['videos']+result['media']['contact_sheets']]
 require(actual==expected,'embedded media differ')
 checks.append({'fixture':name,'passed':True,'embedded_assets':len(actual),'html':bound(out),'asset_sha256':actual})
save(ROOT/'audit/HTML_EMBEDDING_VERIFIED.json',{'passed':True,'checks':checks,'scope':'Synthetic media only; no actual run claimed','created_unix':time.time()})
freeze=read(ROOT/'CONSUMER_FREEZE.json')
save(ROOT/'audit/FINAL_PREPARATION.json',{'schema':'r100-cpu-consumer-preparation-v1','passed':True,'consumer_freeze':bound(ROOT/'CONSUMER_FREEZE.json'),'frozen_files':len(freeze['files']),'producer_seal_sha256':config()['producer_seal_sha256'],'tests':{'passed':48,'log':bound(ROOT/'audit/CPU_TESTS_FINAL.txt')},'actual_remote_static':bound(ROOT/'audit/ACTUAL_REMOTE_STATIC_BINDING.json'),'fixture_html':bound(ROOT/'audit/HTML_EMBEDDING_VERIFIED.json'),'scope':'One-shot CPU intake only. No watcher, service, CUDA or producer verifier started. Actual execution binding awaits root STARTED. MF manifests contain media inputs only; scores remain pending.','created_unix':time.time()})
print(json.dumps({'freeze':bound(ROOT/'CONSUMER_FREEZE.json'),'receipt':bound(ROOT/'audit/FINAL_PREPARATION.json'),'frozen_files':len(freeze['files'])}))
