"""Six native predictions of frozen one-step branches; no sampling loop."""
import hashlib
import json
import time
import uuid
from pathlib import Path

import torch

from .dependencies import counterfactual, guards, observer

Config = counterfactual.Config
signature_tree = counterfactual.signature_tree
condition_signature = counterfactual.condition_signature
rng_state, assert_rng, synchronize = counterfactual.rng_state, counterfactual.assert_rng, counterfactual.synchronize
router, readout = counterfactual.router, counterfactual.readout
official_basic_guider_class = guards.official_basic_guider_class
FrozenGap5Observer = observer.FrozenGap5Observer

KEY = 'H3OneStepForkAudit/six-native-v1'
POINTS = (6, 10, 14)
SOURCE_RUN = 'r10_s05_fixed_full_probe'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def output_head_contract(final_layer):
    """Freeze the Ref2VA single-head shapes and the actual loaded float dtype."""
    heads = {}
    for name, width in (('video_out', 96), ('audio_out', 32)):
        head = getattr(final_layer, name, None)
        kind = type(head)
        mixed_linear = (isinstance(head, torch.nn.Module) and kind.__module__ == 'comfy.ops' and
                        kind.__qualname__ == 'mixed_precision_ops.<locals>.MixedPrecisionOps.Linear')
        require(isinstance(head, torch.nn.Linear) or mixed_linear,
                'expected official Linear output head: ' + name)
        require(head.in_features == 5376 and head.out_features == width and
                tuple(head.weight.shape) == (width, 5376) and head.bias is not None and
                tuple(head.bias.shape) == (width,), 'frozen output head shape changed: ' + name)
        require(head.weight.dtype in (torch.float16, torch.bfloat16, torch.float32) and
                head.bias.dtype == head.weight.dtype,
                'frozen output head dtype changed: ' + name)
        require(getattr(head, 'quant_format', None) is None and getattr(head, 'layout_type', None) is None,
                'frozen output head must be nonquantized: ' + name)
        heads[name] = {'weight_shape': list(head.weight.shape), 'bias_shape': list(head.bias.shape),
                       'in_features': head.in_features, 'out_features': head.out_features,
                       'class_module': kind.__module__, 'class_qualname': kind.__qualname__,
                       'weight_dtype': str(head.weight.dtype), 'bias_dtype': str(head.bias.dtype)}
    return {'head_mode': 'single_linear', 'pdd_active': False, 'bank_size': 1, 'heads': heads}


