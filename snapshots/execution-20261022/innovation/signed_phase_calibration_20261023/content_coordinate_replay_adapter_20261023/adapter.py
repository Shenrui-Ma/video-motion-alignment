"""Finite new-live-state diagnostic through the actual CFG/AV sampler wrappers.

One process_conds invocation precedes two zero and, only after both exact gates,
two content-swap forwards. No Euler update, trajectory callback, or VAE call.
"""
import copy
import time
from pathlib import Path
import torch
try:
    from .identity import tensor_info, exact_tensor, write_json
    from .condition import prepared_payload, replaced_reference, ConditionRowsOracle
    from .capture import ProbeLayout, PassiveQKCapture
except ImportError:
    from identity import tensor_info, exact_tensor, write_json
    from condition import prepared_payload, replaced_reference, ConditionRowsOracle
    from capture import ProbeLayout, PassiveQKCapture

QK_NAMES = tuple(s + '_' + b for s in ('raw', 'actual') for b in ('Q_C', 'Q_R', 'K_R'))
TENSOR_METADATA = ('q_norm_weight', 'k_norm_weight', 'position_canvas', 'position_reference', 'rope_canvas', 'rope_reference')
VALUE_METADATA = ('step_zero_based', 'layer_zero_based', 'spatial_ids', 'valid_bins', 'time_role',
                  'physical_frame_spans_inclusive', 'raw_stage', 'actual_stage', 'heads', 'head_dim',
                  'rot_dim', 'q_norm_eps', 'k_norm_eps')


def exact_capture(actual, expected, *, include_qk=True):
    for name in TENSOR_METADATA + (QK_NAMES if include_qk else ()):
        exact_tensor(actual[name], expected[name], name)
    for name in VALUE_METADATA:
        if actual[name] != expected[name]:
            raise ValueError('capture metadata mismatch: ' + name)
    return True


def arm_native(options, step, outdir):
    result = dict(options)
    to = dict(result.get('transformer_options', {})); result['transformer_options'] = to
    replace = dict(to.get('patches_replace', {})); to['patches_replace'] = replace
    dit = dict(replace.get('dit', {})); replace['dit'] = dit
    patches = [dit.get(('double_block', i)) for i in range(50)]
    if any(p is None for p in patches) or len({id(p.state) for p in patches}) != 1:
        raise ValueError('50 shared fresh native router patches required')
    old = patches[0].state
    if (old.mode != 'native' or old.forward_index != -1 or old.next_block != 0
            or old.audit['started_calls'] != 0):
        raise ValueError('original unused native router required')
    state = copy.deepcopy(old)
    state.forward_index = step - 1
    state.path = Path(outdir) / 'router.json'
    state.audit['calls_by_forward'] = [0] * step
    state.audit['routed_by_forward'] = [0] * step
    state.audit['replay'] = dict(step_zero_based=step, physical_calls_expected=1,
                                leading_zeros_are_skipped_not_executed=True)
    state.audit['status'] = 'finite_content_diagnostic'
    for i, old_patch in enumerate(patches):
        patch = copy.copy(old_patch); patch.state = state
        dit[('double_block', i)] = patch
    return result, state


def check_router_contract(state, expected):
    for key, wanted in expected.items():
        actual = getattr(state, key, None)
        if key == 'active_steps' and actual is not None:
            actual = list(actual)
        if actual != wanted:
            raise ValueError('native router identity mismatch: ' + key)


def context_signature(guider):
    """Hash tensors of prepared multimodal context; omit only reference content."""
    def visit(v, path):
        if isinstance(v, torch.Tensor):
            return tensor_info(v)
        if isinstance(v, dict):
            result = {str(k): visit(x, path + '/' + str(k)) for k, x in v.items()
                    if not (path.endswith('/minimax_payload') and k in ('refs', 'cond_video_latents'))}
            if path.endswith('/minimax_payload') and 'refs' in v:
                result['refs'] = [visit({k: x for k, x in ref.items() if k != 'latent'}, path + '/refs') for ref in v['refs']]
            return result
        if isinstance(v, (list, tuple)):
            return [visit(x, path) for x in v]
        if hasattr(v, 'cond'):
            return visit(v.cond, path)
        if hasattr(v, 'position_ids'):
            return dict(type=type(v).__name__, signature=list(v.signature), segments=list(v.segments),
                        position_ids=tensor_info(v.position_ids))
        if v is None or isinstance(v, (str, int, float, bool)):
            return v
        return dict(type=type(v).__name__, identity=id(v))
    return visit(guider.conds, '')


