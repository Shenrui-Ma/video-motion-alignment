"""Recreate a missing Qwen embedding once from the exact archived Qwen RGB inputs.

CPU check imports no CUDA and validates all archived inputs. GPU execution is an
explicit root-authorized predecessor-gated step; it performs no VAE or DiT call.
"""
import argparse,copy,hashlib,importlib.util,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--cpu-check',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args()
assert a.cpu_check != a.execute
cfg=json.loads((ROOT/'config.json').read_text());template=Path(cfg['runtime_template']);runtime=json.loads((template/'configs/runtime.json').read_text())
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(p,d):
 q=Path(p);tmp=q.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,q)
if a.cpu_check:os.environ['CUDA_VISIBLE_DEVICES']=''
else:
 approval=read(ROOT/'ENCODE_APPROVAL.json');assert approval['approved'] and approval['config_sha256']==sha(ROOT/'config.json') and approval['worker_sha256']==sha(__file__)
 assert os.environ['CUDA_VISIBLE_DEVICES']==runtime['gpu_uuid'];assert not (ROOT/'CACHE_RECOVERY_RESULT.json').exists()
sys.path[:0]=[runtime['dependencies'],runtime['core'],str(template/'scripts')]
sys.argv=['historical_condition','--use-pytorch-cross-attention','--disable-dynamic-vram','--reserve-vram','8','--enable-triton-backend']+(['--cpu'] if a.cpu_check else [])
from compatibility_bootstrap import install,install_video_compat
install();install_video_compat()
import comfy.options
comfy.options.enable_args_parsing()
import comfy.cli_args
import torch
assert not a.cpu_check or not torch.cuda.is_initialized()
def signature(t):
 v=t.detach().to('cpu').contiguous();return {'shape':list(v.shape),'dtype':str(v.dtype),'sha256':hashlib.sha256(v.view(torch.uint8).numpy().data).hexdigest()}
assert sha(cfg['historical_metadata'])==cfg['historical_metadata_sha256'];old=read(cfg['historical_metadata']);assert hashlib.sha256(old['prompt'].encode()).hexdigest()==cfg['prompt_sha256']
loaded={}
for rec in cfg['roles']:
 assert sha(rec['file'])==rec['sha256'],rec['role'];v=torch.load(rec['file'],map_location='cpu',weights_only=True);assert signature(v)==rec['tensor_signature'];loaded[rec['role']]=v
assert sha(cfg['noise_file'])==cfg['noise_sha256']
assert len(old['qwen_presentation'])==2 and old['qwen_presentation'][1]['sampling']['semantic_fps']==2
sampling=old['qwen_presentation'][1]['sampling'];assert sampling['phase_frames']==0
items=[{'type':'image','data':loaded['qwen_image_rgb']},{'type':'video','data':loaded['qwen_video_rgb'],'timestamps':sampling['sample_timestamps_seconds']}]
assert signature(items[0]['data'])==old['qwen_presentation'][0]['data']['tensor']
assert signature(items[1]['data'])=={k:old['qwen_presentation'][1]['actual_sampled_frames'][k] for k in ('shape','dtype','sha256')}
spec=importlib.util.spec_from_file_location('_recovery_event_audit',template/'extensions/H3EventAudit/__init__.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
class NoStore:
 def tensor(self,t,save=False):return signature(t)
if a.cpu_check:
 from comfy.text_encoders.minimax import MiniMaxH3Tokenizer
 tokens=MiniMaxH3Tokenizer().tokenize_with_weights(old['prompt'],minimax_ref_items=items)
 assert audit.token_ledger(tokens,NoStore())==old['tokenization_before_vision_expansion'],'CPU original tokenization differs'
 write(ROOT/'RECOVERY_CPU_CHECK.json',{'passed':True,'cuda_initialized':torch.cuda.is_initialized(),'original_Qwen_RGB_verified':True,'original_cached_VAE_tags_positions_verified':True,'no_models_loaded':True,'original_tokenization_equal':True,'config_sha256':sha(ROOT/'config.json'),'worker_sha256':sha(__file__),'unix':time.time()});print('CPU cache and exact Qwen presentation PASS');sys.exit(0)
from int8_row_chunking import install as install_rows
install_rows(log_path=ROOT/'int8_row_chunking.jsonl')
import folder_paths
folder_paths.add_model_folder_path('text_encoders',str(Path(runtime['models'])/'text_encoders'))
folder_paths.add_model_folder_path('text_encoders',str(Path(runtime['models'])/'clip'))
folder_paths.add_model_folder_path('embeddings',str(Path(runtime['models'])/'embeddings'))
import nodes
start=time.monotonic();clip=globals().get('_SHARED_CLIP')
if clip is None:clip=nodes.CLIPLoader().load_clip('qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors','minimax','default')[0]
load_seconds=time.monotonic()-start
tokens=clip.tokenize(old['prompt'],minimax_ref_items=items)
assert audit.token_ledger(tokens,NoStore())==old['tokenization_before_vision_expansion'],'original tokenization or Qwen RGB differs'
start=time.monotonic()
with torch.inference_mode():positive=clip.encode_from_tokens_scheduled(tokens)
encode_seconds=time.monotonic()-start
assert len(positive)==1;embedding,meta=positive[0];sig=signature(embedding);tags=signature(meta['minimax_token_tags'])
assert tags=={k:old['token_tags'][k] for k in ('shape','dtype','sha256')},'token tags changed';assert sig['shape']==old['conditioning_embedding']['shape'] and sig['dtype']==old['conditioning_embedding']['dtype']
name=hashlib.sha256(json.dumps(sig,sort_keys=True).encode()).hexdigest()+'.pt';path=ROOT/name;assert not path.exists();torch.save(embedding.detach().cpu().contiguous(),path)
new=copy.deepcopy(old);new['conditioning_embedding']={**sig,'tensor_file':'tensor_blobs/'+name};write(ROOT/'recovered_conditioning.json',new)
match=sig['sha256']==old['conditioning_embedding']['sha256']
result={'schema':'r150-recovered-Qwen-condition-v1','passed':True,'candidate_id':cfg['candidate_id'],'original_embedding_signature':old['conditioning_embedding'],'actual_embedding_signature':sig,'same_historical_embedding':match,'requires_shared_cache_native':not match,'embedding_file':str(path),'embedding_file_sha256':sha(path),'metadata_file':str(ROOT/'recovered_conditioning.json'),'metadata_sha256':sha(ROOT/'recovered_conditioning.json'),'input_config_sha256':sha(ROOT/'config.json'),'worker_sha256':sha(__file__),'original_tokenization_equal':True,'reference_vae_calls':0,'dit_forward_calls':0,'qwen_encode_calls':1,'load_seconds':load_seconds,'encode_seconds':encode_seconds,'pid':os.getpid(),'torch':torch.__version__,'unix':time.time()}
write(ROOT/'CACHE_RECOVERY_RESULT.json',result);print(json.dumps(result),flush=True)
if not globals().get('_BATCH_MODE', False):
 import comfy.model_management
 comfy.model_management.unload_all_models();comfy.model_management.soft_empty_cache()
