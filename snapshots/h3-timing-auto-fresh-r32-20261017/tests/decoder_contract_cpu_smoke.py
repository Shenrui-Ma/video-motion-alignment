"""Actual Comfy VAE regular/fallback entry contract without GPU or weights."""
import argparse,ast,importlib.util,json,os,sys,types
from pathlib import Path
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--comfy-root',required=True);a=p.parse_args()
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'scripts'),str(R/'extensions'),a.comfy_root]
os.environ['CUDA_VISIBLE_DEVICES']='';sys.argv=['decoder_cpu_smoke','--cpu','--disable-dynamic-vram','--use-pytorch-cross-attention']
import torch
torch.set_num_threads(1)
import comfy.options
comfy.options.enable_args_parsing()
from compatibility_bootstrap import install,install_video_compat
install();install_video_compat()
import comfy.sd
from comfy import model_management as mm
import decode_live_child as live
from H3AutomaticWindowRouter.dependencies import readout
from observer_import import t

# Native RGB/encoder loop is source-identical to the frozen decoder.
def function_source(path,name):
 s=Path(path).read_text();node=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name)
 return ast.get_source_segment(s,node)
assert function_source(R/'scripts/decode_x0.py','write_video')==function_source(R/'scripts/decode_live_child.py','write_video')
import tempfile
# Full real AV shapes, fresh immutable metadata; no historical missing-file assumption.
with tempfile.TemporaryDirectory(prefix='r27-decode-request-') as tmp:
 path=Path(tmp)/'native.pt'
 video=torch.arange(1*24*42*46*82,dtype=torch.float32).reshape(1,24,42,46,82)/10000
 audio=torch.arange(1*32*2*235,dtype=torch.float32).reshape(1,32,2,235)/10000
 raw=[readout.tensor_signature(video),readout.tensor_signature(audio*4)]
 meta={'physical_index':10,'branch':'native','nfe_index':10,'seed':2026101313,'sigma':.923,'sigma_next':.907,
       'condition_sha256':'fixture','reference_sha256':'reference','raw_stream_signatures':raw}
 torch.save({'video':video,'audio':audio,'metadata':meta},path)
 live.REQUEST=dict(meta,endpoint_file=str(path),endpoint_file_sha256=t.sha(path),normalized_stream_signatures=[readout.tensor_signature(v) for v in (video,audio)])
 live.REQUEST_SHA='cpu-fixture';payload=live.load_snapshot(path,readout)
 assert torch.equal(payload['video'],video) and torch.equal(payload['audio'],audio)
 live.REQUEST['sigma']=.5
 try:live.load_snapshot(path,readout)
 except ValueError as error:assert 'metadata differs' in str(error)
 else:raise AssertionError('wrong request sigma accepted')

class First:
 comfy_has_chunked_io=False
 def decode(self,samples,**kwargs):return samples+1
v=comfy.sd.VAE.__new__(comfy.sd.VAE)
v.device=v.output_device=torch.device('cpu');v.latent_dim=3;v.vae_dtype=torch.float16;v.disable_offload=True
v.first_stage_model=First();v.throw_exception_if_invalid=lambda:None;v.memory_used_decode=lambda shape,dtype:1
v.patcher=types.SimpleNamespace(get_free_memory=lambda device:10);v.vae_output_dtype=lambda:torch.float32
v.process_output=lambda x:None;v.extra_1d_channel=None;v.spacial_compression_decode=lambda:8
x=torch.arange(16,dtype=torch.float32).reshape(1,1,2,2,4)
names=('decode_tiled','decode_tiled_','decode_tiled_1d','decode_tiled_3d','_decode_tiled_owned');original={n:getattr(comfy.sd.VAE,n) for n in names if hasattr(comfy.sd.VAE,n)}
with patch.object(mm,'load_models_gpu',lambda *a,**k:None),patch.object(mm,'soft_empty_cache',lambda *a,**k:None),patch.object(mm,'get_total_memory',lambda *a,**k:100000):
 before=v.decode(x)
 live.install_fallback_guard(comfy.sd.VAE)
 try:
  assert torch.equal(before,v.decode(x))
  for owned in (False,True):
   v.handles_tiling=owned
   def oom(*a,**k):raise torch.OutOfMemoryError('CPU simulated OOM at actual regular decode')
   v.first_stage_model.decode=oom
   try:v.decode(x)
   except RuntimeError as error:assert 'R19 rejects OOM spatial tiled fallback' in str(error)
   else:raise AssertionError('fallback was not rejected')
 finally:
  for name,method in original.items():setattr(comfy.sd.VAE,name,method)
assert not torch.cuda.is_initialized()
print('R27_DECODER_CPU_SMOKE='+json.dumps({'success':True,'CUDA_initialized':False,'actual_VAE_regular_equal':True,'actual_3D_fallback_owned_and_unowned_rejected':True,'full_AV_request_streams_unchanged':True,'wrong_request_sigma_rejected':True,'native_RGB_writer_source_identical':True,'fallback_calls':live.FALLBACK['calls']}))
