"""One MODEL node, one shared run state and one actual Euler forward per callback."""
from .core import JointState,JointBlockPatch
from .layout import conditioning_metadata
from .architecture import architecture_contract
from .sampler_gate import SamplerGate,KEY
class H3ForwardReverseRouter:
 @classmethod
 def INPUT_TYPES(cls):return {'required':{'model':('MODEL',),'positive':('CONDITIONING',),'mode':(['joint'],),'run_id':('STRING',{'default':'unbound_r30'}),'audit_dir':('STRING',{'default':'/tmp/unbound-r30-router'})}}
 RETURN_TYPES=('MODEL',);FUNCTION='apply';CATEGORY='research/H3ForwardReverseRouter'
 def apply(self,model,positive,mode,run_id,audit_dir):
  import comfy.ldm.minimax.model as h3
  from comfy.patcher_extension import WrappersMP
  from r30_contract import validate_router,ROOT,read
  validate_router(mode,run_id,audit_dir);diffusion=model.get_model_object('diffusion_model')
  if not isinstance(diffusion,h3.MiniMaxH3Model) or (tuple(diffusion.patch_size),diffusion.latents_dim)!=((1,2,2),24):raise ValueError('actual H3 Ref2VA model required')
  contract=architecture_contract(diffusion)
  if contract['heads']!=56 or tuple(h3.FRAME_PER_TOKEN)!=(1,4,4,4,4) or h3.FRAME_RESCALE!=5/3:raise ValueError('frozen architecture/positions differ')
  if getattr(h3.optimized_attention,'__name__',None)!='attention_pytorch':raise ValueError('native PyTorch attention required')
  options=model.model_options.get('transformer_options',{})
  if options.get('optimized_attention_override') is not None or options.get('patches_replace',{}).get('dit'):raise ValueError('existing attention/block patch')
  if model.get_wrappers(WrappersMP.SAMPLER_SAMPLE,KEY):raise ValueError('duplicate sampler gate')
  state=JointState(conditioning_metadata(positive),run_id,audit_dir);state.audit['actual_model_contract']=contract;cloned=model.clone()
  for i in range(50):cloned.set_model_patch_replace(JointBlockPatch(state,i),'dit','double_block',i)
  parent=read(ROOT/'parent_evidence/full_x0_manifest.json');prefix=next(x for x in parent['captures'] if x['step_zero_based']==5)
  gate=SamplerGate(state,prefix,parent['sigmas_video'],2026101311,parent['target_latent_shapes'])
  gate.parent_condition=read(ROOT/'parent_evidence/reverse_block_router.json')['sampler_gate']['actual_current_condition']['tree']
  gate.prefix_bindings=read(ROOT/'design/PREFIX_0TO5_BINDING.json')
  native=read(ROOT/'parent_evidence/native_replay_actual_tensors.json');row=next(x for x in native['rows'] if x['stem']=='x0_step005')
  gate.native005={'file':native['b']+'/x0_step005.pt','sha256':row['file_sha256'][1]}
  cloned.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE,KEY,gate);return (cloned,)
NODE_CLASS_MAPPINGS={'H3ForwardReverseRouter':H3ForwardReverseRouter}
NODE_DISPLAY_NAME_MAPPINGS={'H3ForwardReverseRouter':'H3 joint forward Full and reverse BLOCK diagnostic'}
