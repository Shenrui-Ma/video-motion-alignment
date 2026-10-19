"""Read-only evidence for the frozen official same-device sigma mapping.

The sampling grid and the head's derived sigma are distinct numeric objects.
No tolerance, input replacement, or CPU reconstruction is used by live checks.
"""
import math
import torch
from .source import require


def tensor_record(value):
    if not isinstance(value, torch.Tensor):
        return {'type': type(value).__name__, 'tensor': False}
    flat = value.detach().flatten()
    record = {'tensor': True, 'dtype': str(value.dtype), 'device': str(value.device),
              'shape': list(value.shape), 'numel': value.numel()}
    # Only small schedule/time tensors are admitted; never copy model activations.
    if value.numel() <= 21:
        numbers = flat.cpu().tolist()
        record['values'] = [float(x) if math.isfinite(float(x)) else None for x in numbers]
        record['nonfinite_indices'] = [i for i, x in enumerate(numbers) if not math.isfinite(float(x))]
        if value.dtype == torch.float32:
            record['raw_bits_hex'] = [f'{x & 0xffffffff:08x}' for x in flat.contiguous().view(torch.int32).cpu().tolist()]
    return record


def official_head_sigma(timestep):
    # comfy/ldm/minimax/model.py MiniMaxH3Model._forward, frozen line628.
    return (timestep.flatten()[0] / 1000.0).float().clamp(min=1e-6)


def exact_tensor(actual, expected):
    return (isinstance(actual, torch.Tensor) and isinstance(expected, torch.Tensor)
            and actual.dtype == expected.dtype and actual.device == expected.device
            and actual.shape == expected.shape and torch.equal(actual, expected))


def timestep_evidence(entry, actual, sampling):
    expected = sampling.timestep(entry).float()
    return {'entry_sigma': tensor_record(entry), 'actual_timestep': tensor_record(actual),
            'expected_timestep': tensor_record(expected),
            'exact_official_timestep': exact_tensor(actual, expected)}, expected


def check_timestep(entry, actual, expected, full_grid):
    require(entry.dtype == torch.float32 and entry.shape == (1,) and
            float(entry[0]) == full_grid[4], 'entry sigma/index4 changed')
    require(exact_tensor(actual, expected), 'actual timestep differs from official same-device sampling path')


def head_evidence(actual, timestep, grid, shifts):
    expected = official_head_sigma(timestep)
    index = None
    if (isinstance(grid, torch.Tensor) and isinstance(actual, torch.Tensor)
            and grid.device == actual.device and grid.dtype == actual.dtype == torch.float32
            and grid.shape == (21,) and actual.shape == ()
            and bool(torch.isfinite(grid).all()) and bool(torch.isfinite(actual).all())):
        index = int((grid - actual).abs().argmin())
    try:
        shift_values = [float(x) for x in shifts]
        shift_values = [x if math.isfinite(x) else None for x in shift_values]
    except (TypeError, ValueError):
        shift_values = None
    return {'actual_head_sigma': tensor_record(actual), 'expected_head_sigma': tensor_record(expected),
            'actual_grid': tensor_record(grid), 'actual_index': index, 'actual_shifts': shift_values,
            'exact_official_head_sigma': exact_tensor(actual, expected)}, expected


def check_head(actual, expected, grid, shifts, full_grid, evidence):
    require(isinstance(grid, torch.Tensor) and grid.dtype == torch.float32 and
            grid.shape == (21,) and grid.detach().cpu().tolist() == full_grid, 'actual output head full grid changed')
    require(evidence['actual_index'] == 4, 'actual output head nearest grid index changed')
    require(evidence['actual_shifts'] == [12.0, 3.0], 'actual output head shifts changed')
    require(exact_tensor(actual, expected), 'actual head sigma differs from official same-device timestep path')
