"""Two frozen terminal Native states, with no Euler or media execution."""
import time
import types
import torch
from .source import Source, ROOT, require
from .core import State, Block, TerminalSampler, KEY
from .signatures import rng_state, assert_rng
from .head import output_head_contract


def install(model, positive, source, output, *, require_cuda=True):
    import comfy.ldm.minimax.model as h3
    from comfy.patcher_extension import WrappersMP
    diffusion = model.get_model_object('diffusion_model')
    require(isinstance(diffusion, h3.MiniMaxH3Model) and
            (tuple(diffusion.patch_size), diffusion.latents_dim, len(diffusion.blocks)) == ((1, 2, 2), 24, 50),
            'frozen H3 architecture required')
    require(tuple(h3.FRAME_PER_TOKEN) == (1, 4, 4, 4, 4) and h3.FRAME_RESCALE == 5.0 / 3.0,
            'H3 temporal geometry changed')
    require(getattr(h3.optimized_attention, '__name__', None) == 'attention_pytorch', 'native backend entry changed')
    require(not any(model.wrappers.values()), 'existing model wrappers unsupported')
    options = model.model_options.get('transformer_options', {})
    require(not options.get('patches_replace', {}).get('dit') and
            options.get('optimized_attention_override') is None, 'existing DiT/attention patch')
    state = State(source, positive, output)
    clone = model.clone()
    for i in range(50):
        clone.set_model_patch_replace(Block(state, i), 'dit', 'double_block', i)
    clone.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE, KEY, TerminalSampler(state, require_cuda))
    return clone, state


class ModelAudit:
    def __init__(self, model, state):
        self.model, self.state = model, state

    def __enter__(self):
        model, state = self.model, self.state
        heads = output_head_contract(model.diffusion_model.final_layer)
        self.had_own = 'extra_conds' in vars(model)
        self.original = model.extra_conds
        def count(this, *args, **kwargs):
            state.extra_conds_calls += 1
            require(state.extra_conds_calls == 1, 'duplicate condition materialization')
            device = torch.device(kwargs['device']); before = rng_state(device)
            started = time.perf_counter()
            result = self.original(*args, **kwargs)
            assert_rng(before, device)
            state.audit['condition_materialization_seconds'] = time.perf_counter() - started
            state.audit['materialization_rng_unchanged'] = True
            return result
        model.extra_conds = types.MethodType(count, model)
        def output_head(module, args):
            require(state.active and len(args) == 7, 'output head outside authorized Native/interface')
            _, _, _, _, sigma, grid, shifts = args
            require(grid.dtype == torch.float32 and grid.detach().cpu().tolist() == state.source.s['full_grid'],
                    'actual output head full grid changed')
            require(int((grid - sigma).abs().argmin()) == 4 and float(sigma) == state.source.s['full_grid'][4]
                    and tuple(map(float, shifts)) == (12.0, 3.0), 'actual head sigma/index/shifts changed')
            require(output_head_contract(module) == heads, 'loaded head contract changed')
            state.output_head_calls += 1
            require(state.output_head_calls == 1, 'duplicate output head')
            state.audit['output_head'] = dict(index=4, sigma=float(sigma), sigma_next=float(grid[5]),
                                            shifts=list(shifts), **heads)
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


class H3AttentionStateProbe:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'state_id': (['bad', 'normal'],)}}
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('report_path',)
    FUNCTION = 'execute'
    OUTPUT_NODE = True
    CATEGORY = 'research/H3AttentionStateProbe'

    def execute(self, model, state_id):
        from comfy.nested_tensor import NestedTensor
        from comfy.samplers import KSAMPLER
        from comfy.k_diffusion.sampling import sample_euler
        from comfy_extras.nodes_custom_sampler import Guider_Basic
        source = Source(state_id)
        positive = source.positive()
        noise = source.noise()
        patched, state = install(model, positive, source, ROOT/'audit/probe'/state_id)
        try:
            guider = Guider_Basic(patched)
            guider.set_conds(positive)
            source.restore_original_uuid(guider)
            state.audit['original_UUID_restored'] = True
            with ModelAudit(patched.model, state):
                # KSAMPLER is a required lifecycle argument, never executed by TerminalSampler.
                guider.sample(NestedTensor(noise), NestedTensor([torch.zeros_like(x) for x in noise]),
                              KSAMPLER(sample_euler), torch.tensor(source.s['full_grid'], dtype=torch.float32),
                              callback=None, disable_pbar=True, seed=source.s['seed'])
            require(state.complete and state.extra_conds_calls == state.output_head_calls == 1,
                    'terminal Native not complete')
            return (str(state.output/'report.json'),)
        except BaseException as error:
            state.fail(error)
            raise


NODE_CLASS_MAPPINGS = {'H3AttentionStateProbe': H3AttentionStateProbe}
NODE_DISPLAY_NAME_MAPPINGS = {'H3AttentionStateProbe': 'H3 two-state passive attention diagnostic'}
