import hashlib,json,uuid
import torch
from H3X0Readout import core as readout

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


