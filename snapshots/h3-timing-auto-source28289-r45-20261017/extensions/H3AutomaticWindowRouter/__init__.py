"""Native-first current-step observer gate with optional same-state Full."""
from .core import Config, State, BlockPatch, PredictionProbe, SamplerAudit, KEY, POLICIES
from .guards import extract_reference

class H3AutomaticWindowRouter:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'positive': ('CONDITIONING',),
                
                'run_id': ('STRING', {'default': 'r45_source28289_seed2026101701_auto'}),
                'audit_dir': ('STRING', {'default': '/tmp/h3-counterfactual'})}}
    RETURN_TYPES = ('MODEL',)
    FUNCTION = 'apply'
    CATEGORY = 'research/H3AutomaticWindowRouter'

    def apply(self, model, positive, run_id, audit_dir):
        import comfy.ldm.minimax.model as h3
        from comfy.patcher_extension import WrappersMP
        config = Config(run_id, audit_dir)
        diffusion = model.get_model_object('diffusion_model')
        if not isinstance(diffusion, h3.MiniMaxH3Model) or (tuple(diffusion.patch_size), diffusion.latents_dim, len(diffusion.blocks)) != ((1, 2, 2), 24, 50):
            raise ValueError('requires frozen H3 architecture')
        if tuple(h3.FRAME_PER_TOKEN) != (1, 4, 4, 4, 4) or h3.FRAME_RESCALE != 5.0/3.0:
            raise ValueError('H3 temporal geometry changed')
        if getattr(h3.optimized_attention, '__name__', None) != 'attention_pytorch':
            raise ValueError('requires PyTorch attention entry point')
        if model.get_wrappers(WrappersMP.SAMPLER_SAMPLE, KEY) or model.get_wrappers(WrappersMP.PREDICT_NOISE, KEY):
            raise ValueError('counterfactual wrapper already registered')
        options = model.model_options.get('transformer_options', {})
        if options.get('optimized_attention_override') is not None or options.get('patches_replace', {}).get('dit'):
            raise ValueError('existing DiT or attention patch unsupported')
        metadata, reference = extract_reference(positive, config)
        state = State(metadata, reference, config)
        cloned = model.clone()
        for i in range(50):
            cloned.set_model_patch_replace(BlockPatch(state, i), 'dit', 'double_block', i)
        cloned.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE, KEY, SamplerAudit(state))
        cloned.add_wrapper_with_key(WrappersMP.PREDICT_NOISE, KEY, PredictionProbe(state))
        return (cloned,)

NODE_CLASS_MAPPINGS = {'H3AutomaticWindowRouter': H3AutomaticWindowRouter}
NODE_DISPLAY_NAME_MAPPINGS = {'H3AutomaticWindowRouter': 'H3 automatic window current Native pose controller (20..39 NFE)'}
