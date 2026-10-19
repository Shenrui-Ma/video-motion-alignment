"""Native endpoint observation chooses this physical step's optional Full branch."""
from dataclasses import dataclass
import hashlib
import json
import time
from pathlib import Path
import uuid

import torch

from .dependencies import router, readout
from .guards import extract_reference, official_basic_guider_class
from .transport import PROTOCOL_SHA
from .dynamic_support import make_gain
from .selector import Controller
from .live_observer import LivePoseObserver, parent_guard
from .pair_gate import HistoricalPairGate

KEY = 'H3AutomaticWindowRouter/current-pose-v1'
ELIGIBLE_STEPS = tuple(range(20))
POLICIES = ('automatic_windows',)
INPUT_STEPS = (6, 10, 14)


@dataclass(frozen=True)
class Config:
    run_id: str
    audit_dir: str
    width: int = 1312
    height: int = 736
    length: int = 141
    policy: str = 'automatic_windows'
    fixed_indices: str = ''

    def __post_init__(self):
        readout.CaptureConfig(self.run_id, self.audit_dir, self.width, self.height, self.length)
        if (self.width, self.height, self.length) != (1312, 736, 141):
            raise ValueError('R19 geometry is frozen')
        if self.policy not in POLICIES:
            raise ValueError('unknown native-observer policy')
        indices = self.indices
        if self.policy != 'fixed' and indices:
            raise ValueError('fixed_indices must be empty outside fixed policy')

    @property
    def indices(self):
        if not isinstance(self.fixed_indices, str):
            raise ValueError('fixed_indices must be a comma-separated string')
        if not self.fixed_indices.strip():
            return ()
        parts = [part.strip() for part in self.fixed_indices.split(',')]
        if any(not part.isdecimal() for part in parts):
            raise ValueError('fixed_indices require nonnegative integer indices')
        values = tuple(int(part) for part in parts)
        if len(set(values)) != len(values) or tuple(sorted(values)) != values or any(v not in ELIGIBLE_STEPS for v in values):
            raise ValueError('fixed indices must be unique increasing indices6..19')
        return values

    @property
    def shapes(self):
        return readout.CaptureConfig(self.run_id, self.audit_dir).shapes



