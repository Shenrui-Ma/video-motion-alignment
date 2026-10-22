import numpy as np
import librosa
import sys
from pathlib import Path

from alignment.flexdtw import flexdtw

def run_global_dtw(y_query, y_ref, sr=22050):
    """Run standard Global DTW."""
    F_q = librosa.feature.chroma_cqt(y=y_query, sr=sr, norm=2)
    F_r = librosa.feature.chroma_cqt(y=y_ref, sr=sr, norm=2)
    # F_q is (12, N_q), F_r is (12, N_r)
    # We want C to be (N_q, N_r)
    C = 1 - np.dot(F_q.T, F_r)
    
    step_sizes_sigma = np.array([[1, 1], [1, 2], [2, 1]])
    weights_mul = np.array([2, 3, 3])
    D, wp = librosa.sequence.dtw(
        C=C,
        step_sizes_sigma=step_sizes_sigma,
        weights_mul=weights_mul,
        subseq=False
    )

    return wp, C  # (N, 2) array of (query_idx, ref_idx)

def run_flex_dtw_on_subrectangle(C, q_range, r_range, buffer=None, return_debug=False):
    """
    Runs FlexDTW on a specific sub-rectangle of the cost matrix
    q_range: (q_start, q_end) in frames
    r_range: (r_start, r_end) in frames
    """
    q_start, q_end = q_range
    r_start, r_end = r_range
    
    # Slice cost matrix
    C_sub = C[q_start : q_end + 1, r_start : r_end + 1]
    
    if C_sub.size == 0:
        if return_debug:
            return np.empty((0, 2)), None, None, None
        return np.empty((0, 2))
    
    # Compute buffer
    if buffer is None:
        min_len, max_len = min(C_sub.shape), max(C_sub.shape)
        ratio = min_len / max_len
        buffer = min_len * (1 - 0.9 * ratio)
    steps = np.array([(1, 1), (1, 2), (2, 1)])
    weights = np.array([2, 3, 3])
    
    # Run FlexDTW
    try:
        best_cost, wp_local, debug, D, B, P = flexdtw(C_sub, steps, weights, buffer)
        wp_local = wp_local.T # (N, 2)
    except Exception as e:
        print(f"FlexDTW subrectangle error: {e}")
        if return_debug:
            return np.empty((0, 2)), None, None, None
        return np.empty((0, 2))
    
    # Translate back to global coordinates
    wp_global = np.empty((0, 2))
    if len(wp_local) > 0:
        wp_global = wp_local.copy()
        wp_global[:, 0] += q_start
        wp_global[:, 1] += r_start
    
    if return_debug:
        return wp_global, debug, D, P
    
    return wp_global