def dispatch_delta(before, after):
    keys = {b + '.' + op for b in ('cuda', 'triton', 'eager') for op in ('int8_linear', 'w4a8_int8_linear')}
    for snapshot in (before, after):
        if set(snapshot['operations']) != keys:
            raise ValueError('complete six-operation dispatch snapshot required')
        for value in snapshot['operations'].values():
            if any(type(value.get(k)) is not int or value[k] < 0
                   for k in ('attempted_calls', 'successful_calls', 'failed_calls')):
                raise ValueError('invalid actual dispatch counters')
    result = {}
    for key in set(before['operations']) | set(after['operations']):
        a, b = before['operations'].get(key, {}), after['operations'].get(key, {})
        result[key] = {k: b.get(k + '_calls', 0) - a.get(k + '_calls', 0) for k in ('attempted', 'successful', 'failed')}
    total = lambda backend, counter: sum(v[counter] for k, v in result.items() if k.startswith(backend + '.'))
    if (total('triton', 'attempted') != 200 or total('triton', 'successful') != 200
            or any(v['failed'] != 0 or min(v.values()) < 0 for v in result.values())
            or any(v['attempted'] != 0 for k, v in result.items() if not k.startswith('triton.'))):
        raise ValueError('actual 200 Triton and zero other dispatch gate failed')
    return result


