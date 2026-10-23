"""CPU-only signed retrieval-phase oracle, not an H3 controller.

The supplied logit derivative must come from a real downstream observation
Jacobian. A current attention output correction is NOT a query derivative.
Only NumPy is used. No model, server, runtime, or queue code is imported.
"""
from __future__ import annotations

import math
import numpy as np


def vector(value, name):
    x = np.asarray(value, dtype=np.float64)
    if x.ndim != 1 or x.size == 0 or not np.isfinite(x).all():
        raise ValueError(name + " must be a nonempty finite vector")
    return x


def softmax(logits):
    z = vector(logits, "logits")
    ex = np.exp(z - np.max(z))
    return ex / ex.sum()


def phase(logits, times, target_time, logit_derivative=None):
    """Return signed retrieval mean and exact derivative for supplied z'."""
    z, tau = vector(logits, "logits"), vector(times, "times")
    if z.shape != tau.shape or not math.isfinite(target_time):
        raise ValueError("incompatible phase inputs")
    p = softmax(z)
    mean = float(p @ tau)
    result = {"probabilities": p, "retrieval_error": mean - target_time,
              "variance_time": float(p @ (tau - mean) ** 2)}
    if logit_derivative is not None:
        g = vector(logit_derivative, "logit_derivative")
        if g.shape != z.shape:
            raise ValueError("incompatible derivative")
        mean_g = float(p @ g)
        result["signed_sensitivity"] = float(p @ ((tau - mean) * (g - mean_g)))
        # Exact second derivative only when z(alpha)=z+alpha*g.
        result["affine_logit_second_derivative"] = float(
            p @ ((tau - mean) * (g - mean_g) ** 2))
    return result


def box_linearized_ls(error, sensitivity, *, alpha_prior=0.25, alpha_cap=0.5):
    """Minimize (e+alpha*s)^2 on a box; no gain/semantic claim.

    A zero or numerically flat sensitivity returns the prior. The flatness
    floor concerns floating-point arithmetic only, not a learned confidence
    threshold. Real use still requires independent identifiability tests.
    """
    if not all(math.isfinite(x) for x in (error, sensitivity, alpha_prior, alpha_cap)):
        raise ValueError("nonfinite scalar")
    if not 0 <= alpha_prior <= alpha_cap or alpha_cap <= 0:
        raise ValueError("invalid alpha bounds")
    floor = 64 * np.finfo(np.float64).eps * max(1.0, abs(error))
    if abs(sensitivity) <= floor:
        return {"alpha": alpha_prior, "status": "unobserved_sensitivity",
                "predicted_error": error + alpha_prior * sensitivity}
    alpha = float(np.clip(-error / sensitivity, 0, alpha_cap))
    return {"alpha": alpha, "status": "oracle_only",
            "predicted_error": error + alpha * sensitivity}


def gaussian_content(times, location, sigma=1.0):
    tau = vector(times, "times")
    if not math.isfinite(location) or not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("invalid Gaussian diagnostic")
    # Can be represented as dot product [location/sigma², 1/sigma²]
    # with key [time, -time²/2], up to a query-only additive constant.
    return -0.5 * ((tau - location) / sigma) ** 2


def role_preserving_content(times, query_bin, motion_location, *, period=5,
                            role_strength=20.0, sigma=1.0):
    """Synthetic latent role remains at t%5 while only motion is shifted."""
    tau = vector(times, "times")
    if period <= 0 or type(period) is not int:
        raise ValueError("invalid period")
    roles = np.remainder(np.arange(tau.size), period)
    z = gaussian_content(tau, motion_location, sigma)
    return z + role_strength * (roles == query_bin % period)