class Source:
    def __init__(self, manifest):
        self.manifest_path = Path(manifest)
        self.manifest = json.loads(self.manifest_path.read_text())
        m = self.manifest
        require(m.get('schema') == 'h3-r13-source-binding-v1' and m.get('status') == 'bound',
                'source binding is incomplete')
        require(m.get('source_run') == SOURCE_RUN, 'wrong source run')
        self.root = Path(m['source_root']).resolve()
        require(self.root.is_absolute() and bool(m['files']), 'invalid source root/inventory')
        for rel, digest in m['files'].items():
            path = self.root / rel
            require(not Path(rel).is_absolute() and path.resolve().is_relative_to(self.root), 'source path escape')
            require(path.is_file() and sha(path) == digest, 'source file mismatch: ' + rel)
        self.audit = self.json(f'audit/counterfactual/{SOURCE_RUN}.json')
        c = self.audit['counterfactual']
        require(self.audit['status'] == 'complete' and c['actual_model_nfe'] == 29 and
                c['callback_count'] == 20 and self.audit['completed_calls'] == 1450 and
                self.audit['routed_calls'] == 450, 'R10 is incomplete')
        pair = self.json('analysis/parent_pair_check.json')
        require(pair.get('passed') is True and pair.get('parent_final_video_audio_exact') is True,
                'R10/R3 paired archive gate not passed')
        self.c = c
        self.branches = {(r['physical_index'], r['branch']): r for r in c['branches']}
        self.inputs = {r['physical_index']: r for r in c['inputs']}
        require(len(self.branches) == 29 and set(self.inputs) == set(POINTS), 'source inventory changed')
        require(c['seed'] == 2026101311 and len(c['full_grid']) == 21, 'source seed/grid changed')
        require(c['full_grid'][-1] == 0 and all(a > b for a, b in zip(c['full_grid'], c['full_grid'][1:])),
                'source grid not decreasing')
        self.condition = c['conditioning']
        self.shapes = ((1, 24, 42, 46, 82), (1, 32, 2, 235))

    def path(self, rel):
        require(rel in self.manifest['files'], 'unbound source file: ' + rel)
        path = self.root / rel
        require(path.resolve().is_relative_to(self.root) and sha(path) == self.manifest['files'][rel],
                'source changed after binding: ' + rel)
        return path

    def json(self, rel):
        return json.loads(self.path(rel).read_text())

    def tensor(self, row):
        rel = f'audit/counterfactual/{SOURCE_RUN}_snapshots/' + Path(row['file']).name
        path = self.path(rel)
        require(sha(path) == row['file_sha256'], 'R10 tensor file SHA mismatch')
        return torch.load(path, map_location='cpu', weights_only=True)

    def endpoint(self, n, branch):
        row = self.branches[(n, branch)]
        data = self.tensor(row)
        for key in ('physical_index', 'branch', 'nfe_index', 'sigma', 'sigma_next', 'seed',
                    'condition_sha256', 'reference_sha256'):
            require(data['metadata'][key] == row[key], 'endpoint metadata mismatch: ' + key)
        require(row['physical_index'] == n and row['branch'] == branch and
                row['sigma'] == self.c['full_grid'][n] and row['sigma_next'] == self.c['full_grid'][n+1] and
                row['condition_sha256'] == self.condition['sha256'] and row['seed'] == self.c['seed'],
                'endpoint conditioning/index binding mismatch')
        streams = [data['video'], data['audio']]
        require([readout.tensor_signature(v) for v in streams] == row['normalized_stream_signatures'],
                'normalized endpoint bytes changed')
        raw = [streams[0], streams[1] * 4]
        require([readout.tensor_signature(v) for v in raw] == row['raw_stream_signatures'],
                'raw endpoint is not losslessly reconstructible')
        for value, shape in zip(raw, self.shapes):
            require(tuple(value.shape) == shape and value.dtype == torch.float32 and
                    bool(torch.isfinite(value).all()), 'raw endpoint geometry/dtype')
        return torch.cat([v.reshape(1, 1, -1) for v in raw], dim=-1), row

    def input(self, n):
        row = self.inputs[n]
        data = self.tensor(row)
        require(readout.tensor_signature(data['packed']) == row['packed_signature'], 'raw input bytes changed')
        for key in ('physical_index', 'sigma', 'sigma_next', 'full_grid', 'packed_signature', 'seed',
                    'condition_sha256', 'reference_sha256', 'coordinate_system'):
            require(data['metadata'][key] == row[key], 'input metadata mismatch: ' + key)
        require(row['physical_index'] == n and row['full_grid'] == self.c['full_grid'] and
                row['sigma'] == self.c['full_grid'][n] and row['sigma_next'] == self.c['full_grid'][n+1] and
                row['condition_sha256'] == self.condition['sha256'] and row['seed'] == self.c['seed'] and
                row['coordinate_system'] == 'raw sampler packed video/audio; no process_latent_out',
                'input coordinate/condition/index mismatch')
        require(data['packed'].dtype == torch.float32 and data['packed'].is_contiguous() and
                tuple(data['packed'].shape) == (1, 1, sum(torch.Size(s).numel() for s in self.shapes)),
                'input packed shape/dtype mismatch')
        return data['packed'], row


def restore_uuid(guider, source):
    actual = signature_tree(guider.original_conds)
    old = source.condition['tree']['original']
    require(set(actual) == {'positive'} and len(actual['positive']) == 1 and
            set(old) == {'positive'} and len(old['positive']) == 1, 'one positive required')
    new_uuid = actual['positive'][0].pop('uuid')
    old_copy = json.loads(json.dumps(old))
    previous = old_copy['positive'][0].pop('uuid')
    uuid.UUID(new_uuid)
    previous_uuid = uuid.UUID(previous)
    require(actual == old_copy, 'original conditioning differs beyond UUID')
    guider.original_conds['positive'][0]['uuid'] = previous_uuid
    require(signature_tree(guider.original_conds) == old, 'UUID restoration failed')
    return {'new_runtime_uuid': new_uuid, 'restored_source_uuid': previous,
            'all_other_original_condition_content_equal': True}