class ContentCoordinateSampler:
    def __init__(self, inputs, contract, output_dir, *, allow_swap=False, backend_snapshot=None):
        if set(inputs) != {9, 19}:
            raise ValueError('exactly two native live inputs required')
        self.inputs, self.contract = inputs, contract
        self.out = Path(output_dir)
        self.allow_swap = allow_swap
        self.backend_snapshot = backend_snapshot
        self.used = False
        self.records = []
        self.last_raw = None

    def __call__(self, model_k, initial_x, sigmas, extra_args=None, callback=None, disable=None, **kw):
        if self.used:
            raise RuntimeError('finite sampler cannot be reused')
        self.used = True
        args = dict(extra_args or {})
        if kw or args.get('denoise_mask') is not None:
            raise ValueError('unexpected finite sampler options/mask')
        expected_sigmas = torch.tensor(self.contract['sigmas_video'], dtype=torch.float32)
        exact_tensor(sigmas.cpu(), expected_sigmas, 'full21 sigmas')
        if tensor_info(initial_x)['sha256'] != self.contract['noise_tensor_sha256']:
            raise ValueError('original full AV initial noise mismatch')
        guider = model_k.inner_model
        base, model = guider.inner_model, guider.inner_model.diffusion_model
        if (guider.cfg != 1 or float(base.audio_scale()) != 4
                or float(base.model_sampling.noise_scale) != 1
                or (base.model_sampling.shift, base.model_sampling.audio_shift, base.model_sampling.multiplier) != (12, 3, 1000)
                or [list(s) for s in base.latent_shapes] != self.contract['target_shapes']):
            raise ValueError('CFG/AV/noise domain mismatch')
        exact_tensor(args['model_options']['transformer_options']['sample_sigmas'].cpu(), expected_sigmas, 'model21 sigmas')
        if len(model.blocks) != 50 or (model.blocks[25].attn.heads, model.blocks[25].attn.head_dim) != (56, 128):
            raise ValueError('actual H3 architecture mismatch')
        payload = prepared_payload(guider)
        if int(payload['seed']) != 2026101701 or float(payload['audio_scale']) != 4:
            raise ValueError('prepared conditioning differs')
        probes = ProbeLayout.from_actual(payload['layout'], self.contract['target_shapes'][0], 105)
        if sum(probes.valid_bins) != 31:
            raise ValueError('31 complete bins required')
        if self.backend_snapshot is None:
            import backend_dispatch_audit
            audit = backend_dispatch_audit._active_auditor
            if audit is None:
                raise ValueError('actual backend auditor required')
            self.backend_snapshot = audit.summary
        self.out.mkdir(parents=True, exist_ok=False)
        prepared_before = context_signature(guider)
        template_options = args['model_options']
        report = dict(schema='h3-content-coordinate-exact-gate-v1', status='running', passed=False,
                      calls=self.records, is_trajectory=False, historical_replay_used=False,
                      single_guider_sample_entry=True,
                      preparation_path='existing CFGGuider process_conds; no preparation inside finite sampler',
                      noise_evidence='exact original-method recipe and current rows; historical N not independently saved')
        try:
            with ConditionRowsOracle(model) as rows_oracle:
                schedule = [(False, 9), (False, 19)] + ([(True, 9), (True, 19)] if self.allow_swap else [])
                for swap, step in schedule:
                    if swap and not all(r['zero_exact'] for r in self.records[:2]):
                        raise ValueError('both zero gates required before any swap')
                    label = ('swap' if swap else 'zero') + str(step)
                    d = self.out / label; d.mkdir()
                    saved, original_qk = self.inputs[step]
                    call_args = dict(args)
                    call_args['model_options'], router = arm_native(template_options, step, d)
                    check_router_contract(router, self.contract['router'])
                    x = saved['packed_x'].to(initial_x.device, dtype=torch.float32, copy=True)
                    x_before = tensor_info(x)
                    sigma = sigmas[step] * x.new_ones([x.shape[0]])
                    before_backend = self.backend_snapshot()
                    count = [0]
                    def count_forward(module, hook_args, hook_kw, output):
                        if output is not None:
                            count[0] += 1
                    handle = model.register_forward_hook(count_forward, with_kwargs=True, always_call=True)
                    cap = PassiveQKCapture(model.blocks[25].attn, probes, step=step, layer=25,
                                           in_training=__import__('comfy.model_management', fromlist=['in_training']).in_training)
                    started = time.perf_counter()
                    try:
                        with replaced_reference(guider, swap), cap:
                            if context_signature(guider) != prepared_before:
                                raise ValueError('non-reference prepared context changed')
                            result = model_k(x, sigma, **call_args)
                            if context_signature(guider) != prepared_before:
                                raise ValueError('prepared context mutated inside model')
                    finally:
                        handle.remove()
                    record = dict(label=label, step=step, swap=swap, seconds=time.perf_counter()-started,
                                  target_unchanged=tensor_info(x) == x_before,
                                  prepared_context_unchanged=context_signature(guider) == prepared_before,
                                  model_forward_calls=count[0], router_completed_blocks=router.audit['completed_calls'],
                                  zero_exact=False, coordinate_noise=rows_oracle.calls[-1])
                    self.records.append(record)
                    raw = result.detach().to('cpu', copy=True).contiguous()
                    torch.save({'raw_packed_x0': raw}, d / 'raw.pt')
                    cap.save(d / 'qk.pt')
                    if (not record['target_unchanged'] or not record['prepared_context_unchanged']
                            or count[0] != 1 or router.forward_index != step or router.next_block != 0
                            or router.audit['completed_calls'] != 50 or router.audit['completed_forward_calls'] != 1
                            or len(rows_oracle.calls) != len(self.records)
                            or raw.shape != saved['raw_packed_x0'].shape or raw.dtype != torch.float32
                            or not bool(torch.isfinite(raw).all())):
                        raise ValueError('single independent forward/context gate failed')
                    record['backend_delta'] = dispatch_delta(before_backend, self.backend_snapshot())
                    exact_capture(cap.data, original_qk, include_qk=not swap)
                    if not swap:
                        exact_tensor(raw, saved['raw_packed_x0'], 'complete raw AV x0')
                        record['zero_exact'] = True
                    record['raw'] = tensor_info(raw)
                    self.last_raw = raw
                    write_json(d / 'FORWARD.json', record)
                    write_json(self.out / 'GATE.json', report)
                torch.save(rows_oracle.noise, self.out / 'coordinate_noise.pt')
            report.update(status='forwards_complete', passed=False, outer_normalization_pending=True,
                          physical_forward_calls=len(self.records),
                          zero_steps_passed=[r['step'] for r in self.records if r['zero_exact']])
            write_json(self.out / 'GATE.json', report)
            # Outer sampler requires a tensor. This is not an updated trajectory.
            return result
        except BaseException as error:
            report.update(status='failed', passed=False, error=type(error).__name__ + ': ' + str(error))
            write_json(self.out / 'GATE.json', report)
            raise
