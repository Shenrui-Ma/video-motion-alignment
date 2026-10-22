"""CPU-only reference prototype for head/bin temporal-direction gating.

Inputs are vectors from one Attention head in one block, before head concat.
reference_probabilities describe internal reference-token routing. Their temporal
centroid is NOT a measurement of physical action delay. No model/device imports.
"""
from dataclasses import dataclass
from math import isfinite, log, sqrt
from typing import Sequence


@dataclass(frozen=True)
class GateConfig:
    alpha: float = 0.45
    min_routing_offset: float = 0.25  # bins; provisional, must freeze before study
    min_concentration: float = 0.15  # 1 - normalized entropy; provisional
    min_tangent_norm: float = 1e-6  # numerical/feature scale guard, not action threshold
    epsilon: float = 1e-12


@dataclass(frozen=True)
class GateResult:
    status: str
    reason: str
    gate: float
    alpha_effective: float
    correction: tuple[float, ...]
    routing_offset_bins: float | None
    concentration: float | None
    cosine: float | None


def norm(vector: Sequence[float]) -> float:
    return sqrt(sum(float(x) ** 2 for x in vector))


def direction_gate(
    native_correction: Sequence[float],
    previous_reference_output: Sequence[float],
    next_reference_output: Sequence[float],
    reference_probabilities: Sequence[float],
    query_bin: int,
    *,
    previous_bin: int,
    next_bin: int,
    config: GateConfig = GateConfig(),
) -> GateResult:
    """Return alpha*g*D; UNKNOWN skips this feedback correction.

    D is m_ref*(S_same - R_all). Neighbor outputs use the SAME query/head,
    with reference K/V restricted to previous_bin or next_bin respectively.
    Caller passes one-sided bin indices at boundaries, without duplicating bins.
    Different heads/layers are never compared by raw channel-vector cosine.
    """
    d = tuple(float(x) for x in native_correction)
    if not d or len(previous_reference_output) != len(d) or len(next_reference_output) != len(d):
        raise ValueError('Attention feature dimensions must match and be nonempty')
    if not 0 <= config.alpha <= 1 or not 0 <= config.min_concentration <= 1:
        raise ValueError('alpha and concentration threshold must be within [0,1]')
    if config.min_routing_offset < 0 or config.min_tangent_norm < 0 or config.epsilon <= 0:
        raise ValueError('thresholds must be nonnegative and epsilon positive')
    if not 0 <= query_bin < len(reference_probabilities):
        raise ValueError('query bin outside reference timeline')
    if not 0 <= previous_bin < next_bin < len(reference_probabilities):
        raise ValueError('neighbor bins must be distinct, ordered and valid')

    def unknown(reason, offset=None, concentration=None):
        return GateResult('UNKNOWN', reason, 0., 0., tuple(0. for _ in d), offset, concentration, None)

    values = (*d, *previous_reference_output, *next_reference_output, *reference_probabilities)
    if not all(isfinite(float(v)) for v in values):
        return unknown('nonfinite_input')
    p = tuple(float(x) for x in reference_probabilities)
    if any(x < 0 for x in p) or sum(p) <= config.epsilon:
        return unknown('invalid_reference_distribution')
    total = sum(p)
    p = tuple(x / total for x in p)
    entropy = -sum(x * log(x) for x in p if x > 0)
    concentration = max(0., min(1., 1. - entropy / log(len(p))))
    offset = query_bin - sum(i * v for i, v in enumerate(p))
    if concentration < config.min_concentration:
        return unknown('diffuse_reference_routing', offset, concentration)
    if abs(offset) < config.min_routing_offset:
        return unknown('small_internal_routing_offset', offset, concentration)
    tangent = tuple((float(n) - float(o)) / (next_bin - previous_bin)
                    for o, n in zip(previous_reference_output, next_reference_output))
    if norm(tangent) < config.min_tangent_norm or norm(d) <= config.epsilon:
        return unknown('low_feature_signal', offset, concentration)
    desired = tuple(offset * t for t in tangent)
    cosine = sum(x * y for x, y in zip(d, desired)) / (norm(d) * norm(desired))
    cosine = max(-1., min(1., cosine))
    gate = max(0., cosine) ** 2
    alpha_eff = config.alpha * gate
    return GateResult('ACTIVE' if gate > 0 else 'SKIP', 'direction_supported' if gate > 0 else 'direction_conflict',
                      gate, alpha_eff, tuple(alpha_eff * x for x in d), offset, concentration, cosine)


def equal_energy_uniform_alpha(
    native_corrections: Sequence[Sequence[float]],
    gated_corrections: Sequence[Sequence[float]],
    *, epsilon: float = 1e-12,
) -> float:
    """Uniform coefficient matching squared correction energy on identical traces.

    Apply this coefficient in a NEW paired generation as a control. Its realized
    energy can then differ because the trajectory changes; record that energy.
    This is neither equality of final pixels nor equality after output projection.
    """
    if len(native_corrections) != len(gated_corrections) or any(
        len(a) != len(b) for a, b in zip(native_corrections, gated_corrections)
    ):
        raise ValueError('matched correction traces required')
    flat_base = [float(x) for row in native_corrections for x in row]
    flat_target = [float(x) for row in gated_corrections for x in row]
    if not all(isfinite(x) for x in (*flat_base, *flat_target)):
        raise ValueError('finite traces required')
    base_energy = sum(x*x for x in flat_base)
    target_energy = sum(x*x for x in flat_target)
    if base_energy <= epsilon:
        if target_energy > epsilon:
            raise ValueError('nonzero correction cannot match zero base energy')
        return 0.
    return sqrt(target_energy / base_energy)
