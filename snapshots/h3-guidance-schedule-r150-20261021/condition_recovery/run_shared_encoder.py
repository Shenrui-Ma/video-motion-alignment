"""Restore three historical conditions with one Qwen model load, no VAE/DiT calls."""
import gc,hashlib,json,os,runpy,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
assert sys.argv[1:]==['--execute']
a=json.loads((ROOT/'BATCH_APPROVAL.json').read_text());assert a['approved'] and a['worker_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
clip=None;records=[];start=time.monotonic()
try:
 for cid in ['musk05','firefly06','sam07']:
  p=ROOT/cid/'encode_historical_condition.py';sys.argv=[str(p),'--execute']
  state=runpy.run_path(str(p),init_globals={'_SHARED_CLIP':clip,'_BATCH_MODE':True})
  clip=state['clip'];records.append(state['result']);del state;gc.collect()
 import comfy.model_management
 comfy.model_management.unload_all_models();comfy.model_management.soft_empty_cache()
 value={'passed':True,'qwen_model_loads':1,'qwen_encode_calls':len(records),'VAE_calls':0,'DiT_calls':0,'records':records,'seconds':time.monotonic()-start,'pid':os.getpid(),'unix':time.time()}
 (ROOT/'BATCH_RESULT.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value),flush=True)
finally:
 if 'comfy.model_management' in sys.modules:
  import comfy.model_management
  comfy.model_management.unload_all_models();comfy.model_management.soft_empty_cache()