def signature_tree(value):
    """Content signature of actual original and processed conditioning."""
    if isinstance(value, torch.Tensor):
        return readout.tensor_signature(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [signature_tree(v) for v in value]
    if isinstance(value, dict):
        return {str(k): signature_tree(v) for k, v in sorted(value.items(), key=lambda p: str(p[0]))}
    if isinstance(value, (uuid.UUID, torch.device, torch.dtype)):
        return str(value)
    if hasattr(value, 'cond'):
        return {'type': type(value).__qualname__, 'cond': signature_tree(value.cond)}
    if type(value).__name__ == 'PackedLayout':
        return {'type': 'PackedLayout', 'fields': signature_tree(vars(value))}
    raise ValueError('unsupported conditioning value: ' + type(value).__qualname__)


def condition_signature(guider):
    value = signature_tree({'original': guider.original_conds, 'processed': getattr(guider, 'conds', {})})
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return {'sha256': hashlib.sha256(encoded).hexdigest(), 'tree': value}


def rng_state(device):
    result = {'cpu': torch.random.get_rng_state().clone()}
    if device.type == 'cuda':
        result['cuda'] = torch.cuda.get_rng_state(device).clone()
    return result


def assert_rng(previous, device):
    now = rng_state(device)
    if set(now) != set(previous) or any(not torch.equal(previous[k], now[k]) for k in previous):
        raise ValueError('model/probe consumed global RNG')


def synchronize(device):
    if device.type == 'cuda':
        torch.cuda.synchronize(device)


class State(router.RouterState):
    def __init__(self, metadata, reference, config, *, observer=None):
        self.config = config
        self.reference = reference.detach().to('cpu', copy=True).contiguous()
        self.reference_signature = readout.tensor_signature(self.reference)
        self.observer = observer
        self.controller = Controller()
        self.query_gain = None
        self.active_bins = []
        self.live_observer = LivePoseObserver()
        self.pair_gate = HistoricalPairGate()
        self.entered = self.finished = False
        self.callback_count = 0
        self.previous_choice = False
        self.full_indices = []
        self.phase = None
        self.transaction = None
        self.grid = None
        self.unpack = self.nested = self.model = self.guider = None
        self.initial_condition = None
        self.seed = None
        self.sample_options = None
        self.snapshots = Path(config.audit_dir) / (config.run_id + '_snapshots')
        self.snapshots.mkdir(parents=True, exist_ok=False)
        super().__init__(metadata, 'mass_preserve', 1.0, 0, 0, 0, 140, 0, 50, 0, 40,
                         config.run_id, config.audit_dir)
        self.audit['counterfactual'] = {'schema': 'h3-automatic-window-current-step-v1',
            'diagnostic_only': True, 'new_method_claim': False,
            'policy': config.policy, 'fixed_indices': list(config.indices),
            'observer_controls_selection': 'external_frozen_RGB_pose_only',
            'eligible_full_indices': list(ELIGIBLE_STEPS), 'full_physical_indices': self.full_indices,
            'input_archive_indices': list(INPUT_STEPS),
            'expected_euler_updates': 20, 'expected_model_nfe': '20+active_count',
            'model_nfe_bounds': [20, 39], 'reference': self.reference_signature,
            'observer_protocol_sha256': PROTOCOL_SHA,
            'branches': [], 'steps': [], 'inputs': [], 'callback_count': 0, 'measurements': [], 'pair_gates': [],
            'legacy_forward_index_semantics': 'model NFE index, not Euler step',
            'legacy_component_readouts': 'passive NFE positions; sigma labels mapped to physical step',
            'frozen_scientific_protocol_sha256':PROTOCOL_SHA,
            'endpoint_scaling': 'video identity/audio divided4 on CPU copies; returned endpoint untouched'}
        self.write()

    def selected(self, block):
        if self.phase is None or self.phase['nfe_index'] != self.forward_index:
            raise ValueError('missing exact branch authorization')
        return self.phase['active'] and 0 <= block < 50

    def authorize(self, physical, branch):
        if self.phase is not None or self.next_block != 0 or not self.entered or self.finished:
            raise ValueError('branch authorization outside idle sampling state')
        if self.transaction is None or physical != self.callback_count or self.transaction['physical_index'] != physical:
            raise ValueError('branch physical index differs from current transaction')
        entries = self.transaction['branches']
        if branch == 'native':
            if entries:
                raise ValueError('native must be the first and only native branch')
        elif branch == 'full':
            if physical not in ELIGIBLE_STEPS or len(entries) != 1 or entries[0]['branch'] != 'native' or not self.transaction.get('decision', {}).get('chosen_full'):
                raise ValueError('Full requires this step native decision authorization')
        else:
            raise ValueError('unknown prediction branch')
        if branch == 'full' and (not self.active_bins or self.query_gain is None):
            raise ValueError('Full requires immutable nonempty selected-bin union')
        self.phase = {'physical_index': physical, 'branch': branch, 'latent_bins': list(self.active_bins) if branch == 'full' else [],
                      'active': branch == 'full', 'nfe_index': self.forward_index + 1}

    def finish_forward(self):
        super().finish_forward()
        if self.phase is None:
            raise ValueError('unauthorized forward')
        self.audit['forward_summaries'][-1].update(self.phase)
        for name in ('component_readouts', 'temporal_readouts'):
            for row in self.audit.get(name, []):
                if row['forward_index'] == self.forward_index and 'physical_index' not in row:
                    row.update(physical_index=self.phase['physical_index'], branch=self.phase['branch'])
                    if 'sampler_sigma_video' in row:
                        row['sampler_sigma_video'] = float(self.grid[self.phase['physical_index']])
        self.write()

    def raw(self, value):
        leaves = readout.split_streams(value, self.config.shapes, self.unpack)
        raw = [v.detach().to('cpu', copy=True).contiguous() for v in leaves]
        if any(v.dtype != torch.float32 or not bool(torch.isfinite(v).all()) for v in raw):
            raise ValueError('endpoint/input requires finite fp32 streams')
        return raw

    def save_endpoint(self, value, physical, branch):
        start = time.perf_counter()
        raw = self.raw(value)
        raw_sig = [readout.tensor_signature(v) for v in raw]
        with torch.no_grad():
            ready = list(self.model.process_latent_out(self.nested([v.clone() for v in raw])).unbind())
        if len(ready) != 2 or not torch.equal(ready[0], raw[0]) or not torch.equal(ready[1], raw[1] * 0.25):
            raise ValueError('unexpected MiniMax normalization')
        if any(v.device.type != 'cpu' or v.dtype != torch.float32 or tuple(v.shape) != shape
               for v, shape in zip(ready, self.config.shapes)):
            raise ValueError('unexpected normalized endpoint schema')
        observation = None  # Pose is measured on every current Native endpoint externally.
        path = self.snapshots / f'step{physical:03d}_{branch}.pt'
        if path.exists():
            raise FileExistsError(path)
        metadata = {'physical_index': physical, 'branch': branch, 'nfe_index': self.forward_index,
                    'sigma': float(self.grid[physical]), 'sigma_next': float(self.grid[physical + 1]),
                    'raw_stream_signatures': raw_sig, 'seed': self.seed,
                    'condition_sha256': self.initial_condition['sha256'],
                    'reference_sha256': self.reference_signature['sha256']}
        readout.atomic_write(path, {'video': ready[0], 'audio': ready[1], 'metadata': metadata}, tensor=True)
        return dict(metadata, file=str(path), file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    normalized_stream_signatures=[readout.tensor_signature(v) for v in ready],
                    observation=observation, archive_and_readout_seconds=time.perf_counter()-start)

    def save_input(self, x, sigma, physical):
        started = time.perf_counter()
        copy = x.detach().to('cpu', copy=True).contiguous()
        self.raw(copy)  # verifies complete packed geometry, finite fp32
        path = self.snapshots / f'step{physical:03d}_input_raw.pt'
        metadata = {'physical_index': physical, 'sigma': float(self.grid[physical]),
                    'sigma_next': float(self.grid[physical + 1]), 'full_grid': self.grid.tolist(),
                    'packed_signature': readout.tensor_signature(copy), 'seed': self.seed,
                    'condition_sha256': self.initial_condition['sha256'],
                    'reference_sha256': self.reference_signature['sha256'],
                    'coordinate_system': 'raw sampler packed video/audio; no process_latent_out'}
        readout.atomic_write(path, {'packed': copy, 'metadata': metadata}, tensor=True)
        self.audit['counterfactual']['inputs'].append(dict(metadata, file=str(path),
            file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            archive_seconds=time.perf_counter()-started))


class BlockPatch(router.EventBlockPatch):
    def __call__(self, args, extra_args):
        s = self.state
        if s.phase is None:
            raise ValueError('DiT forward without authorized branch')
        if self.block_index == 0:
            if s.phase['nfe_index'] != s.forward_index + 1 or s.audit['completed_forward_calls'] != s.forward_index + 1:
                raise ValueError('duplicate/missing branch forward')
        return super().__call__(args, extra_args)


def validate_guider(guider, options, state, guider_class=None):
    if guider_class is None:
        from comfy_extras.nodes_custom_sampler import Guider_Basic
        guider_class = Guider_Basic
    if not official_basic_guider_class(type(guider), guider_class) or guider.cfg != 1.0:
        raise ValueError('requires official BasicGuider CFG1')
    conds = guider.original_conds
    if set(conds) != {'positive'} or len(conds['positive']) != 1:
        raise ValueError('requires exactly one positive and no negative')
    c = conds['positive'][0]
    if any(c.get(k) is not None for k in ('hooks', 'control', 'mask', 'area')):
        raise ValueError('condition hook/region unsupported')
    refs = [r for r in c.get('minimax_refs', []) if r['kind'] in ('video', 'video_audio')]
    if len(refs) != 1 or refs[0]['kind'] != 'video' or readout.tensor_signature(refs[0]['latent']) != state.reference_signature:
        raise ValueError('reference binding mismatch')
    for opts in (guider.model_options, options):
        for key in ('sampler_cfg_function', 'sampler_pre_cfg_function', 'sampler_post_cfg_function',
                    'sampler_calc_cond_batch_function', 'disable_cfg1_optimization',
                    'multigpu_thread_pool', 'model_function_wrapper'):
            if opts.get(key):
                raise ValueError('unsupported model option: ' + key)
        tr = opts.get('transformer_options', {})
        wrappers = tr.get('wrappers', {})
        for category, groups in wrappers.items():
            values = [v for seq in groups.values() for v in seq]
            if category not in ('sampler_sample', 'predict_noise') and values:
                raise ValueError('unsupported per-forward wrapper')
            if category == 'predict_noise' and (len(values) != 1 or not isinstance(values[0], PredictionProbe) or values[0].state is not state):
                raise ValueError('predict wrapper identity mismatch')
        patches = tr.get('patches_replace', {}).get('dit', {})
        if len(patches) != 50 or any(not isinstance(patches.get(('double_block', i)), BlockPatch)
                                   or patches[('double_block', i)].state is not state for i in range(50)):
            raise ValueError('block state identity mismatch')


class PredictionProbe:
    def __init__(self, state):
        self.state = state

    def __call__(self, executor, x, timestep, model_options=None, seed=None):
        s = self.state
        n = s.callback_count
        if not s.entered or s.finished or s.transaction is not None or not 0 <= n < 20:
            raise ValueError('prediction outside exact Euler transaction')
        if executor.class_obj is not s.guider or seed != s.seed or model_options is not s.sample_options:
            raise ValueError('prediction guider/seed/options binding mismatch')
        if not isinstance(x, torch.Tensor) or x.dtype != torch.float32 or x.ndim != 3:
            raise ValueError('expected packed fp32 sampler input')
        sigma = timestep.detach().to(device='cpu', copy=True).clone()
        if sigma.numel() != 1 or not torch.equal(sigma.reshape(()), s.grid[n].to(sigma.dtype).reshape(())):
            raise ValueError('prediction sigma does not match physical step')
        input_sig = readout.tensor_signature(x)
        before_rng = rng_state(x.device)
        if n in INPUT_STEPS:
            s.save_input(x, timestep, n)
        entries = []
        s.transaction = {'physical_index': n, 'branches': entries, 'input': input_sig,
                         'input_stream_signatures': [readout.tensor_signature(v) for v in s.raw(x)]}
        try:
            for branch in ('native', 'full'):
                if branch == 'full' and not s.transaction['decision']['chosen_full']:
                    break
                condition_started = time.perf_counter()
                if condition_signature(s.guider) != s.initial_condition:
                    raise ValueError('conditioning content changed')
                condition_seconds = time.perf_counter() - condition_started
                if not torch.equal(timestep.detach().cpu(), sigma):
                    raise ValueError('branch timestep mutated')
                if readout.tensor_signature(x) != input_sig:
                    raise ValueError('same-state input mutated')
                assert_rng(before_rng, x.device)
                s.authorize(n, branch)
                count = s.audit['completed_forward_calls']
                synchronize(x.device)
                started = time.perf_counter()
                output = executor(x, timestep, model_options, seed)
                synchronize(x.device)
                elapsed = time.perf_counter() - started
                if s.audit['completed_forward_calls'] != count + 1 or s.next_block != 0 or s.audit['calls_by_forward'][-1] != 50:
                    raise ValueError('branch must execute exactly one complete50-block forward')
                if s.audit['routed_by_forward'][-1] != (50 if branch == 'full' else 0):
                    raise ValueError('branch routing changed')
                assert_rng(before_rng, x.device)
                condition_started = time.perf_counter()
                condition_after = condition_signature(s.guider)
                condition_seconds += time.perf_counter() - condition_started
                if not torch.equal(timestep.detach().cpu(), sigma):
                    raise ValueError('branch timestep mutated')
                if readout.tensor_signature(x) != input_sig or condition_after != s.initial_condition:
                    raise ValueError('branch modified input or conditioning')
                row = s.save_endpoint(output, n, branch)
                row.update(model_seconds_synchronized=elapsed, condition_copy_hash_seconds=condition_seconds, same_input=input_sig,
                           global_rng_unchanged=True, condition_unchanged=True,
                           full_grid_unchanged=torch.equal(model_options['transformer_options']['sample_sigmas'].detach().cpu().double(), s.grid))
                if not row['full_grid_unchanged']:
                    raise ValueError('sigma grid mutated')
                entries.append(row)
                s.audit['counterfactual']['branches'].append(row)
                # G1/G3 only compare genuinely common historical states/branches.
                s.pair_gate.branch(s, x, output, row)
                if branch == 'native':
                    measurement = None
                    if True:
                        guard = parent_guard(s, x, timestep, output)
                        measurement = s.live_observer(s, row)
                        if parent_guard(s, x, timestep, output) != guard:
                            raise ValueError('observer changed parent state/residency/environment')
                        assert_rng(before_rng, x.device)
                        if condition_signature(s.guider) != s.initial_condition or readout.tensor_signature(x) != input_sig:
                            raise ValueError('observer changed current x/condition')
                        if not torch.equal(timestep.detach().cpu(), sigma):
                            raise ValueError('observer changed physical sigma')
                        s.audit['counterfactual']['measurements'].append(measurement)
                    s.transaction['decision'] = s.controller.select(n, measurement)
                    s.active_bins = s.transaction['decision']['latent_bins']
                    s.query_gain = make_gain(s.active_bins) if s.active_bins else None
                    s.pair_gate.decision(s, n, s.transaction['decision'])
                    s.transaction['decision']['native_nfe_index'] = row['nfe_index']
                else:
                    s.full_indices.append(n)
                s.phase = None
                s.write()
            s.transaction.update(chosen=entries[-1], selected_branch=entries[-1]['branch'])
            if True:
                s.previous_choice = entries[-1]['branch'] == 'full'
            return output
        finally:
            s.phase = None


class SamplerAudit:
    def __init__(self, state, *, unpack=None, nested=None, guider_class=None):
        self.state, self.unpack, self.nested, self.guider_class = state, unpack, nested, guider_class

    def __call__(self, executor, model_wrap, sigmas, extra_args, callback, noise,
                 latent_image=None, denoise_mask=None, disable_pbar=False):
        s = self.state
        if s.entered:
            raise ValueError('state is single-use')
        s.entered = True
        try:
            validate_guider(model_wrap, extra_args['model_options'], s, self.guider_class)
            sampler, model = executor.class_obj, model_wrap.inner_model
            if getattr(sampler.sampler_function, '__name__', None) != 'sample_euler' or getattr(sampler, 'extra_options', {}).get('s_churn', 0) != 0:
                raise ValueError('requires unchanged Euler without churn')
            if denoise_mask is not None or getattr(sampler, 'inpaint_options', {}).get('random', False):
                raise ValueError('inpaint masks/randomness unsupported')
            if tuple(tuple(v) for v in model.latent_shapes) != s.config.shapes or model.audio_scale() != 4.0 or model.latent_format.scale_factor != 1.0:
                raise ValueError('H3 geometry/normalization mismatch')
            grid = sigmas.detach().cpu().double().clone()
            if grid.ndim != 1 or len(grid) != 21 or not bool(torch.isfinite(grid).all()) or grid[-1] != 0 or not bool((grid[:-1] > grid[1:]).all()):
                raise ValueError('requires20 strictly decreasing intervals')
            if self.unpack is None:
                from comfy.utils import unpack_latents
                from comfy.nested_tensor import NestedTensor
                s.unpack, s.nested = unpack_latents, NestedTensor
            else:
                s.unpack, s.nested = self.unpack, self.nested
            s.grid, s.guider, s.model = grid, model_wrap, model
            s.original_sigmas = sigmas
            s.seed, s.sample_options = extra_args.get('seed'), extra_args['model_options']
            s.initial_condition = condition_signature(model_wrap)
            s.pair_gate.begin(s, noise)
            c = s.audit['counterfactual']
            c.update(full_grid=grid.tolist(), seed=s.seed, initial_noise=readout.tensor_signature(noise),
                     conditioning=s.initial_condition)
            original_noise = readout.tensor_signature(noise)
            original_rng = rng_state(noise.device)
            def record(index, x0, x, total):
                if type(index) is not int or total != 20 or index != s.callback_count or s.phase is not None or s.transaction is None:
                    raise ValueError('invalid Euler callback order')
                tx = s.transaction
                if tx['physical_index'] != index or len(tx['branches']) != (2 if tx['decision']['chosen_full'] else 1):
                    raise ValueError('callback does not match completed branches')
                expected = tx['chosen']['raw_stream_signatures']
                if [readout.tensor_signature(v) for v in s.raw(x0)] != expected:
                    raise ValueError('Euler did not receive the selected endpoint')
                if [readout.tensor_signature(v) for v in s.raw(x)] != tx['input_stream_signatures']:
                    raise ValueError('callback input mismatch')
                c['steps'].append({'physical_index': index, 'selected_branch': tx['selected_branch'],
                    'chosen_file': tx['chosen']['file'], 'chosen_raw_stream_signatures': expected,
                    'decision': tx['decision'],
                    'nfe_indices': [v['nfe_index'] for v in tx['branches']], 'callback_observed_once': True})
                s.callback_count += 1
                c['callback_count'] = s.callback_count
                s.transaction = None
                s.write()
                if callback is not None:
                    return callback(index, x0, x, total)
            result = executor(model_wrap, sigmas, extra_args, record, noise,
                              latent_image, denoise_mask, disable_pbar)
            nfe = 20 + len(s.full_indices)
            if len(s.audit['counterfactual']['measurements']) != 20 or 0 in s.full_indices or len(s.full_indices)>19:
                raise ValueError('requires20 current native observations and persistence from index0')
            s.pair_gate.finish(s)
            if s.callback_count != 20 or s.audit['completed_forward_calls'] != nfe or s.audit['completed_calls'] != 50 * nfe or s.audit['routed_calls'] != 50 * len(s.full_indices) or s.transaction is not None:
                raise ValueError('incomplete variable-NFE sampling')
            if readout.tensor_signature(noise) != original_noise or condition_signature(model_wrap) != s.initial_condition or readout.tensor_signature(s.reference) != s.reference_signature:
                raise ValueError('noise/condition/reference changed')
            assert_rng(original_rng, noise.device)
            final = s.raw(result)
            readout.atomic_write(s.snapshots / 'sampler_final_raw.pt', {'video': final[0], 'audio': final[1],
                'metadata': {'coordinate_system': 'raw sampler', 'signatures': [readout.tensor_signature(v) for v in final]}}, tensor=True)
            c.update(actual_model_nfe=nfe, actual_full_count=len(s.full_indices),
                     actual_euler_updates=20, all_branch_rng_unchanged=True,
                     full_sigma_dose=sum(float(grid[i]-grid[i+1]) for i in s.full_indices))
            s.audit['status'] = 'complete'
            return result
        except BaseException as error:
            s.audit['status'], s.audit['error'] = 'failed', f'{type(error).__name__}: {error}'
            raise
        finally:
            s.finished, s.phase = True, None
            s.write()
