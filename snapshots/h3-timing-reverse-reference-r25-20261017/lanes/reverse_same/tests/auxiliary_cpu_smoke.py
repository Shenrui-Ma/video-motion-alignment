"""CPU current Noise node against archived actual R3 AV noise SHA.
R3's clean embedding has a raw SHA but no archived tensor_file; this gate makes
no claim of reloading that historical embedding or exercising its numeric hash.
"""
import argparse,asyncio,importlib.util,json,os,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch

def main():
 p=argparse.ArgumentParser();p.add_argument('--comfy-root',required=True);p.add_argument('--compat-bootstrap',required=True);a=p.parse_args();r=Path(__file__).resolve().parents[1];start=time.monotonic();os.environ['CUDA_VISIBLE_DEVICES']=''
 import torch
 torch.set_num_threads(1);torch.set_num_interop_threads(1);sys.path[:0]=[str(r/'scripts'),a.comfy_root];sys.argv=['r25_aux_cpu','--cpu','--disable-dynamic-vram','--use-pytorch-cross-attention']
 import comfy.options
 comfy.options.enable_args_parsing();spec=importlib.util.spec_from_file_location('r25_aux_compat',a.compat_bootstrap);compat=importlib.util.module_from_spec(spec);spec.loader.exec_module(compat);compat.install();compat.install_video_compat()
 import nodes
 for n in ('H3EventAudit','H3PairAudit'):assert asyncio.run(nodes.load_custom_node(str(r/'extensions'/n),module_parent='custom_nodes'))
 import r25_contract as c
 from comfy.nested_tensor import NestedTensor
 Noise=nodes.NODE_CLASS_MAPPINGS['H3EventAuditNoise'];noise_module=sys.modules[Noise.__module__]
 old=c.read(r/'parent_evidence/full_6to14_conditioning.json');oldnoise=c.read(r/'parent_evidence/full_6to14_noise.json')
 target={'samples':NestedTensor([torch.zeros(shape) for shape in old['target_latent_shapes']])};run=c.run_name('reverse_block');g=c.expected_graph(r,'reverse_block')
 with tempfile.TemporaryDirectory(prefix='r25-aux-real-') as tmp:
  folder=Path(tmp);rng=torch.get_rng_state().clone()
  with patch.object(c,'audit_dir',return_value=folder):
   noise=Noise().get_noise(c.SEED,g['6']['inputs']['audit_dir'],run,c.PAIR)[0];first=noise.generate_noise(target);after_native_generation=torch.get_rng_state().clone();second=noise.generate_noise(target)
   assert all(torch.equal(x,y) for x,y in zip(first.unbind(),second.unbind()))
   first.unbind()[0].add_(1);third=noise.generate_noise(target);assert all(torch.equal(x,y) for x,y in zip(second.unbind(),third.unbind()))
   actual=json.loads((folder/(run+'_noise.json')).read_text());assert actual['historical_R3_noise_equal'] is True and actual['actual_noise_streams']==oldnoise['actual_noise_streams']
   bad=dict(oldnoise,actual_noise_streams=[]);badnoise=noise_module.ParentBoundNoise(c.SEED,folder,run,c.PAIR,bad)
   try:badnoise.generate_noise(target)
   except ValueError as e:assert 'archived R3' in str(e)
   else:raise AssertionError('bad archived noise accepted')
  assert torch.equal(after_native_generation,torch.get_rng_state())
 assert not torch.cuda.is_initialized()
 print('R25_AUX_CPU_SMOKE='+json.dumps({'passed':True,'actual_ParentBoundNoise_old_AV_bitwise_signatures':True,'cached_noise_copies_do_not_alias':True,'cache_hits_rng_unchanged':True,'native_cold_generation_scope':'official comfy.sample.prepare_noise calls torch.manual_seed and advances global CPU RNG, as historical parent; sampler gate starts after noise preparation','wrong_parent_noise_rejected':True,'CUDA_initialized':False,'seconds':time.monotonic()-start,'scope':'current official Noise node/CPU generator compared to archived R3 actual two-stream SHA; no VAE/Qwen/DiT; old embedding raw SHA lacks tensor_file so no reloaded-clean-numeric test or postaugmentation claim'}))
if __name__=='__main__':main()
