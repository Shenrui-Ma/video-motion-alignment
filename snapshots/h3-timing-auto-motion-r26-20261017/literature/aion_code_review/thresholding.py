"""
Thresholding techniques for anomaly detection evaluation.
Implements global and adaptive/local thresholding methods.
"""

import numpy as np
from sklearn.metrics import roc_curve, precision_recall_curve
from scipy import stats


def global_threshold_mean_std(benign_scores, multiplier=2.0):
    """
    Global threshold based on mean + k*std of benign scores.
    
    Parameters:
        benign_scores: Array of anomaly scores from benign samples
        multiplier: Number of standard deviations (default: 2.0 for ~95% coverage)
    
    Returns:
        threshold: Global threshold value
    """
    if len(benign_scores) == 0:
        return 0.0
    
    mean_score = np.mean(benign_scores)
    std_score = np.std(benign_scores)
    threshold = mean_score + multiplier * std_score
    return threshold


def global_threshold_percentile(benign_scores, percentile=95):
    """
    Global threshold based on percentile of benign scores.
    
    Parameters:
        benign_scores: Array of anomaly scores from benign samples
        percentile: Percentile to use (default: 95)
    
    Returns:
        threshold: Global threshold value
    """
    if len(benign_scores) == 0:
        return 0.0
    
    threshold = np.percentile(benign_scores, percentile)
    return threshold


def global_threshold_median_iqr(benign_scores, multiplier=1.5):
    """
    Global threshold based on median + k*IQR (Interquartile Range).
    More robust to outliers than mean+std.
    
    Parameters:
        benign_scores: Array of anomaly scores from benign samples
        multiplier: IQR multiplier (default: 1.5, similar to box plot whiskers)
    
    Returns:
        threshold: Global threshold value
    """
    if len(benign_scores) == 0:
        return 0.0
    
    median_score = np.median(benign_scores)
    q75 = np.percentile(benign_scores, 75)
    q25 = np.percentile(benign_scores, 25)
    iqr = q75 - q25
    threshold = median_score + multiplier * iqr
    return threshold


def global_threshold_max(benign_scores, safety_margin=0.1):
    """
    Global threshold based on maximum benign score with safety margin.
    
    Parameters:
        benign_scores: Array of anomaly scores from benign samples
        safety_margin: Additional margin as fraction of max (default: 0.1 = 10%)
    
    Returns:
        threshold: Global threshold value
    """
    if len(benign_scores) == 0:
        return 0.0
    
    max_score = np.max(benign_scores)
    threshold = max_score * (1 + safety_margin)
    return threshold


def adaptive_threshold_sliding_window(scores, window_size=50, percentile=95):
    """
    Adaptive threshold using sliding window percentile.
    Threshold adapts to local distribution of scores.
    
    Parameters:
        scores: Array of anomaly scores (can include both benign and attack)
        window_size: Size of sliding window
        percentile: Percentile to use within window (default: 95)
    
    Returns:
        thresholds: Array of adaptive thresholds (one per score)
    """
    if len(scores) == 0:
        return np.array([])
    
    thresholds = np.zeros_like(scores)
    half_window = window_size // 2
    
    for i in range(len(scores)):
        # Define window boundaries
        start_idx = max(0, i - half_window)
        end_idx = min(len(scores), i + half_window + 1)
        
        # Get scores in window
        window_scores = scores[start_idx:end_idx]
        
        if len(window_scores) > 0:
            thresholds[i] = np.percentile(window_scores, percentile)
        else:
            thresholds[i] = scores[i]  # Fallback
    
    return thresholds


def adaptive_threshold_exponential_smoothing(scores, alpha=0.1, percentile=95, window_size=20):
    """
    Adaptive threshold using exponential smoothing of local percentiles.
    Provides smoother threshold adaptation.
    
    Parameters:
        scores: Array of anomaly scores
        alpha: Smoothing factor (0 < alpha <= 1, default: 0.1)
        percentile: Percentile to use within window (default: 95)
        window_size: Window size for percentile calculation
    
    Returns:
        thresholds: Array of adaptive thresholds
    """
    if len(scores) == 0:
        return np.array([])
    
    thresholds = np.zeros_like(scores)
    half_window = window_size // 2
    
    # Initialize with first window
    first_window = scores[:min(window_size, len(scores))]
    if len(first_window) > 0:
        smoothed_threshold = np.percentile(first_window, percentile)
    else:
        smoothed_threshold = scores[0] if len(scores) > 0 else 0.0
    
    for i in range(len(scores)):
        # Calculate local percentile
        start_idx = max(0, i - half_window)
        end_idx = min(len(scores), i + half_window + 1)
        window_scores = scores[start_idx:end_idx]
        
        if len(window_scores) > 0:
            local_percentile = np.percentile(window_scores, percentile)
            # Exponential smoothing
            smoothed_threshold = alpha * local_percentile + (1 - alpha) * smoothed_threshold
            thresholds[i] = smoothed_threshold
        else:
            thresholds[i] = smoothed_threshold
    
    return thresholds