class State(router.RouterState):
    def __init__(self, metadata, reference, config, source, observer=None):
        self.config, self.source = config, source
        self.reference = reference.detach().to('cpu', copy=True).contiguous()
        self.reference_signature = readout.tensor_signature(self.reference)
        self.observer = observer or FrozenGap5Observer(self.reference)
        self.entered = self.finished = False
        self.phase = None
        self.extra_conds_calls = 0
        self.snapshots = Path(config.audit_dir) / (config.run_id + '_snapshots')
        self.snapshots.mkdir(parents=True, exist_ok=False)
        super().__init__(metadata, 'mass_preserve', 1.0, 0, 0, 50, 65, 0, 50, 0, 1,
                         config.run_id, config.audit_dir)
        self.audit['fork'] = {'schema': 'h3-one-step-fork-v1', 'diagnostic_only': True,
            'new_method_claim': False, 'observer_controls_selection': False,
            'source_manifest_sha256': sha(source.manifest_path), 'source_indices': list(POINTS),
            'expected_nfe': 6, 'euler_updates': 0, 'sampler_callbacks': 0,
            'pairs': [], 'predictions': [], 'pdd': [], 'reference': self.reference_signature}
        self.write()

    def selected(self, block):
        require(self.phase is not None, 'native forward was not authorized')
        return False

    def finish_forward(self):
        super().finish_forward()
        require(self.phase is not None, 'missing phase')
        self.audit['forward_summaries'][-1].update(self.phase)


class BlockPatch(router.EventBlockPatch):
    def __call__(self, args, extra_args):
        s = self.state
        require(s.phase is not None and s.entered and not s.finished, 'unauthorized block')
        if self.block_index == 0:
            require(s.phase['probe_nfe'] == s.forward_index + 1, 'extra model forward')
        return super().__call__(args, extra_args)


def validate_guider(guider, options, state, expected_class):
    require(official_basic_guider_class(type(guider), expected_class) and guider.cfg == 1.0,
            'requires official BasicGuider CFG1')
    require(set(guider.original_conds) == {'positive'} and len(guider.original_conds['positive']) == 1,
            'requires one positive')
    cond = guider.original_conds['positive'][0]
    require(not any(cond.get(k) is not None for k in ('hooks', 'control', 'mask', 'area')), 'regional/control hooks')
    for opts in (guider.model_options, options):
        for key in ('sampler_cfg_function', 'sampler_pre_cfg_function', 'sampler_post_cfg_function',
                    'sampler_calc_cond_batch_function', 'disable_cfg1_optimization',
                    'multigpu_thread_pool', 'model_function_wrapper'):
            require(not opts.get(key), 'unsupported model option: ' + key)
        tr = opts.get('transformer_options', {})
        for category, groups in tr.get('wrappers', {}).items():
            values = [v for group in groups.values() for v in group]
            require(not values or (category == 'sampler_sample' and len(values) == 1 and
                    isinstance(values[0], ForkSampler) and values[0].state is state), 'unexpected wrapper')
        patches = tr.get('patches_replace', {}).get('dit', {})
        require(len(patches) == 50 and all(isinstance(patches.get(('double_block', i)), BlockPatch)
                and patches[('double_block', i)].state is state for i in range(50)), 'patch/state mismatch')


