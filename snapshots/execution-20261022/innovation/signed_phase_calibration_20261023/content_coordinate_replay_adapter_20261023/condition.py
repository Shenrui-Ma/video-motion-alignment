"""Reference-only content exchange; original payload and coordinate noise retained."""
import copy
from contextlib import contextmanager
import types
import torch
try:
    from .identity import tensor_info, exact_tensor
except ImportError:
    from identity import tensor_info, exact_tensor


def swap_latent(z):
    if z.ndim != 5 or z.shape[2] != 32 or z.dtype != torch.float32 or not bool(torch.isfinite(z).all()):
        raise ValueError('full 32-bin FP32 reference required')
    idx = torch.arange(32, device=z.device)
    idx[5:10] = torch.arange(10, 15, device=z.device)
    idx[10:15] = torch.arange(5, 10, device=z.device)
    return z.index_select(2, idx)  # Preserve original device and dtype, allocate storage.


def prepared_payload(guider):
    pos = guider.conds.get('positive', [])
    if len(pos) != 1 or guider.conds.get('negative'):
        raise ValueError('one BasicGuider positive condition required')
    return pos[0]['model_conds']['minimax_payload'].cond


@contextmanager
def replaced_reference(guider, swap):
    original = guider.conds
    payload = prepared_payload(guider)
    zs, refs = payload['cond_video_latents'], payload['refs']
    if len(zs) != 1 or len(refs) != 1 or refs[0]['kind'] != 'video' or refs[0]['latent'] is not zs[0]:
        raise ValueError('single shared reference latent required')
    z = zs[0]
    before = tensor_info(z)
    replacement = swap_latent(z) if swap else z.clone()
    new_payload = dict(payload)
    new_refs = [dict(refs[0])]
    new_refs[0]['latent'] = replacement
    new_payload['refs'] = new_refs
    new_payload['cond_video_latents'] = [replacement]
    cond = dict(original)
    item = dict(original['positive'][0])
    model_conds = dict(item['model_conds'])
    constant = copy.copy(model_conds['minimax_payload'])
    constant.cond = new_payload
    model_conds['minimax_payload'] = constant
    item['model_conds'] = model_conds
    cond['positive'] = [item]
    guider.conds = cond
    try:
        yield new_payload
    finally:
        guider.conds = original
        if tensor_info(z) != before:
            raise ValueError('original reference mutated')


class ConditionRowsOracle:
    """Call original method; compare its rows to exact patch-row RNG arithmetic.

    New noise is generated privately on CPU. The original returned object is
    preserved. Never moves z before augmentation or patches global randn.
    """
    def __init__(self, model):
        self.model = model
        self.calls = []
        self.had_override = '_cond_video_rows' in model.__dict__
        self.original_override = model.__dict__.get('_cond_video_rows')
        self.original = model._cond_video_rows
        self.patchify = self.original.__func__.__globals__['patchify_video']
        self.noise = None

    def __enter__(self):
        def wrapped(this, payload, device):
            actual = self.original(payload, device)
            zs = payload.get('cond_video_latents', [])
            if len(zs) != 1 or float(payload.get('visual_cond_noise_aug', .999)) != .999 or int(payload.get('seed', 0)) != 2026101701:
                raise ValueError('conditioning noise recipe changed')
            z = zs[0]
            rows = self.patchify(z.to(torch.float32), this.patch_size)
            if tuple(rows.shape) != (30176, 96):
                raise ValueError('actual patch-row noise shape mismatch')
            rng = torch.Generator('cpu').manual_seed(2026101701)
            noise = torch.randn(rows.shape, generator=rng, dtype=torch.float32)
            expected = .999 * rows + (1.0 - .999) * noise.to(rows.device)
            exact_tensor(actual, expected.to(device), 'original augmented conditioning rows')
            if self.noise is not None:
                exact_tensor(noise, self.noise, 'same coordinate noise across calls')
            else:
                self.noise = noise.clone()
            self.calls.append(dict(noise=tensor_info(noise), augmented_rows=tensor_info(actual),
                                   source_latent_device=str(z.device), source_latent_dtype=str(z.dtype),
                                   arithmetic_device=str(rows.device), arithmetic_dtype=str(rows.dtype)))
            return actual
        self.model._cond_video_rows = types.MethodType(wrapped, self.model)
        return self

    def __exit__(self, typ, value, tb):
        if self.had_override:
            self.model._cond_video_rows = self.original_override
        else:
            del self.model._cond_video_rows
        return False