def grouped_lse_derivative(token_logits, token_derivative, groups):
    """Exact grouped LSE and its derivative; includes within-bin weighting."""
    z, g = vector(token_logits, "token_logits"), vector(token_derivative, "token_derivative")
    ids = np.asarray(groups)
    if z.shape != g.shape or ids.shape != z.shape or ids.dtype.kind not in "iu":
        raise ValueError("invalid grouped inputs")
    unique = np.unique(ids)
    if not np.array_equal(unique, np.arange(len(unique))):
        raise ValueError("groups must cover contiguous nonnegative IDs")
    out_z, out_g = [], []
    for group in unique:
        zg, gg = z[ids == group], g[ids == group]
        peak = np.max(zg)
        out_z.append(float(peak + np.log(np.exp(zg - peak).sum())))
        out_g.append(float(softmax(zg) @ gg))
    return np.array(out_z), np.array(out_g)


def affine_remainder_bound(times, logit_derivative, alpha):
    """Conservative |e(alpha)-e(0)-alpha*e'(0)| bound for affine logits."""
    tau, g = vector(times, "times"), vector(logit_derivative, "logit_derivative")
    if tau.shape != g.shape or not math.isfinite(alpha):
        raise ValueError("invalid remainder inputs")
    return 0.5 * alpha ** 2 * float(np.ptp(tau)) * float(np.ptp(g)) ** 2


def rms_jvp(x, dx, eps=1e-6):
    """Continuous RMSNorm oracle and exact directional derivative."""
    x, dx = vector(x, "x"), vector(dx, "dx")
    if x.shape != dx.shape or eps <= 0:
        raise ValueError("invalid RMSNorm inputs")
    root = float(np.sqrt(np.mean(x*x) + eps))
    return x/root, dx/root - x*float(np.mean(x*dx))/(root**3)


def continuous_local_chain(alpha, x, native, correction, weights):
    """Small float64 structural oracle, NOT the quantized H3 implementation.

    Current attention output -> output projection/gate -> MLP residual ->
    next-block norm/query projection/query norm. Reference keys can be fixed
    only when their current attention outputs have already been computed.
    """
    w = weights
    residual = x + w['gate_attention']*(w['out']@(native+alpha*correction))
    dresidual = w['gate_attention']*(w['out']@correction)
    n, dn = rms_jvp(residual,dresidual)
    u, du = w['scale_mlp']*n+w['shift_mlp'],w['scale_mlp']*dn
    left,right = w['up1']@u,w['up2']@u
    dleft,dright = w['up1']@du,w['up2']@du
    sigmoid = 1/(1+np.exp(-left))
    silu = left*sigmoid
    dsilu = (sigmoid+left*sigmoid*(1-sigmoid))*dleft
    ff = residual+w['gate_mlp']*(w['down']@(silu*right))
    dff = dresidual+w['gate_mlp']*(w['down']@(dsilu*right+silu*dright))
    n,dn = rms_jvp(ff,dff)
    qraw = w['query']@(w['scale_next']*n+w['shift_next'])
    dqraw = w['query']@(w['scale_next']*dn)
    return rms_jvp(qraw,dqraw)


def examples():
    tau = np.arange(-20, 21, dtype=np.float64)
    examples = {}
    for lag in (-5.0, 0.0, 5.0):
        # lag > 0 means the query content is like an earlier reference time.
        z = gaussian_content(tau, -lag)
        result = phase(z, tau, 0, lag * tau)
        estimate = box_linearized_ls(result["retrieval_error"], result["signed_sensitivity"])
        examples[str(lag)] = {k: v for k, v in result.items() if k != "probabilities"} | estimate
    z = gaussian_content(tau, -5)
    examples["indistinguishable_worlds"] = {
        "observed_retrieval_error": phase(z, tau, 0)["retrieval_error"],
        "world_1_true_motion_lag": 5.0,
        "world_2_true_motion_lag": 0.0,
        "world_2_appearance_query_shift": -5.0,
        "same_Q_K_V_D_can_be_observed": True,
    }
    e = phase(z, tau, 0)["retrieval_error"]
    examples["same_block"] = {"true_current_attention_derivative": 0.0,
                              "post_mixture_derivative": -e,
                              "post_mixture_box_optimum": 0.5,
                              "is_independent_motion_validation": False}
    return examples
