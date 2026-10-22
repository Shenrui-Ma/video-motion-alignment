"""Known codec-residual controls, using the original frozen R70 time operator."""
import sys
from pathlib import Path
import numpy as np
import torch
PARENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PARENT / 'scripts'))
import operators


def check_latents(*values):
    for value in values:
        if value.device.type != 'cpu' or value.dtype != torch.float32 or tuple(value.shape) != (1,24,47,48,72):
            raise ValueError('expected CPU float32 H3 video latent [1,24,47,48,72]')
        if not bool(torch.isfinite(value).all()):
            raise ValueError('nonfinite latent')


def apply(z, e_identity, e_phi, coordinates, mode):
    check_latents(z, e_identity, e_phi)
    positions = np.asarray(coordinates['latent_positions'], dtype=np.float64)
    if positions.shape != (47,) or not np.isfinite(positions).all():
        raise ValueError('47 finite frozen latent positions required')
    if mode not in ('anchor','transport'):
        raise ValueError('unknown codec residual mode')
    # Algebraic identity plus signed-zero preservation. No numerical branch for tested nonidentity maps.
    if np.array_equal(positions, np.arange(47)) and torch.equal(e_identity, e_phi):
        return z.clone()
    if mode == 'anchor':
        output = z + (e_phi - e_identity)
    else:
        output = operators.interpolate(z, positions, 2) + (e_phi - operators.interpolate(e_identity, positions, 2))
    check_latents(output)
    return output.contiguous()
