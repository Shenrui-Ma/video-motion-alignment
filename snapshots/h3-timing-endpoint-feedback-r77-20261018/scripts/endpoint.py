"""Single-step clean-endpoint feedback and passive packed-state audit.

No Comfy or CUDA initialization at import. A provider receives a CPU copy of the
current prediction; lifecycle and pose/VAE execution are supplied separately.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import time

import torch


def signature(value):
    value = value.detach().to('cpu').contiguous()
    return {'shape': list(value.shape), 'dtype': str(value.dtype),
            'sha256': hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()}


def require(test, message):
    if not test:
        raise ValueError(message)


def euler(x, z, sigma, next_sigma):
    # Preserve the order used by sample_euler; use actual float32 sigma scalars.
    s = x.new_tensor(sigma)
    dt = x.new_tensor(next_sigma) - s
    return x + ((x - z) / s) * dt


def gain(arm, sigma, next_sigma):
    c = (sigma - next_sigma) / sigma
    require(sigma > next_sigma >= 0 and c > 0, 'invalid Euler step')
    if arm == 'A':
        return 0.0
    if arm == 'B':
        return 1.0
    if arm == 'C':
        return (1 - next_sigma) / c
    raise ValueError('unknown arm')


@dataclass(frozen=True)
class Config:
    run_id: str
    arm: str
    output: str
    sigmas: tuple
    video_shape: tuple = (1, 24, 47, 48, 72)
    audio_shape: tuple = (1, 32, 2, 263)
    step: int = 6

    def __post_init__(self):
        require(self.arm in ('A', 'B', 'C') and self.step == 6, 'frozen A/B/C index6 contract')
        require(len(self.sigmas) == 21 and self.sigmas[-1] == 0 and
                all(math.isfinite(x) for x in self.sigmas) and
                all(a > b for a, b in zip(self.sigmas, self.sigmas[1:])), 'Euler20 sigma grid')
        require(self.video_shape == (1, 24, 47, 48, 72) and
                self.audio_shape == (1, 32, 2, 263), 'R65 fitness AV shape required')
        require(Path(self.output).is_absolute(), 'absolute audit directory required')
        require(self.run_id and Path(self.run_id).name == self.run_id and
                self.run_id not in ('.', '..'), 'safe run id required')


@dataclass
class Proposal:
    delta: torch.Tensor
    mask: torch.Tensor
    current_video_sha256: str
    basis: str = 'current_x0'
    eligible: bool = True
    evidence: dict = None


class EndpointController:
    """One controller per complete sampler call; never reused across runs."""
    r77_endpoint_hook = True

    def __init__(self, config, provider):
        self.config, self.provider = config, provider
        self.active = False
        self.count = 0
        self.expected_next = None
        self.report = {'schema': 'r77-endpoint-audit-v1', 'run_id': config.run_id,
                       'arm': config.arm, 'status': 'not_started', 'calls': [],
                       'intervention_steps': [], 'proposal_calls': 0}

    def _json(self):
        path = self.directory / 'REPORT.json'
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.report, indent=2, allow_nan=False) + '\n')
        temp.replace(path)

    def begin(self, sigmas):
        require(not self.active and self.report['status'] == 'not_started', 'single sampler invocation required')
        actual = sigmas.detach().to('cpu')
        expected = torch.tensor(self.config.sigmas, dtype=torch.float32)
        require(actual.dtype == torch.float32 and torch.equal(actual, expected), 'actual sigma grid differs')
        directory = Path(self.config.output) / self.config.run_id
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.active = True
        self.report.update(status='running', started_unix=time.time(), sigmas=actual.tolist(),
                           normalization='video normalized VAE latent; packed audio stays sampler-scaled')
        self._json()

    def _packed(self, value):
        n = math.prod(self.config.video_shape)
        total = n + math.prod(self.config.audio_shape)
        require(isinstance(value, torch.Tensor) and not value.is_nested and
                tuple(value.shape) == (1, 1, total) and value.dtype == torch.float32,
                'exact packed float32 AV shape required')
        require(bool(torch.isfinite(value).all()), 'nonfinite packed tensor')
        return value[..., :n].view(self.config.video_shape), value[..., n:]

    @torch.no_grad()
    def __call__(self, args):
        require(self.active and self.count < 20, 'hook outside active Euler20 or duplicate call')
        i = self.count
        x, z = args['input'], args['denoised']
        video, audio = self._packed(z)
        self._packed(x)
        require(x.device == z.device and args['cond_scale'] == 1, 'CFG1 and shared state device required')
        sigma = args['sigma'].detach().to('cpu').flatten()
        require(sigma.numel() == 1 and float(sigma[0]) == self.config.sigmas[i], 'duplicate/skipped sigma or wrong order')
        # Copies only: audit/proposal code cannot mutate the live model inputs.
        row = {'index': i, 'sigma': float(sigma[0]), 'input': signature(x),
               'pre_hook_endpoint': signature(z)}
        if i in (6, 7, 12, 19):
            torch.save({'input': x.detach().cpu().clone(),
                        'pre_hook_endpoint': z.detach().cpu().clone()}, self.directory / f'step{i:03d}_pre.pt')
        if self.expected_next is not None:
            actual = x.detach().cpu()
            expected = self.expected_next
            error = (actual - expected).abs()
            # This exact packed input is before KSamplerX0Inpaint changes (mask forbidden).
            require(torch.allclose(actual, expected, rtol=2e-6, atol=2e-6), 'observed x7 differs from actual float32 Euler update')
            row['x7_check'] = {'max_abs': float(error.max()), 'mean_abs': float(error.mean()),
                               'rtol': 2e-6, 'atol': 2e-6, 'passed': True}
            self.expected_next = None
        result = z
        if i == self.config.step:
            cpu_video = video.detach().to('cpu', copy=True).contiguous()
            context = {'run_id': self.config.run_id, 'step': i,
                       'video': signature(cpu_video), 'packed_input': row['input'],
                       'sigma': self.config.sigmas[i], 'next_sigma': self.config.sigmas[i+1]}
            proposal = self.provider(cpu_video.clone(), json.loads(json.dumps(context)))
            self.report['proposal_calls'] += 1
            require(isinstance(proposal, Proposal) and proposal.basis == 'current_x0', 'current-x0 proposal required')
            require(proposal.current_video_sha256 == context['video']['sha256'], 'proposal belongs to another trajectory')
            require(tuple(proposal.delta.shape) == self.config.video_shape and
                    proposal.delta.dtype == torch.float32 and proposal.delta.device.type == 'cpu' and
                    bool(torch.isfinite(proposal.delta).all()), 'invalid proposal delta')
            require(tuple(proposal.mask.shape) == (47,) and proposal.mask.device.type == 'cpu' and
                    bool(torch.isfinite(proposal.mask).all()) and bool(((proposal.mask >= 0) & (proposal.mask <= 1)).all()),
                    'invalid temporal support mask')
            require(bool((proposal.mask[13:] == 0).all()), 'mask crosses frozen first2s output domain')
            require(bool((proposal.delta[:, :, proposal.mask == 0] == 0).all()), 'delta outside declared support')
            lam = gain(self.config.arm, self.config.sigmas[i], self.config.sigmas[i+1]) if proposal.eligible else 0.0
            if lam and bool((proposal.delta != 0).any()):
                result = z.clone()
                new_video, new_audio = self._packed(result)
                new_video.add_(proposal.delta.to(z.device), alpha=lam)
                require(torch.equal(new_audio.view(torch.uint8), audio.view(torch.uint8)), 'packed audio changed')
                require(bool(torch.isfinite(result).all()), 'nonfinite feedback result')
                self.report['intervention_steps'].append(i)
            self.expected_next = euler(x, result, self.config.sigmas[i], self.config.sigmas[i+1]).detach().cpu().clone()
            original_next = euler(x, z, self.config.sigmas[i], self.config.sigmas[i+1])
            observed_delta = self.expected_next - original_next.detach().cpu()
            n = math.prod(self.config.video_shape)
            c = (self.config.sigmas[i] - self.config.sigmas[i+1]) / self.config.sigmas[i]
            analytic = torch.zeros_like(observed_delta)
            analytic[..., :n] = (proposal.delta * (c * lam)).reshape(1, 1, n)
            torch.save({'post_hook_endpoint': result.detach().cpu().clone(),
                        'expected_next_input': self.expected_next,
                        'delta_video': proposal.delta, 'mask': proposal.mask,
                        'proposal_context': context}, self.directory / 'intervention.pt')
            row['proposal'] = {'eligible': proposal.eligible, 'basis': proposal.basis,
                               'video_sha256': proposal.current_video_sha256,
                               'mask': proposal.mask.tolist(), 'lambda': lam, 'c': c,
                               'nominal_next_state_delta_factor': c * lam,
                               'analytic_increment_max_abs_error': float((observed_delta-analytic).abs().max()),
                               'evidence': proposal.evidence or {}}
        row['post_hook_endpoint'] = signature(result)
        self.report['calls'].append(row)
        self.count += 1
        self._json()
        return result

    def finish(self, final):
        require(self.active and self.count == 20 and self.expected_next is None, 'incomplete trajectory')
        self._packed(final)
        require(self.report['proposal_calls'] == 1, 'exactly one proposal required')
        require(self.report['intervention_steps'] in ([], [6]), 'unexpected intervention count')
        torch.save({'sampler_final_packed': final.detach().cpu().clone()}, self.directory / 'final.pt')
        self.report.update(status='complete', final=signature(final), finished_unix=time.time())
        self.active = False
        self._json()

    def fail(self, error):
        self.report.update(status='failed', error=repr(error), finished_unix=time.time())
        self.active = False
        if hasattr(self, 'directory'):
            self._json()


def install(model, config, provider):
    """Comfy integration API. No production graph/node is registered by this file."""
    from comfy.patcher_extension import WrappersMP
    require(not model.model_options.get('sampler_post_cfg_function'), 'other post-CFG hooks require explicit audit')
    key = 'R77/single_endpoint'
    require(not model.get_wrappers(WrappersMP.SAMPLER_SAMPLE, key), 'R77 already installed')
    controller = EndpointController(config, provider)

    def sample_wrapper(executor, model_wrap, sigmas, extra_args, callback, noise,
                       latent_image=None, denoise_mask=None, disable_pbar=False):
        sampler = getattr(executor, 'class_obj', None)
        require(getattr(getattr(sampler, 'sampler_function', None), '__name__', None) == 'sample_euler', 'Euler required')
        require(getattr(sampler, 'extra_options', {}).get('s_churn', 0) == 0 and denoise_mask is None, 'churn/inpaint masks unsupported')
        actual = model_wrap.inner_model
        require(tuple(tuple(s) for s in actual.latent_shapes) == (config.video_shape, config.audio_shape), 'actual AV layout differs')
        require(float(actual.audio_scale()) == 4 and float(actual.latent_format.scale_factor) == 1, 'actual normalization differs')
        try:
            controller.begin(sigmas)
            result = executor(model_wrap, sigmas, extra_args, callback, noise, latent_image, denoise_mask, disable_pbar)
            controller.finish(result)
            return result
        except BaseException as error:
            controller.fail(error)
            raise

    cloned = model.clone()
    cloned.set_model_sampler_post_cfg_function(controller)
    cloned.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE, key, sample_wrapper)
    return cloned, controller
