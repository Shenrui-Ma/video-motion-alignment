"""Original overlap-to-bin rule with explicit full geometry and valid time domain."""
import importlib
from .dependencies import router, layout
from .geometry import LEGACY
QueryGain = importlib.import_module(router.__package__ + '.mask').QueryGain


def bins_for(intervals, geometry=LEGACY):
    bins = set()
    mapping = []
    for value in intervals:
        if not isinstance(value, (list, tuple)) or len(value) != 2 or any(type(x) is not int for x in value):
            raise ValueError('physical intervals require integer inclusive bounds')
        a, b = value
        if not 0 <= a <= b < geometry.valid_frames:
            raise ValueError('physical interval outside valid observation domain')
        lo, hi = layout.event_latent_range(a, b, geometry.latent_bins)
        bins.update(range(lo, hi))
        mapping.append({'physical_interval': [a, b], 'latent_interval_half_open': [lo, hi]})
    return sorted(bins), mapping


def bin_coverage(bins, geometry=LEGACY):
    """Descriptive only: actual execution still uses complete positional bins."""
    spans = layout.frame_spans(geometry.latent_bins)
    rows = []
    for i in bins:
        if type(i) is not int or not 0 <= i < geometry.latent_bins:
            raise ValueError('invalid positional bin')
        start = sum(spans[:i])
        end = start + spans[i] - 1
        rows.append({'bin': i, 'nominal_frames_inclusive': [start, end],
                     'padding_spillover_frames': list(range(max(start, geometry.valid_frames), end + 1))})
    return rows


def make_gain(bins, spatial_shape=None, *, geometry=LEGACY):
    import torch
    if list(bins) != sorted(set(bins)) or any(type(i) is not int or not 0 <= i < geometry.latent_bins for i in bins):
        raise ValueError('bins require sorted unique in-range integers')
    # spatial_shape permits only the inherited small dense-oracle test fixture.
    spatial_shape = geometry.spatial_shape if spatial_shape is None else spatial_shape
    values = torch.zeros((geometry.latent_bins, *spatial_shape), dtype=torch.float32, device='cpu')
    if bins:
        values[bins] = 1
    return QueryGain(values, expected_shape=values.shape)
