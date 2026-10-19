"""Report-only Comfy output node for the fixed R13 diagnostic."""
import time
import types

import torch

from .dependencies import guards
from .core import (BlockPatch, Config, ForkSampler, KEY, Source, State, require,
                   restore_uuid, rng_state, assert_rng, readout, output_head_contract)


def install(model, positive, source, run_id, audit_dir, *, observer=None, require_cuda=True):
    import comfy.ldm.minimax.model as h3
    from comfy.patcher_extension import WrappersMP
    config = Config(run_id, audit_dir)
    diffusion = model.get_model_object('diffusion_model')
    require(isinstance(diffusion, h3.MiniMaxH3Model) and
            (tuple(diffusion.patch_size), diffusion.latents_dim, len(diffusion.blocks)) == ((1, 2, 2), 24, 50),
            'frozen H3 model required')
    require(tuple(h3.FRAME_PER_TOKEN) == (1, 4, 4, 4, 4) and h3.FRAME_RESCALE == 5.0/3.0,
            'H3 temporal geometry changed')
    require(getattr(h3.optimized_attention, '__name__', None) == 'attention_pytorch', 'native backend entry changed')
    require(not any(model.wrappers.values()), 'existing model wrappers unsupported')
    options = model.model_options.get('transformer_options', {})
    require(not options.get('patches_replace', {}).get('dit') and
            options.get('optimized_attention_override') is None, 'existing DiT/attention patch')
    metadata, reference = guards.extract_reference(positive, config)
    state = State(metadata, reference, config, source, observer=observer)
    clone = model.clone()
    for i in range(50):
        clone.set_model_patch_replace(BlockPatch(state, i), 'dit', 'double_block', i)
    clone.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE, KEY, ForkSampler(state, require_cuda=require_cuda))
    return clone, state


class ModelAudit:
    """Read-only materialization counter and frozen single-head argument hook."""
    def __init__(self, model, state):
        self.model, self.state = model, state

    def __enter__(self):
        model, state = self.model, self.state
        heads = output_head_contract(model.diffusion_model.final_layer)
        self.had_own = 'extra_conds' in vars(model)
        self.original = model.extra_conds
        def count(this, *args, **kwargs):
            state.extra_conds_calls += 1
            require(state.extra_conds_calls == 1, 'duplicate extra_conds materialization')
            device = torch.device(kwargs['device'])
            before = rng_state(device)
            started = time.perf_counter()
            result = self.original(*args, **kwargs)
            assert_rng(before, device)
            state.audit['fork']['condition_materialization_seconds'] = time.perf_counter()-started
            state.audit['fork']['materialization_rng_unchanged'] = True
            return result
        model.extra_conds = types.MethodType(count, model)
        def output_head(module, args):
            require(state.phase is not None, 'output head outside an authorized forward')
            require(len(args) == 7, 'output head interface changed')
            _, _, _, _, sigma, grid, shifts = args
            m = state.phase['eval_euler_index']
            require(grid.dtype == torch.float32 and grid.detach().cpu().tolist() == state.source.c['full_grid'],
                    'output head full grid changed')
            i = int((grid-sigma).abs().argmin())
            require(i == m and tuple(map(float, shifts)) == (12.0, 3.0), 'output head interval/shifts changed')
            require(output_head_contract(module) == heads, 'output head contract changed during run')
            require(not any(row['probe_nfe'] == state.phase['probe_nfe'] for row in state.audit['fork']['pdd']),
                    'duplicate output head call')
            # Keep the existing archive key; the record explicitly marks PDD inactive.
            state.audit['fork']['pdd'].append(dict(state.phase, sigma=float(sigma),
                sigma_next=float(grid[i+1]), grid_signature=readout.tensor_signature(grid),
                index=i, start=None, stop=None, shifts=list(shifts), **heads,
                compute_dtype=str(model.get_dtype_inference())))
        try:
            self.handle = model.diffusion_model.final_layer.register_forward_pre_hook(output_head)
        except BaseException:
            self._restore()
            raise
        return self

    def _restore(self):
        if self.had_own:
            self.model.extra_conds = self.original
        else:
            delattr(self.model, 'extra_conds')

    def __exit__(self, kind, value, traceback):
        self.handle.remove()
        self._restore()


class H3OneStepForkAudit:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'positive': ('CONDITIONING',), 'noise': ('NOISE',),
            'sigmas': ('SIGMAS',), 'latent_image': ('LATENT',), 'source_manifest': ('STRING',),
            'run_id': ('STRING',), 'audit_dir': ('STRING',)}}
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('audit_report_path',)
    FUNCTION = 'execute'
    OUTPUT_NODE = True
    CATEGORY = 'research/H3OneStepForkAudit'

    def execute(self, model, positive, noise, sigmas, latent_image, source_manifest, run_id, audit_dir):
        import comfy.sample
        from comfy.samplers import KSAMPLER
        from comfy.k_diffusion.sampling import sample_euler
        from comfy_extras.nodes_custom_sampler import Guider_Basic
        source = Source(source_manifest)
        patched, state = install(model, positive, source, run_id, audit_dir)
        try:
            guider = Guider_Basic(patched)
            guider.set_conds(positive)
            state.audit['fork']['uuid_restoration'] = restore_uuid(guider, source)
            target = latent_image.copy()
            require('noise_mask' not in target, 'no mask supported')
            target['samples'] = comfy.sample.fix_empty_latent_channels(patched, target['samples'],
                target.get('downscale_ratio_spacial'), target.get('downscale_ratio_temporal'))
            initial = noise.generate_noise(target)
            require(noise.seed == source.c['seed'], 'Noise object seed changed')
            with ModelAudit(patched.model, state):
                # Return is a lifecycle placeholder, deliberately not a LATENT output.
                guider.sample(initial, target['samples'], KSAMPLER(sample_euler), sigmas,
                              callback=None, disable_pbar=True, seed=noise.seed)
            require(state.audit['status'] == 'complete' and len(state.audit['fork']['pdd']) == 6,
                    'six actual output head calls required')
            state.write()
            return (str(state.path),)
        except BaseException as error:
            state.audit['status'], state.audit['error'] = 'failed', f'{type(error).__name__}: {error}'
            state.write()
            raise


NODE_CLASS_MAPPINGS = {'H3OneStepForkAudit': H3OneStepForkAudit}
NODE_DISPLAY_NAME_MAPPINGS = {'H3OneStepForkAudit': 'H3 fixed one-step fork diagnostic (report only)'}