def adaptive_threshold_cusum(scores, baseline_window=50, drift_threshold=2.0):
    """
    Adaptive threshold using CUSUM (Cumulative Sum) for change detection.
    Threshold adapts when baseline shifts are detected.
    
    Parameters:
        scores: Array of anomaly scores
        baseline_window: Window size for baseline estimation
        drift_threshold: Threshold for detecting baseline drift (in std units)
    
    Returns:
        thresholds: Array of adaptive thresholds
    """
    if len(scores) == 0:
        return np.array([])
    
    thresholds = np.zeros_like(scores)
    baseline = np.mean(scores[:min(baseline_window, len(scores))])
    baseline_std = np.std(scores[:min(baseline_window, len(scores))])
    
    if baseline_std < 1e-6:
        baseline_std = baseline * 0.01 if baseline > 0 else 1e-6
    
    # Use mean + 2*std as initial threshold
    current_threshold = baseline + 2.0 * baseline_std
    
    for i in range(len(scores)):
        # Update baseline if significant drift detected
        if i >= baseline_window:
            recent_window = scores[max(0, i - baseline_window):i]
            recent_mean = np.mean(recent_window)
            recent_std = np.std(recent_window)
            
            # Check for drift
            drift = abs(recent_mean - baseline) / (baseline_std + 1e-6)
            if drift > drift_threshold:
                # Update baseline and threshold
                baseline = recent_mean
                baseline_std = recent_std
                if baseline_std < 1e-6:
                    baseline_std = baseline * 0.01 if baseline > 0 else 1e-6
                current_threshold = baseline + 2.0 * baseline_std
        
        thresholds[i] = current_threshold
    
    return thresholds


def calculate_tpr_at_fpr(y_true, y_scores, target_fprs=[0.01, 0.05, 0.1, 0.2, 0.5]):
    """
    Calculate evaluation metrics (TPR, Precision, Recall, F1) at specific FPR targets.
    
    Parameters:
        y_true: Ground truth labels (0=benign, 1=attack)
        y_scores: Anomaly scores (higher = more anomalous)
        target_fprs: List of target FPR values (default: [0.01, 0.05, 0.1, 0.2, 0.5])
    
    Returns:
        results: Dict mapping FPR -> metrics dict (tpr, fpr, precision, recall, f1, threshold, etc.)
    """
    if len(np.unique(y_true)) < 2:
        return {
            fpr: {
                'tpr': 0.0,
                'fpr': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0,
                'threshold': 0.0,
                'target_fpr': float(fpr),
                'tpr_from_curve': 0.0,
                'fpr_from_curve': 0.0
            } for fpr in target_fprs
        }
    
    fpr_curve, tpr_curve, thresholds = roc_curve(y_true, y_scores)
    
    # Replace inf thresholds with largest finite threshold
    finite_thresholds = thresholds[np.isfinite(thresholds)]
    max_finite_threshold = finite_thresholds[-1] if len(finite_thresholds) > 0 else thresholds[-1]
    
    results = {}
    for target_fpr in target_fprs:
        # Find indices where FPR is <= target; if none, use closest index
        le_indices = np.where(fpr_curve <= target_fpr)[0]
        if len(le_indices) > 0:
            idx = le_indices[-1]
        else:
            idx = np.argmin(np.abs(fpr_curve - target_fpr))
        
        threshold = thresholds[idx] if idx < len(thresholds) else thresholds[-1]
        if np.isinf(threshold) or np.isnan(threshold):
            threshold = max_finite_threshold
        
        metrics = evaluate_threshold(y_true, y_scores, threshold)
        metrics.update({
            'threshold': float(threshold),
            'target_fpr': float(target_fpr),
            'tpr_from_curve': float(tpr_curve[idx]),
            'fpr_from_curve': float(fpr_curve[idx])
        })
        
        results[target_fpr] = metrics
    
    return results


def evaluate_threshold(y_true, y_scores, threshold):
    """
    Evaluate a threshold by computing TPR, FPR, Precision, Recall, F1.
    
    Parameters:
        y_true: Ground truth labels (0=benign, 1=attack)
        y_scores: Anomaly scores
        threshold: Threshold value
    
    Returns:
        metrics: Dictionary with TPR, FPR, Precision, Recall, F1
    """
    y_pred = (y_scores >= threshold).astype(int)
    
    tp = np.sum((y_true == 1) & (y_pred == 1))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fn = np.sum((y_true == 1) & (y_pred == 0))
    
    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tpr
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        'tpr': tpr,
        'fpr': fpr,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'threshold': threshold
    }


def get_benign_scores(result_data, metric, attack_name_filter=None):
    """
    Extract benign anomaly scores from result data.
    
    Parameters:
        result_data: DataFrame with anomaly scores
        metric: Metric name to extract
        attack_name_filter: Optional filter for specific attacks (None = all)
    
    Returns:
        benign_scores: Array of benign scores
    """
    if attack_name_filter is None:
        # Get all benign samples (where attack_name contains 'Benign')
        benign_mask = result_data['attack_name'].str.contains('Benign', case=False, na=False)
    else:
        # Get benign samples for specific attack context
        benign_mask = result_data['attack_name'].str.contains('Benign', case=False, na=False)
        if attack_name_filter:
            # Also consider samples from the same dataset/modality context
            modality = attack_name_filter.split('_')[0] if '_' in attack_name_filter else None
            if modality:
                benign_mask = benign_mask & (result_data['attack_name'].str.startswith(modality))
    
    benign_data = result_data[benign_mask]
    
    if metric not in benign_data.columns:
        return np.array([])
    
    benign_scores = benign_data[metric].values
    # Remove NaN and infinite values
    benign_scores = benign_scores[np.isfinite(benign_scores)]
    
    return benign_scores

