import numpy as np

def compute_percent_agreement_zerotol(global_wp, flex_wp, q_start, q_end):
    """
    Computes % agreement between two warping paths in a specific query frame range.
    
    Args:
        global_wp: (N, 2) numpy array of (query_idx, ref_idx) (the primary path).
        flex_wp: (M, 2) numpy array of (query_idx, ref_idx) (the benchmark path).
        q_start, q_end: range of query frames (inclusive).
        
    Returns:
        score: ratio of global path points in range that are also in the flex path.
    """
    # Extract points from global_wp within the query range
    mask_global = (global_wp[:, 0] >= q_start) & (global_wp[:, 0] <= q_end)
    points_in_chunk = global_wp[mask_global]
    
    if len(points_in_chunk) == 0:
        return 0.0
    
    flex_set = set(map(tuple, flex_wp))
    
    match_count = 0
    for pt in points_in_chunk:
        if tuple(pt) in flex_set:
            match_count += 1
            
    return match_count / len(points_in_chunk)

def compute_percent_agreement(global_wp, flex_wp, q_start, q_end, X = 0):

    if X == 0:
        return compute_percent_agreement_zerotol(global_wp, flex_wp, q_start, q_end)
    
    # 1. Filter points in range
    mask_global = (global_wp[:, 0] >= q_start) & (global_wp[:, 0] <= q_end)
    points_in_chunk = global_wp[mask_global]
    
    if len(points_in_chunk) == 0:
        return 0.0
    
    # 2. Calculate Euclidean distance between all pairs
    # points_in_chunk shape: (N, 2), flex_wp shape: (M, 2)
    # diffs shape becomes (N, M, 2)
    diffs = points_in_chunk[:, np.newaxis, :] - flex_wp[np.newaxis, :, :]
    # dists shape becomes (N, M)
    dists = np.linalg.norm(diffs, axis=2)
    
    # 3. Check if min distance for each point is <= x_dist
    within_threshold = np.any(dists <= X, axis=1)
    
    return np.mean(within_threshold)