class ForkSampler:
    """Terminal SAMPLER_SAMPLE wrapper: deliberately never executes KSAMPLER."""
    def __init__(self, state, *, unpack=None, to_d=None, expected_class=None, require_cuda=True):
        self.state, self.unpack, self.to_d = state, unpack, to_d
        self.expected_class, self.require_cuda = expected_class, require_cuda

    def __call__(self, executor, guider, sigmas, extra_args, callback, noise,
                 latent_image=None, denoise_mask=None, disable_pbar=False):
        s, src = self.state, self.state.source
        require(not s.entered, 'single-use run state')
        s.entered = True
        start = time.perf_counter()
        try:
            if self.unpack is None:
                from comfy.utils import unpack_latents
                from comfy.k_diffusion.sampling import to_d
                from comfy_extras.nodes_custom_sampler import Guider_Basic
                self.unpack, self.to_d, self.expected_class = unpack_latents, to_d, Guider_Basic
            model = guider.inner_model
            options = extra_args['model_options']
            validate_guider(guider, options, s, self.expected_class)
            require(callback is None and denoise_mask is None, 'no sampler callbacks or mask')
            require(noise.dtype == torch.float32 and (not self.require_cuda or noise.device.type == 'cuda'),
                    'production reconstruction requires original CUDA device/fp32')
            require(tuple(tuple(v) for v in model.latent_shapes) == src.shapes and
                    model.audio_scale() == 4.0 and model.latent_format.scale_factor == 1.0,
                    'H3 shape/normalization changed')
            grid = sigmas.detach().to('cpu', copy=True).contiguous()
            require(grid.dtype == torch.float32 and grid.tolist() == src.c['full_grid'], 'complete sigma grid changed')
            require(torch.equal(options['transformer_options']['sample_sigmas'], sigmas), 'model grid differs')
            require(readout.tensor_signature(noise) == src.c['initial_noise'], 'original noise changed')
            require(extra_args.get('seed') == src.c['seed'], 'seed changed')
            require(condition_signature(guider) == src.condition, 'processed condition hash changed')
            require(s.extra_conds_calls == 1, 'extra_conds must execute exactly once')
            initial_rng = rng_state(noise.device)
            noise_sig = readout.tensor_signature(noise)
            s.audit['fork'].update(condition=src.condition, full_grid=grid.tolist(),
                seed=src.c['seed'], device=str(noise.device), input_dtype=str(noise.dtype),
                raw_audio_scale=model.audio_scale(), condition_materializations=1)

            def archive(name, packed, metadata, observe=False):
                begin = time.perf_counter()
                raw = packed.detach().to('cpu', copy=True).contiguous()
                streams = self.unpack(raw, src.shapes)
                require(len(streams) == 2 and raw.dtype == torch.float32 and bool(torch.isfinite(raw).all()),
                        'nonfinite/nonfp32 packed result')
                ready = [streams[0], streams[1] * 0.25]
                row = dict(metadata, packed_signature=readout.tensor_signature(raw),
                           raw_stream_signatures=[readout.tensor_signature(v) for v in streams],
                           normalized_stream_signatures=[readout.tensor_signature(v) for v in ready])
                path = s.snapshots / name
                require(not path.exists(), 'duplicate archive')
                readout.atomic_write(path, {'packed': raw, 'video': ready[0], 'audio': ready[1],
                                           'metadata': row}, tensor=True)
                if observe:
                    row['observation'] = s.observer(ready[0])
                row.update(file=str(path), file_sha256=sha(path), archive_readout_seconds=time.perf_counter()-begin)
                return row

            def predict(u, n, branch):
                m = n + 1
                require(s.phase is None and s.next_block == 0, 'prediction state not idle')
                nfe = len(s.audit['fork']['predictions'])
                s.phase = {'source_euler_index': n, 'eval_euler_index': m, 'branch': branch, 'probe_nfe': nfe}
                input_sig = readout.tensor_signature(u)
                timestep = sigmas[m] * u.new_ones([u.shape[0]])
                sigma_copy = timestep.detach().to('cpu', copy=True)
                rng = rng_state(u.device)
                hash_start = time.perf_counter()
                require(condition_signature(guider) == src.condition, 'condition changed before prediction')
                hash_seconds = time.perf_counter()-hash_start
                synchronize(u.device)
                model_start = time.perf_counter()
                y = guider(u, timestep, model_options=options, seed=src.c['seed'])
                synchronize(u.device)
                model_seconds = time.perf_counter()-model_start
                assert_rng(rng, u.device)
                hash_start = time.perf_counter()
                require(condition_signature(guider) == src.condition, 'condition changed after prediction')
                hash_seconds += time.perf_counter()-hash_start
                require(readout.tensor_signature(u) == input_sig and torch.equal(timestep.cpu(), sigma_copy),
                        'input/sigma mutated')
                require(torch.equal(sigmas.cpu(), grid) and torch.equal(options['transformer_options']['sample_sigmas'].cpu(), grid),
                        'full grid mutated')
                require(s.audit['completed_forward_calls'] == nfe+1 and s.next_block == 0 and
                        s.audit['calls_by_forward'][-1] == 50 and s.audit['routed_by_forward'][-1] == 0,
                        'expected exactly one native50-block forward')
                require(isinstance(y, torch.Tensor) and y.dtype == torch.float32 and y.shape == u.shape,
                        'denoised output coordinate schema changed')
                row = archive(f'n{n:02d}_{branch}_endpoint.pt', y, dict(s.phase, sigma=float(sigmas[m]),
                    sigma_next=float(sigmas[m+1]), input_signature=input_sig, condition_sha256=src.condition['sha256'],
                    reference_sha256=s.reference_signature['sha256'], seed=src.c['seed']), observe=True)
                row.update(model_seconds_synchronized=model_seconds, condition_hash_seconds=hash_seconds,
                           global_rng_unchanged=True, input_unchanged=True)
                s.audit['fork']['predictions'].append(row)
                s.phase = None
                s.write()
                return y, row

            for n in POINTS:
                m = n+1
                x_cpu, x_row = src.input(n)
                yn_cpu, yn_row = src.endpoint(n, 'native')
                yf_cpu, yf_row = src.endpoint(n, 'full')
                _, known = src.endpoint(m, 'native')
                require(x_row['reference_sha256'] == s.reference_signature['sha256'] and
                        all(r['reference_sha256'] == s.reference_signature['sha256'] for r in (yn_row, yf_row, known)),
                        'reference binding mismatch')
                x = x_cpu.to(device=noise.device, copy=True)
                yn, yf = [v.to(device=noise.device, copy=True) for v in (yn_cpu, yf_cpu)]
                synchronize(x.device)
                begin = time.perf_counter()
                d_f = self.to_d(x, sigmas[n], yf)
                dt = sigmas[m] - sigmas[n]
                u_f = x + d_f * dt
                d_n = self.to_d(x, sigmas[n], yn)
                u_n = x + d_n * dt
                synchronize(x.device)
                reconstruction_seconds = time.perf_counter()-begin
                pair = {'source_euler_index': n, 'eval_euler_index': m, 'reconstruction_seconds': reconstruction_seconds,
                        'source_x': x_row, 'source_native': yn_row, 'source_full': yf_row}
                pair['u_full'] = archive(f'n{n:02d}_u_full_raw.pt', u_f, {'coordinate_system': 'raw next sampler input'})
                pair['u_native'] = archive(f'n{n:02d}_u_native_raw.pt', u_n, {'coordinate_system': 'raw next sampler input'})
                s.audit['fork']['pairs'].append(pair)
                require(readout.tensor_signature(u_f) == known['same_input'], 'Full next-input SHA replay gate failed')
                pair['full_next_input_exact'] = True
                s.write()
                _, replay = predict(u_f, n, 'replay_full')
                require(replay['raw_stream_signatures'] == known['raw_stream_signatures'] and
                        replay['normalized_stream_signatures'] == known['normalized_stream_signatures'],
                        'Full next-endpoint SHA replay gate failed')
                pair['full_next_endpoint_exact'] = True
                s.write()
                predict(u_n, n, 'fork_native')
            require(len(s.audit['fork']['predictions']) == 6 and s.audit['completed_calls'] == 300 and
                    s.audit['routed_calls'] == 0 and s.extra_conds_calls == 1, 'incomplete six native probes')
            require(condition_signature(guider) == src.condition and readout.tensor_signature(noise) == noise_sig and
                    readout.tensor_signature(s.reference) == s.reference_signature, 'bound data mutated')
            assert_rng(initial_rng, noise.device)
            s.audit['fork'].update(actual_nfe=6, wall_seconds=time.perf_counter()-start,
                all_replay_gates_passed=True, output_is_report_only=True, global_rng_unchanged=True)
            s.audit['status'] = 'complete'
            # Only for Guider's lifecycle return; the report node discards this.
            return torch.zeros_like(noise)
        except BaseException as error:
            s.audit['status'], s.audit['error'] = 'failed', f'{type(error).__name__}: {error}'
            raise
        finally:
            s.finished, s.phase = True, None
            s.write()
