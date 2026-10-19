"""One terminal Native prediction of an archived state with a bounded passive probe."""
import json
import time
from pathlib import Path
import torch
from .dependencies import router, layout, readout
from .source import Source, SHAPES, ROOT, require, sha
from .signatures import condition_signature, rng_state, assert_rng, synchronize
from .probe import mapping, read_distribution, describe, HEADS

KEY = 'H3AttentionStateProbe/two-fixed-states-v1'


def cpu_tree(value):
    if isinstance(value, torch.Tensor):
        return value.detach().to('cpu', copy=True).contiguous()
    if isinstance(value, dict):
        return {k: cpu_tree(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [cpu_tree(v) for v in value]
    return value


class State:
    def __init__(self, source, positive, output):
        self.source = source
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.metadata = layout.conditioning_metadata(positive)
        self.next_block = self.completed_blocks = self.attention_calls = 0
        self.active = False
        self.entered = self.complete = False
        self.extra_conds_calls = self.output_head_calls = self.probe_calls = 0
        self.audit = {'schema': 'r46-single-state-report-v1', 'label': source.label,
                      'run_id': 'r46_' + source.label + '_index4', 'status': 'installed',
                      'source_run': source.s['source_run'], 'seed': source.s['seed'],
                      'source_binding_sha256': sha(ROOT/'configs/sources.json'),
                      'protocol_sha256': sha(ROOT/'configs/SCIENCE_PROTOCOL.json'),
                      'DiT_NFE': 0, 'attempted_forwards': 0, 'completed_forwards': 0,
                      'Euler_updates': 0, 'ordinary_callbacks': 0,
                      'VAE_calls': 0, 'Qwen_calls': 0, 'routed_calls': 0,
                      'historical_global_rng_restored': False}
        self.write()

    def write(self):
        readout.atomic_write(self.output/'report.json', self.audit)

    def fail(self, error):
        self.active = False
        self.audit.update(status='failed', error=f'{type(error).__name__}: {error}',
                          completed_blocks=self.completed_blocks, native_attention_calls=self.attention_calls,
                          extra_conds_calls=self.extra_conds_calls, output_head_calls=self.output_head_calls)
        self.write()

    def capture(self, q, k, v, full, lse, plan, positions):
        require(self.probe_calls == 0, 'duplicate fixed-layer probe')
        self.probe_calls += 1
        m = mapping(plan, positions)
        require(q.shape == k.shape == v.shape == (1, 56, 87592, 128) and q.dtype == torch.bfloat16,
                'actual probe QKV geometry/dtype changed')
        ids = torch.tensor([row['packed_index'] for row in m['queries']], device=q.device)
        heads = torch.tensor(HEADS, device=q.device)
        ra, rb = m['reference_segment']
        def query_select(value):
            return value[:, heads[:, None], ids[None, :], :].contiguous()
        def reference_select(value):
            return value[:, :, ra:rb, :][:, heads, :, :].contiguous()
        qcopy, kcopy, vcopy = query_select(q), reference_select(k), reference_select(v)
        selected_output = query_select(full)
        lsecopy = lse[:, heads[:, None], ids[None, :]].contiguous()
        # Advanced indexing allocates selected copies, never aliases original storage.
        require(all(a.untyped_storage().data_ptr() != b.untyped_storage().data_ptr()
                    for a, b in ((qcopy, q), (kcopy, k), (vcopy, v), (lsecopy, lse))), 'probe copy aliases model tensor')
        before_rng = rng_state(q.device)
        synchronize(q.device); started = time.perf_counter()
        if q.device.type == 'cuda':
            memory_before = {'allocated': torch.cuda.memory_allocated(q.device),
                             'reserved': torch.cuda.memory_reserved(q.device)}
        else:
            memory_before = None
        result = read_distribution(qcopy, kcopy, vcopy, lsecopy, router.flash_attention_lse,
                                   query_bins=[row['bin'] for row in m['queries']])
        synchronize(q.device); seconds = time.perf_counter() - started
        require(torch.equal(query_select(q), qcopy) and torch.equal(reference_select(k), kcopy) and
                torch.equal(reference_select(v), vcopy) and torch.equal(query_select(full), selected_output),
                'selected original QKV/native output mutated')
        assert_rng(before_rng, q.device)
        summary = describe(result, m)
        payload = cpu_tree({'q': qcopy, 'reference_k': kcopy, 'distribution': result,
                            'descriptors': summary, 'mapping': m})
        path = self.output/'attention.pt'
        readout.atomic_write(path, payload, tensor=True)
        self.audit['probe'] = {'block': 25, 'heads': list(HEADS), 'queries_per_head': 1050,
            'mapping': m, 'quality': result['quality'], 'file': str(path), 'file_sha256': sha(path),
            'statistic_seconds_synchronized': seconds, 'memory_before_statistics': memory_before,
            'selected_original_QKV_output_exact': True, 'global_rng_unchanged': True,
            'original_output_not_passed_to_statistics': True, 'full_QKV_copy': False,
            'saved_tensor_signatures': {'q': readout.tensor_signature(payload['q']),
                                       'reference_k': readout.tensor_signature(payload['reference_k'])},
            'production_mutation_scope': 'selected original rows checked; all original bytes checked in small CPU oracle; full endpoint exact checked separately'}
        self.write()
        require(result['quality']['status'] == 'PASS', 'attention readout numerical gate failed; UNKNOWN retained')


class Attention:
    def __init__(self, state, block, plan, positions):
        self.state, self.block, self.plan, self.positions = state, block, plan, positions
        self.calls = 0

    def __call__(self, native, q, k, v, heads, **kwargs):
        require(getattr(native, '__name__', None) == 'attention_pytorch' and heads == 56 and
                kwargs.get('mask') is None and kwargs.get('skip_reshape') and
                not kwargs.get('skip_output_reshape', False), 'frozen native attention interface')
        self.calls += 1; require(self.calls == 1, 'duplicate attention')
        full, lse = router.flash_attention_lse(q, k, v)
        if self.block == 25:
            self.state.capture(q, k, v, full, lse, self.plan, self.positions)
        self.state.attention_calls += 1
        # Exact R33/R37 native formatting, no correction, clone or dtype conversion.
        return full.transpose(1, 2).reshape(1, q.shape[-2], heads * q.shape[-1])


class Block:
    def __init__(self, state, index):
        self.state, self.index = state, index

    def __call__(self, args, extra_args):
        s = self.state
        require(s.active and s.next_block == self.index, 'unauthorized/duplicate block order')
        options = args['transformer_options']
        require(options.get('block_index') == self.index and options.get('minimax_h3_layout') is args['layout'] and
                options.get('optimized_attention_override') is None, 'actual block/layout/override contract')
        plan = layout.validate_layout(s.metadata, args['layout'], 0, 140)
        require(readout.tensor_signature(args['layout'].position_ids) ==
                s.source.condition['tree']['processed']['positive'][0]['model_conds']['minimax_payload']['cond']['layout']['fields']['position_ids'],
                'actual position tensor differs')
        attention = Attention(s, self.index, plan, args['layout'].position_ids)
        local = dict(args); local['transformer_options'] = dict(options, optimized_attention_override=attention)
        result = extra_args['original_block'](local)
        require(attention.calls == 1, 'missing native attention')
        s.completed_blocks += 1; s.next_block = (self.index + 1) % 50
        return result


class TerminalSampler:
    """Never invoke executor: avoids KSAMPLER.noise_scaling and all Euler updates."""
    def __init__(self, state, require_cuda=True):
        self.state, self.require_cuda = state, require_cuda

    def __call__(self, executor, guider, sigmas, extra_args, callback, noise,
                 latent_image=None, denoise_mask=None, disable_pbar=False):
        from comfy.utils import unpack_latents
        from comfy_extras.nodes_custom_sampler import Guider_Basic
        from .guards import official_basic_guider_class
        s = self.state; src = s.source
        require(not s.entered and not s.complete, 'single-use sampler')
        s.entered = True
        require(official_basic_guider_class(type(guider), Guider_Basic) and guider.cfg == 1.0 and
                set(guider.original_conds) == {'positive'}, 'only official single-positive BasicGuider CFG1')
        require(callback is None and denoise_mask is None, 'no callback/mask')
        require(sigmas.dtype == torch.float32 and sigmas.detach().cpu().tolist() == src.s['full_grid'], 'full grid changed')
        options = extra_args['model_options']; grid = sigmas.detach().cpu().clone()
        require(torch.equal(options['transformer_options']['sample_sigmas'].cpu(), grid), 'model grid differs')
        require(extra_args['seed'] == src.s['seed'] and readout.tensor_signature(noise) == src.s['noise']['packed_signature'], 'noise/seed differs')
        require(condition_signature(guider) == src.condition and s.extra_conds_calls == 1, 'full processed condition mismatch/materialization count')
        model = guider.inner_model
        require(tuple(map(tuple, model.latent_shapes)) == SHAPES and model.audio_scale() == 4.0 and
                model.latent_format.scale_factor == 1.0, 'H3 normalization/shape differs')
        x = src.input().to(noise.device)
        require(not self.require_cuda or x.device.type == 'cuda', 'production Native requires CUDA')
        expected = src.endpoint()
        sigma = sigmas[4] * x.new_ones([1]); sigma_before = sigma.clone()
        before = rng_state(x.device); x_sig = readout.tensor_signature(x)
        s.active = True; synchronize(x.device); started = time.perf_counter()
        s.audit.update(status='predicting', DiT_NFE=1, attempted_forwards=1)
        s.write()
        try:
            y = guider(x, sigma, model_options=options, seed=src.s['seed'])
            synchronize(x.device)
            s.audit['completed_forwards'] = 1
        finally:
            seconds = time.perf_counter() - started
            s.active = False
            s.audit.update(model_and_probe_seconds_synchronized=seconds,
                           completed_blocks=s.completed_blocks, native_attention_calls=s.attention_calls,
                           extra_conds_calls=s.extra_conds_calls, output_head_calls=s.output_head_calls)
            s.write()
        assert_rng(before, x.device)
        require(readout.tensor_signature(x) == x_sig and torch.equal(sigma, sigma_before), 'raw input/sigma mutated')
        require(torch.equal(sigmas.cpu(), grid) and torch.equal(options['transformer_options']['sample_sigmas'].cpu(), grid), 'full grid mutated')
        require(condition_signature(guider) == src.condition, 'condition mutated')
        require(y.dtype == torch.float32 and y.shape == x.shape and bool(torch.isfinite(y).all()), 'Native endpoint schema')
        raw = [v.detach().cpu() for v in unpack_latents(y, SHAPES)]
        require([readout.tensor_signature(v) for v in raw] == src.s['endpoint']['raw_stream_signatures'] and
                all(torch.equal(a, b) for a, b in zip(raw, expected)), 'actual Native4 AV endpoint not bitwise equal')
        require(s.completed_blocks == s.attention_calls == 50 and s.next_block == 0 and
                s.probe_calls == s.output_head_calls == 1, 'one complete Native/probe/head required')
        endpoint = s.output/'endpoint_raw.pt'
        readout.atomic_write(endpoint, {'video': raw[0], 'audio_raw': raw[1]}, tensor=True)
        s.complete = True
        s.audit.update(status='complete', DiT_NFE=1, completed_blocks=50, native_attention_calls=50,
                       raw_input_signature=x_sig, condition_sha256=src.condition['sha256'],
                       full_grid=src.s['full_grid'], actual_sigma=float(sigmas[4]),
                       Native_AV_bitwise_equal=True, input_sigma_grid_condition_RNG_unchanged=True,
                       endpoint_file=str(endpoint), endpoint_sha256=sha(endpoint),
                       model_and_probe_seconds_synchronized=seconds,
                       peak_allocated_bytes=torch.cuda.max_memory_allocated(x.device) if x.device.type == 'cuda' else None,
                       peak_reserved_bytes=torch.cuda.max_memory_reserved(x.device) if x.device.type == 'cuda' else None)
        s.write()
        return x  # Report-only lifecycle placeholder, never decoded or used as output video.
