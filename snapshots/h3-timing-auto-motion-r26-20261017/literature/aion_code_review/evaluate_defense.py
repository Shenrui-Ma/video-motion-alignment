from pathlib import Path
import hydra
from omegaconf import DictConfig
import numpy as np
import h5py
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import cdist

import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc
import json

from eval_util import *


@hydra.main(config_path="config", config_name="config.yaml")
def attack_evaluate(cfg: DictConfig) -> None:
    
    root_dir = "/home/user/workspace/AION/"
    # Save everything under results/evaluation/ to match sweep evaluation structure
    results_base_dir = Path(f"{root_dir}/results/evaluation/{cfg.dataset}/{cfg.metric}")
    
    # Create subdirectories for different plot types
    similarity_dir = results_base_dir / "similarity"
    lineplot_dir = results_base_dir / "lineplots"
    roc_dir = results_base_dir / "roc_curves"
    event_roc_dir = results_base_dir / "event_roc_curves"
    threshold_data_dir = results_base_dir / "threshold_data"
    event_data_dir = results_base_dir / "event_data"
    analysis_dir = results_base_dir / "analysis"
    
    # Create all directories
    for dir_path in [similarity_dir, lineplot_dir, roc_dir, event_roc_dir, threshold_data_dir, event_data_dir, analysis_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Results will be saved to: {results_base_dir}")
    
    # Auto-select feature file based on dataset if not explicitly specified
    if cfg.feature_file_name is None or cfg.feature_file_name == "null":
        # Get default feature files from config
        dataset_feature_map = cfg.dataset_feature_map
        dataset_key = cfg.dataset.lower()
        if dataset_key in dataset_feature_map:
            feature_file_name = dataset_feature_map[dataset_key]
            print(f"Auto-selected feature file for {cfg.dataset}: {feature_file_name}")
        else:
            raise ValueError(f"Unknown dataset: {cfg.dataset}. Supported datasets: {list(dataset_feature_map.keys())}. "
                           f"Please add it to 'dataset_feature_map' in config.yaml")
    else:
        feature_file_name = cfg.feature_file_name
    
    save_path = f"{root_dir}/data/{cfg.dataset}/features/{feature_file_name}.h5"

    #==================== Load features ===================

    with h5py.File(save_path, "r") as hf:
        # List all datasets (frame_ids)
        frame_ids = list(hf.keys())
        frame_ids.sort()  # Optional: sort the frame_ids

        # For feature visualization
        image_features = []
        lidar_features = []
        actual_timestamps = []  # Store actual timestamps from frame_ids

        # Load data for the first 1000 frames (or any subset you want)
        for frame_id in frame_ids[:]:  # Limit to 1000 or change as needed
            image_data = hf[frame_id + '/image'][:]
            lidar_data = hf[frame_id + '/lidar'][:]
            
            image_features.append(image_data)
            lidar_features.append(lidar_data)
            
            # Extract timestamp from frame_id
            # For nuScenes: frame_id format is like "n015-2018-11-21-19-21-35+0800__LIDAR_TOP__1542799750947219.pcd"
            # The timestamp is the last numeric part before .pcd (in microseconds)
            # For other datasets: might be numeric string or other format
            timestamp = None
            try:
                if isinstance(frame_id, str):
                    # Check if it's a nuScenes format (contains __ and ends with .pcd or similar)
                    if '__' in frame_id:
                        # Extract the numeric part after the last __
                        # Format: "prefix__suffix__TIMESTAMP.pcd"
                        parts = frame_id.split('__')
                        if len(parts) >= 2:
                            # Get the last part and extract numeric timestamp
                            last_part = parts[-1]
                            # Remove file extension if present (.pcd, .jpg, etc.)
                            numeric_part = last_part.split('.')[0]
                            if numeric_part.isdigit():
                                # nuScenes timestamps are in microseconds
                                timestamp = int(numeric_part)
                    # Check if entire frame_id is numeric
                    elif frame_id.isdigit():
                        timestamp = int(frame_id)
                    # Check if it's a simple numeric string without separators
                    elif frame_id.replace('.', '').replace('-', '').isdigit():
                        timestamp = int(float(frame_id))
                    else:
                        # For non-numeric strings, use index as fallback
                        timestamp = len(actual_timestamps)
                else:
                    # If frame_id is already numeric
                    timestamp = int(frame_id)
            except (ValueError, AttributeError, IndexError):
                # If conversion fails, use index as fallback
                timestamp = len(actual_timestamps)
            
            actual_timestamps.append(timestamp)
        # Convert to numpy arrays for easier manipulation
        image_features = np.array(image_features)
        lidar_features = np.array(lidar_features)
        actual_timestamps = np.array(actual_timestamps, dtype=np.int64)

    df_cam_ben = pd.DataFrame(image_features)
    df_lid_ben = pd.DataFrame(lidar_features)


    #======== Attacking the Sensor============
    attack_list = cfg.attack_type_list
    attack_mod_list = cfg.attack_mod_list

    # Attack - get default parameters
    default_interval = cfg.attack.interval
    default_duration = cfg.attack.duration
    default_history = getattr(cfg.attack, 'history', default_duration)  # Use duration as default if history not specified
    
    # Helper function to get attack-specific parameter or use default
    def get_attack_param(attack_name, param_name, default_value):
        """Get attack-specific parameter from config, or return default"""
        attack_key = attack_name.lower()
        if hasattr(cfg.attack, attack_key):
            attack_config = getattr(cfg.attack, attack_key)
            if hasattr(attack_config, param_name):
                return getattr(attack_config, param_name)
        return default_value

    # Defense
    window = cfg.defense.window
    exp_base = cfg.defense.exp_base
    scale_base = cfg.defense.scale_base
    sampling_type = cfg.defense.sampling_type

    ext = f'{window}_{exp_base}_{sampling_type}'

    attack_feature_dict = {}

    for attack in attack_list:
        for modality in attack_mod_list:
            print(f"Attack: {attack}, Modality: {modality}")

            df_cam_att = df_cam_ben.copy()
            df_lid_att = df_lid_ben.copy()
            gt_cam_att = np.zeros(df_cam_ben.shape[0])
            gt_lid_att = np.zeros(df_lid_ben.shape[0])

            # Get attack-specific parameters or use defaults
            # Initialize all parameters
            jitter_mu = None
            jitter_delta = None
            drift_rate = None
            burst_size = None
            burst_gap = None
            scheduler_type = None
            quantum = None
            max_delay = None
            
            if attack == 'Constant':
                attack_t = get_attack_param('constant', 'interval', default_interval)
                attack_n = get_attack_param('constant', 'duration', default_duration)
                attack_m = default_history
            elif attack == 'Random':
                attack_t = get_attack_param('random', 'interval', default_interval)
                attack_n = get_attack_param('random', 'duration', default_duration)
                attack_m = get_attack_param('random', 'history', default_history)
            elif attack == 'Reversal':
                attack_t = get_attack_param('reversal', 'interval', default_interval)
                attack_n = get_attack_param('reversal', 'duration', default_duration)
                attack_m = default_history
            elif attack == 'Jitter':
                # For jitter: t=interval (period), n=duration (attack window size)
                # mu and delta are separate jitter parameters
                attack_t = get_attack_param('jitter', 'interval', default_interval)
                attack_n = get_attack_param('jitter', 'duration', default_duration)
                attack_m = default_history
                jitter_mu = get_attack_param('jitter', 'mu', 1)  # Default mu=1
                jitter_delta = get_attack_param('jitter', 'delta', 2)  # Default delta=2
            elif attack == 'Drift':
                # For drift: t=interval (period), n=duration (attack window size)
                attack_t = get_attack_param('drift', 'interval', default_interval)
                attack_n = get_attack_param('drift', 'duration', default_duration)
                attack_m = default_history
                # Get drift_rate from config, or compute from interval if not specified
                drift_rate = get_attack_param('drift', 'drift_rate', None)
                if drift_rate is None:
                    # Fallback: compute from interval (legacy behavior)
                    drift_rate = 1.0 / attack_t if attack_t > 0 else 0.1
            elif attack == 'Burst':
                # For burst: t=interval (period), n=duration (attack window size)
                attack_t = get_attack_param('burst', 'interval', default_interval)
                attack_n = get_attack_param('burst', 'duration', default_duration)
                attack_m = default_history
                burst_size = get_attack_param('burst', 'burst_size', 3)  # Default: 3 frames per burst
                burst_gap = get_attack_param('burst', 'burst_gap', 2)  # Default: 2 frames between bursts
            elif attack == 'Scheduler':
                # For scheduler: t=interval (period), n=duration (attack window size)
                attack_t = get_attack_param('scheduler', 'interval', default_interval)
                attack_n = get_attack_param('scheduler', 'duration', default_duration)
                attack_m = default_history
                scheduler_type = get_attack_param('scheduler', 'scheduler_type', 'round_robin')  # Default: round_robin
                quantum = get_attack_param('scheduler', 'quantum', 3)  # Default: 3 frames per quantum
                max_delay = get_attack_param('scheduler', 'max_delay', 5)  # Default: max delay of 5
            else:  # Benign or unknown
                attack_t = default_interval
                attack_n = default_duration
                attack_m = default_history

            # Initialize timestamp arrays with actual timestamps from HDF5 file
            # Use actual timestamps if available, otherwise fall back to indices
            if len(actual_timestamps) == len(df_cam_att):
                cam_timestamps = actual_timestamps.copy()
                lidar_timestamps = actual_timestamps.copy()
            else:
                # Fallback: use indices if lengths don't match
                cam_timestamps = np.arange(len(df_cam_att), dtype=int)
                lidar_timestamps = np.arange(len(df_lid_att), dtype=int)
            
            # Initialize attack parameters for both modalities (default: same values)
            attack_t_cam = attack_t_lid = attack_t
            attack_n_cam = attack_n_lid = attack_n
            attack_m_cam = attack_m_lid = attack_m
            jitter_mu_cam = jitter_mu_lid = jitter_mu
            jitter_delta_cam = jitter_delta_lid = jitter_delta
            drift_rate_cam = drift_rate_lid = drift_rate
            burst_size_cam = burst_size_lid = burst_size
            burst_gap_cam = burst_gap_lid = burst_gap
            quantum_cam = quantum_lid = quantum
            max_delay_cam = max_delay_lid = max_delay
            phase_offset_cam = phase_offset_lid = 0  # Phase offset for timing differences
            
            # Add randomization for attacks (except Constant and Reversal) when both modalities are attacked
            if modality == 'Both' and attack not in ['Constant', 'Reversal']:
                # Generate phase offsets to make attacks start at different times
                # Phase offset can be up to 40% of the interval to create more distinct timing differences
                np.random.seed(44)  # Seed for phase offset generation
                max_phase_offset = max(1, int(attack_t * 0.40))  # Up to 40% of interval
                phase_offset_cam = np.random.randint(0, max_phase_offset + 1)
                phase_offset_lid = np.random.randint(0, max_phase_offset + 1)
                # Ensure they are sufficiently different (at least 10% of interval apart)
                min_separation = max(1, int(attack_t * 0.10))
                if abs(phase_offset_cam - phase_offset_lid) < min_separation:
                    # Make them more distinct: one early, one late with good separation
                    phase_offset_cam = max(0, int(attack_t * 0.05))   # 5% offset for Camera (early)
                    phase_offset_lid = max(0, int(attack_t * 0.30))   # 30% offset for LiDAR (late)
                # Set random seed for reproducibility but different for each modality
                np.random.seed(42)  # Base seed for Camera
                if attack == 'Random':
                    # Add ±20% random variation to interval, duration, and history for Camera (more distinct)
                    attack_t_cam = max(1, int(attack_t * (1.0 + np.random.uniform(-0.20, 0.20))))
                    attack_n_cam = max(1, int(attack_n * (1.0 + np.random.uniform(-0.20, 0.20))))
                    attack_m_cam = max(1, int(attack_m * (1.0 + np.random.uniform(-0.20, 0.20))))
                    # Different variation for LiDAR
                    np.random.seed(43)  # Different seed for LiDAR
                    attack_t_lid = max(1, int(attack_t * (1.0 + np.random.uniform(-0.20, 0.20))))
                    attack_n_lid = max(1, int(attack_n * (1.0 + np.random.uniform(-0.20, 0.20))))
                    attack_m_lid = max(1, int(attack_m * (1.0 + np.random.uniform(-0.20, 0.20))))
                    # Ensure they are different (if too close, adjust)
                    if abs(attack_t_cam - attack_t_lid) < max(1, int(attack_t * 0.1)):
                        attack_t_cam = max(1, int(attack_t * 1.15))  # +15% for Camera
                        attack_t_lid = max(1, int(attack_t * 0.85))  # -15% for LiDAR
                    if abs(attack_n_cam - attack_n_lid) < max(1, int(attack_n * 0.1)):
                        attack_n_cam = max(1, int(attack_n * 1.15))
                        attack_n_lid = max(1, int(attack_n * 0.85))
                    if abs(attack_m_cam - attack_m_lid) < max(1, int(attack_m * 0.1)):
                        attack_m_cam = max(1, int(attack_m * 1.15))
                        attack_m_lid = max(1, int(attack_m * 0.85))
                elif attack == 'Jitter':
                    # Add ±30% random variation to jitter_mu and jitter_delta for Camera (more distinct)
                    np.random.seed(42)
                    jitter_mu_cam = max(0, jitter_mu * (1.0 + np.random.uniform(-0.30, 0.30)))
                    jitter_delta_cam = max(1, jitter_delta * (1.0 + np.random.uniform(-0.30, 0.30)))
                    # Different variation for LiDAR
                    np.random.seed(43)
                    jitter_mu_lid = max(0, jitter_mu * (1.0 + np.random.uniform(-0.30, 0.30)))
                    jitter_delta_lid = max(1, jitter_delta * (1.0 + np.random.uniform(-0.30, 0.30)))
                    # Ensure they are different (if too close, adjust)
                    if abs(jitter_mu_cam - jitter_mu_lid) < 0.2:
                        jitter_mu_cam = max(0, jitter_mu * 1.25)  # +25% for Camera
                        jitter_mu_lid = max(0, jitter_mu * 0.75)  # -25% for LiDAR
                    if abs(jitter_delta_cam - jitter_delta_lid) < 0.5:
                        jitter_delta_cam = max(1, int(jitter_delta * 1.25))
                        jitter_delta_lid = max(1, int(jitter_delta * 0.75))
                elif attack == 'Drift':
                    # Add ±30% random variation to drift_rate for Camera (more distinct)
                    drift_rate_cam = drift_rate * (1.0 + np.random.uniform(-0.30, 0.30))
                    np.random.seed(43)  # Different seed for LiDAR
                    drift_rate_lid = drift_rate * (1.0 + np.random.uniform(-0.30, 0.30))
                    # Ensure they are different (if too close, adjust)
                    if abs(drift_rate_cam - drift_rate_lid) < 0.05 * drift_rate:
                        drift_rate_cam = drift_rate * 1.25  # +25% for Camera
                        drift_rate_lid = drift_rate * 0.75   # -25% for LiDAR
                elif attack == 'Burst':
                    # Add ±2 frame random variation to burst_size and burst_gap for Camera (more distinct)
                    np.random.seed(42)
                    burst_size_cam = max(1, int(burst_size + np.random.randint(-2, 3)))
                    burst_gap_cam = max(1, int(burst_gap + np.random.randint(-2, 3)))
                    # Different variation for LiDAR
                    np.random.seed(43)
                    burst_size_lid = max(1, int(burst_size + np.random.randint(-2, 3)))
                    burst_gap_lid = max(1, int(burst_gap + np.random.randint(-2, 3)))
                    # Ensure they are different (if too close, adjust)
                    if burst_size_cam == burst_size_lid:
                        burst_size_cam = max(1, burst_size + 2)
                        burst_size_lid = max(1, burst_size - 1)
                    if burst_gap_cam == burst_gap_lid:
                        burst_gap_cam = max(1, burst_gap + 1)
                        burst_gap_lid = max(1, burst_gap - 1)
                elif attack == 'Scheduler':
                    # Add ±2 random variation to quantum and max_delay for Camera (more distinct)
                    np.random.seed(42)
                    quantum_cam = max(1, int(quantum + np.random.randint(-2, 3)))
                    max_delay_cam = max(1, int(max_delay + np.random.randint(-2, 3)))
                    # Different variation for LiDAR
                    np.random.seed(43)
                    quantum_lid = max(1, int(quantum + np.random.randint(-2, 3)))
                    max_delay_lid = max(1, int(max_delay + np.random.randint(-2, 3)))
                    # Ensure they are different (if too close, adjust)
                    if quantum_cam == quantum_lid:
                        quantum_cam = max(1, quantum + 2)
                        quantum_lid = max(1, quantum - 1)
                    if max_delay_cam == max_delay_lid:
                        max_delay_cam = max(1, max_delay + 2)
                        max_delay_lid = max(1, max_delay - 1)
            
            if modality in ['Camera', 'Both']:
                df_cam_att, gt_cam_att, cam_timestamps = unimodal_attack(df_cam_att, attack_type = attack, 
                                                         t=attack_t_cam, n=attack_n_cam, m=attack_m_cam, 
                                                         jitter_mu=jitter_mu_cam, jitter_delta=jitter_delta_cam, 
                                                         drift_rate=drift_rate_cam if attack == 'Drift' else None,
                                                         burst_size=burst_size_cam if attack == 'Burst' else None,
                                                         burst_gap=burst_gap_cam if attack == 'Burst' else None,
                                                         scheduler_type=scheduler_type if attack == 'Scheduler' else None,
                                                         quantum=quantum_cam if attack == 'Scheduler' else None,
                                                         max_delay=max_delay_cam if attack == 'Scheduler' else None,
                                                         phase_offset=phase_offset_cam)
            if modality in ['Lidar', 'Both']:
                df_lid_att, gt_lid_att, lidar_timestamps = unimodal_attack(df_lid_att, attack_type = attack,  
                                                         t=attack_t_lid, n=attack_n_lid, m=attack_m_lid, 
                                                         jitter_mu=jitter_mu_lid, jitter_delta=jitter_delta_lid, 
                                                         drift_rate=drift_rate_lid if attack == 'Drift' else None,
                                                         burst_size=burst_size_lid if attack == 'Burst' else None,
                                                         burst_gap=burst_gap_lid if attack == 'Burst' else None,
                                                         scheduler_type=scheduler_type if attack == 'Scheduler' else None,
                                                         quantum=quantum_lid if attack == 'Scheduler' else None,
                                                         max_delay=max_delay_lid if attack == 'Scheduler' else None,
                                                         phase_offset=phase_offset_lid)

            if cfg.metric == 'cos':
                cosine_distance = cosine_similarity(df_cam_att, df_lid_att)
            elif cfg.metric == 'l1':
                cosine_distance = - cdist(df_cam_att, df_lid_att, metric='cityblock')  # L1 norm
            elif cfg.metric == 'l2':
                cosine_distance = - cdist(df_cam_att, df_lid_att, metric='euclidean')  # L2 norm



            gt_comb_att = np.where((gt_cam_att == 0) & (gt_lid_att == 0), 0, 1)
            # Store distance matrix, ground truth, feature DataFrames, and manipulated timestamps for improved baselines
            attack_feature_dict[f"{modality}_{attack}"] = (
                cosine_distance, 
                gt_comb_att,
                df_cam_att,  # Store attacked camera features
                df_lid_att,  # Store attacked LiDAR features
                cam_timestamps,  # Store manipulated camera timestamps
                lidar_timestamps  # Store manipulated LiDAR timestamps
            )

            # Visualize the distance matrix
            plt.figure(figsize=(3.5, 2.75))
            sns.heatmap(
                cosine_distance[40:70,40:70], 
                vmin=0, vmax=1, cmap='coolwarm'
            )
            plt.xlabel("Camera Time Step")
            plt.ylabel("LiDAR Time Step")
            if attack == 'Benign'   :
                plt.title(f"Benign Condition (No Delays)")
            else:
                plt.title(f"{attack} Delay on {modality}")

            # Set custom ticks
            ticks = [0, 5, 10, 15, 20, 25, 30]
            plt.xticks(ticks, labels=[str(0 + t) for t in ticks])
            plt.yticks(ticks, labels=[str(0 + t) for t in ticks])

            plt.tight_layout()

            # Save both .jpg and .pdf in similarity directory
            file_dir_jpg = similarity_dir / f"Cosine_sim_{modality}_{attack}.jpg"
            file_dir_pdf = similarity_dir / f"Cosine_sim_{modality}_{attack}.pdf"
            plt.savefig(file_dir_jpg, dpi=300)
            plt.savefig(file_dir_pdf, dpi=300)

            plt.show()


    # =============================================== Evaluation ===============================================
    result_data = []
    optimal_path = [(i,i) for i in range(window)]  # Normal sequence warping path  
    
    # First pass: Collect benign snapshots for training anomaly detectors
    benign_snapshots = []
    for attack_name, attack_data in attack_feature_dict.items():
        # Only collect from benign attacks
        if 'Benign' in attack_name:
            cosine_distance, gt_comb_att, df_cam_att, df_lid_att, cam_timestamps, lidar_timestamps = attack_data
            for index in range(window*scale_base, cosine_distance.shape[0]):
                distance_ss, label_ss = get_distance_snapshot(cosine_distance, gt_comb_att, index=index, window=window, scale_base=scale_base, sampling_type=sampling_type, normalize=True)
                benign_snapshots.append(distance_ss)
    
    # Initialize anomaly detectors (One-Class SVM and Isolation Forest)
    one_class_svm_detector_instance = None
    isolation_forest_detector_instance = None
    
    # Train detectors if we have benign snapshots
    if len(benign_snapshots) > 0 and 'one_class_svm' in cfg.eval_metric or 'isolation_forest' in cfg.eval_metric:
        print(f"Training anomaly detectors on {len(benign_snapshots)} benign snapshots...")
        # Train One-Class SVM
        _, one_class_svm_detector_instance = one_class_svm_detector(
            test_snapshot=benign_snapshots[0],  # Dummy, will be replaced
            benign_snapshots=benign_snapshots,
            detector=None
        )
        # Train Isolation Forest
        _, isolation_forest_detector_instance = isolation_forest_detector(
            test_snapshot=benign_snapshots[0],  # Dummy, will be replaced
            benign_snapshots=benign_snapshots,
            detector=None
        )
        print("Anomaly detectors trained successfully.")
    else:
        print("Warning: No benign snapshots found. Anomaly detectors will not be trained.")
    
    # Second pass: Evaluate all attacks (including benign)
    for attack_name, attack_data in attack_feature_dict.items():
        cosine_distance, gt_comb_att, df_cam_att, df_lid_att, cam_timestamps, lidar_timestamps = attack_data
        
        for index in range(window*scale_base, cosine_distance.shape[0]):
            distance_ss, label_ss = get_distance_snapshot(cosine_distance, gt_comb_att, index=index, window=window, scale_base=scale_base, sampling_type=sampling_type, normalize=True)
            # Get global max/min of the entire DataFrame (not per-column)
            if isinstance(distance_ss, pd.DataFrame):
                global_max = distance_ss.values.max()
                global_min = distance_ss.values.min()
            else:
                global_max = np.max(distance_ss)
                global_min = np.min(distance_ss)
            # print(f"distance_ss global range: [{global_min:.6f}, {global_max:.6f}]")
            # Get feature indices for the snapshot (same indices used in get_distance_snapshot)
            if sampling_type == 'uni':
                feature_indices = [index - indx for indx in range(window)][::-1]
            elif sampling_type == 'fac':
                feature_indices = [index - indx for indx in range(0, window*scale_base, scale_base)][::-1]
            elif sampling_type == 'exp':
                feature_indices = [index-exp_base**indx for indx in range(window-1)][::-1] + [index]
            else:
                feature_indices = list(range(max(0, index-window+1), index+1))
            
            # Ensure indices are valid
            feature_indices = [idx for idx in feature_indices if 0 <= idx < len(df_cam_att)]
            
            # Extract feature windows
            if len(feature_indices) > 0:
                cam_features_window = df_cam_att.iloc[feature_indices]
                lidar_features_window = df_lid_att.iloc[feature_indices]
            else:
                # Fallback: use last window frames
                start_idx = max(0, index - window + 1)
                cam_features_window = df_cam_att.iloc[start_idx:index+1]
                lidar_features_window = df_lid_att.iloc[start_idx:index+1]
            
            # DTW-based metrics
            dtw_cost, dtw_matrix, dtw_path = dtw(distance_ss)
            dtw_area = compute_and_plot_dtw_area(dtw_path, optimal_path, n=window, m=window, area_only=True)
            
            # Improved baseline detection methods (Phase 1)
            # 1. Direct feature correlation (more aligned with reviewer's suggestion)
            correlation_score_improved = direct_feature_correlation(
                cam_features_window, lidar_features_window, window=window
            )
            
            # 2. Improved CUSUM on features (traditional CUSUM approach)
            cusum_score_improved = improved_cusum_features(
                cam_features_window, lidar_features_window, window=window
            )
            
            # 3. Timestamp sanity check (statistical timestamp model)
            # Use manipulated timestamps from the attack
            if len(feature_indices) > 0:
                # Extract manipulated timestamps for the feature window
                cam_timestamps_window = cam_timestamps[feature_indices]
                lidar_timestamps_window = lidar_timestamps[feature_indices]
                
                # Compute timestamp sanity for both modalities and combine
                cam_timestamp_score = timestamp_sanity_detector(cam_timestamps_window, window=window, jitter_model='gaussian')
                lidar_timestamp_score = timestamp_sanity_detector(lidar_timestamps_window, window=window, jitter_model='gaussian')
                
                # Combine scores (use maximum or average - maximum is more conservative)
                timestamp_score = max(cam_timestamp_score, lidar_timestamp_score)
            else:
                # Fallback: use frame indices
                timestamps = np.arange(len(cam_features_window))
                timestamp_score = timestamp_sanity_detector(timestamps, window=window, jitter_model='gaussian')
            
            # 4. Feature flow detector (temporal differences in feature representations)
            feature_flow_score = feature_flow_detector(
                cam_features_window, lidar_features_window, window=window
            )
            
            # 5. Diagonal distance detector (superdiagonal and subdiagonal elements)
            diagonal_score = diagonal_distance_detector(distance_ss, window=window)
            
            # 6. Enhanced detection for individual modality attacks
            # Check if this is an individual modality attack (Camera or Lidar only)
            enhanced_score = 0.0
            if 'Camera_' in attack_name and 'Lidar_' not in attack_name:
                # Camera-only attack: use enhanced detection
                from eval_util.individual_modality_detection import compute_enhanced_detection_score
                if len(feature_indices) > 0:
                    cam_timestamps_window = cam_timestamps[feature_indices]
                    lidar_timestamps_window = lidar_timestamps[feature_indices]
                else:
                    cam_timestamps_window = np.arange(len(cam_features_window))
                    lidar_timestamps_window = np.arange(len(lidar_features_window))
                enhanced_score = compute_enhanced_detection_score(
                    cam_features_window, lidar_features_window,
                    cam_timestamps_window, lidar_timestamps_window,
                    attacked_modality='Camera', window=window
                )
            elif 'Lidar_' in attack_name and 'Camera_' not in attack_name:
                # Lidar-only attack: use enhanced detection
                from eval_util.individual_modality_detection import compute_enhanced_detection_score
                if len(feature_indices) > 0:
                    cam_timestamps_window = cam_timestamps[feature_indices]
                    lidar_timestamps_window = lidar_timestamps[feature_indices]
                else:
                    cam_timestamps_window = np.arange(len(cam_features_window))
                    lidar_timestamps_window = np.arange(len(lidar_features_window))
                enhanced_score = compute_enhanced_detection_score(
                    cam_features_window, lidar_features_window,
                    cam_timestamps_window, lidar_timestamps_window,
                    attacked_modality='Lidar', window=window
                )
            
            # Legacy baselines (for comparison/backward compatibility)
            correlation_score_legacy = compute_sliding_window_correlation(distance_ss)
            cusum_score_legacy = compute_cusum(distance_ss)
            
            # Anomaly detection baselines (One-Class SVM and Isolation Forest)
            one_class_svm_score = 0.0
            isolation_forest_score = 0.0
            if one_class_svm_detector_instance is not None:
                one_class_svm_score, _ = one_class_svm_detector(
                    test_snapshot=distance_ss,
                    detector=one_class_svm_detector_instance
                )
            if isolation_forest_detector_instance is not None:
                isolation_forest_score, _ = isolation_forest_detector(
                    test_snapshot=distance_ss,
                    detector=isolation_forest_detector_instance
                )
            
            total_gt = np.sum(label_ss)
            result_data.append({
                "attack_name": attack_name, 
                "index": index, 
                'dtw_cost': dtw_cost, 
                'dtw_area': dtw_area,
                'correlation': correlation_score_improved,  # Use improved version
                'correlation_legacy': correlation_score_legacy,  # Keep for comparison
                'cusum': cusum_score_improved,  # Use improved version
                'cusum_legacy': cusum_score_legacy,  # Keep for comparison
                'timestamp_sanity': timestamp_score,  # New baseline
                'feature_flow': feature_flow_score,  # Feature flow detector
                'diagonal_distance': diagonal_score,  # Diagonal distance detector
                'enhanced_individual': enhanced_score,  # Enhanced detection for individual modality attacks
                'one_class_svm': one_class_svm_score,  # One-Class SVM baseline
                'isolation_forest': isolation_forest_score,  # Isolation Forest baseline
                'total_gt': total_gt
            })
    result_data = pd.DataFrame(result_data)


    # Use 'dtw_area' as the predicted scores and 'total_gt' as ground truth
    for attack_name in result_data["attack_name"].unique():
        filter_attack = result_data['attack_name'] == attack_name
        result_data_att = result_data.where(filter_attack).dropna()

        for metric in cfg.eval_metric:
            plt.figure(figsize=(10,5))
            sns.lineplot(result_data_att[0:100], x = 'index', y = metric)
            sns.lineplot(result_data_att[0:100], x = 'index', y = 'total_gt')
            file_dir = lineplot_dir / f"xlineplot_{attack_name}_{metric}"
            plt.savefig(str(file_dir)+'.jpg', dpi=300)
            plt.savefig(str(file_dir)+'.pdf', dpi=300)
            plt.show()


        for metric in cfg.eval_metric:
            y_true = (result_data_att['total_gt'].values>window/2).astype(int)
            if metric == 'both':
                # y_scores = result_data_att[['dtw_area', 'dtw_cost']].sum().values
                y_scores = result_data_att[['dtw_area', 'dtw_cost']].sum(axis=1).values
            elif metric == 'all_baselines':
                # Combine all baseline methods (improved versions)
                baseline_cols = ['correlation', 'cusum', 'timestamp_sanity']
                available_cols = [col for col in baseline_cols if col in result_data_att.columns]
                if len(available_cols) > 0:
                    y_scores = result_data_att[available_cols].sum(axis=1).values
                else:
                    # Fallback to legacy if improved not available
                    y_scores = result_data_att[['dtw_cost', 'dtw_area', 'correlation', 'cusum']].sum(axis=1).values
            else:
                y_scores = result_data_att[metric].values

            # Check if both classes are present (required for ROC curve)
            unique_classes = np.unique(y_true)
            if len(unique_classes) < 2:
                print(f"WARNING: attack_name={attack_name}, Metric={metric} has only one class (classes: {unique_classes}). "
                      f"total_gt distribution: min={result_data_att['total_gt'].min():.2f}, "
                      f"max={result_data_att['total_gt'].max():.2f}, "
                      f"mean={result_data_att['total_gt'].mean():.2f}. "
                      f"Skipping ROC calculation.")
                continue

            # Calculate ROC curve and AUROC
            fpr, tpr, thresholds = roc_curve(y_true, y_scores)
            roc_auc = auc(fpr, tpr)

            # Plotting the ROC curve
            plt.figure(figsize=(10, 6))
            plt.plot(fpr, tpr, color='blue', label=f'ROC Curve (AUROC = {roc_auc:.2f})')
            plt.plot([0, 1], [0, 1], color='gray', linestyle='--')  # Diagonal line
            plt.xlabel('False Positive Rate')
            plt.ylabel('True Positive Rate')
            plt.title('ROC Curve')
            plt.legend(loc='lower right')
            plt.grid(True)
            file_dir = roc_dir / f"roc_{metric}_{attack_name}_{ext}.jpg"
            plt.savefig(file_dir, dpi=300)
            plt.savefig(str(file_dir).replace('.jpg', '.pdf'), dpi=300)
            plt.show()

            # Print AUROC score
            print(f"attack_name : {attack_name}, Metric: {metric}, AUROC Score: {roc_auc:.4f}")
            
            # ==================== Thresholding Analysis ====================
            # Extract benign scores for global threshold calculation
            benign_scores = get_benign_scores(result_data, metric, attack_name)
            
            # Calculate metrics at different FPR targets
            target_fprs = [0.01, 0.05, 0.1, 0.2, 0.5]
            metrics_at_fpr = calculate_tpr_at_fpr(y_true, y_scores, target_fprs)
            
            # Print metrics at different FPR values
            print(f"  Metrics at different FPR thresholds:")
            for fpr_val in sorted(metrics_at_fpr.keys()):
                metrics_dict = metrics_at_fpr[fpr_val]
                print(
                    f"    FPR≤{fpr_val:.2f}: "
                    f"TPR={metrics_dict['tpr']:.4f} "
                    f"(actual FPR={metrics_dict['fpr']:.4f}), "
                    f"Precision={metrics_dict['precision']:.4f}, "
                    f"Recall={metrics_dict['recall']:.4f}, "
                    f"F1={metrics_dict['f1']:.4f}, "
                    f"Threshold={metrics_dict['threshold']:.4f}"
                )
            
            # Global thresholding methods
            if len(benign_scores) > 0:
                global_thresholds = {
                    'mean_std_2': global_threshold_mean_std(benign_scores, multiplier=2.0),
                    'mean_std_3': global_threshold_mean_std(benign_scores, multiplier=3.0),
                    'percentile_95': global_threshold_percentile(benign_scores, percentile=95),
                    'percentile_99': global_threshold_percentile(benign_scores, percentile=99),
                    'median_iqr_1.5': global_threshold_median_iqr(benign_scores, multiplier=1.5),
                    'median_iqr_2.0': global_threshold_median_iqr(benign_scores, multiplier=2.0),
                    'max_margin_10': global_threshold_max(benign_scores, safety_margin=0.1),
                }
                
                print(f"  Global thresholds (based on {len(benign_scores)} benign samples):")
                for method, threshold in global_thresholds.items():
                    metrics = evaluate_threshold(y_true, y_scores, threshold)
                    print(f"    {method}: threshold={threshold:.4f}, TPR={metrics['tpr']:.4f}, FPR={metrics['fpr']:.4f}, F1={metrics['f1']:.4f}")
            else:
                print(f"  Warning: No benign samples found for global threshold calculation")
                global_thresholds = {}
            
            # Adaptive thresholding methods
            adaptive_thresholds = {
                'sliding_window_95': adaptive_threshold_sliding_window(y_scores, window_size=50, percentile=95),
                'sliding_window_99': adaptive_threshold_sliding_window(y_scores, window_size=50, percentile=99),
                'exp_smoothing_95': adaptive_threshold_exponential_smoothing(y_scores, alpha=0.1, percentile=95, window_size=20),
                'exp_smoothing_99': adaptive_threshold_exponential_smoothing(y_scores, alpha=0.1, percentile=99, window_size=20),
                'cusum_adaptive': adaptive_threshold_cusum(y_scores, baseline_window=50, drift_threshold=2.0),
            }
            
            # Evaluate adaptive thresholds (use mean threshold for evaluation)
            print(f"  Adaptive thresholds (evaluated using mean threshold):")
            for method, thresholds_array in adaptive_thresholds.items():
                if len(thresholds_array) > 0:
                    mean_threshold = np.mean(thresholds_array)
                    metrics = evaluate_threshold(y_true, y_scores, mean_threshold)
                    print(f"    {method}: mean_threshold={mean_threshold:.4f}, TPR={metrics['tpr']:.4f}, FPR={metrics['fpr']:.4f}, F1={metrics['f1']:.4f}")
            
            # Store thresholding results for later analysis
            threshold_results = {
                'attack_name': attack_name,
                'metric': metric,
                'auroc': roc_auc,
                'metrics_at_fpr': metrics_at_fpr,
                'global_thresholds': global_thresholds,
                'adaptive_thresholds_mean': {k: float(np.mean(v)) if len(v) > 0 else 0.0 
                                             for k, v in adaptive_thresholds.items()}
            }
            
            # Save thresholding results to file
            threshold_results_file = threshold_data_dir / f"threshold_results_{metric}_{attack_name}_{ext}.json"
            # Convert numpy types to Python types for JSON serialization
            threshold_results_json = {
                'attack_name': str(threshold_results['attack_name']),
                'metric': str(threshold_results['metric']),
                'auroc': float(threshold_results['auroc']),
                'metrics_at_fpr': {
                    str(k): {metric_name: float(value) for metric_name, value in v.items()}
                    for k, v in threshold_results['metrics_at_fpr'].items()
                },
                'global_thresholds': {str(k): float(v) for k, v in threshold_results['global_thresholds'].items()},
                'adaptive_thresholds_mean': {str(k): float(v) for k, v in threshold_results['adaptive_thresholds_mean'].items()}
            }
            with open(threshold_results_file, 'w') as f:
                json.dump(threshold_results_json, f, indent=2)
            print(f"  Thresholding results saved to: {threshold_results_file}")
            
            # ==================== Event-Based Detection Evaluation ====================
            # Extract full ground truth for this attack
            attack_data = attack_feature_dict[attack_name]
            gt_comb_att = attack_data[1]  # Full ground truth sequence
            
            # Evaluate event detection
            from eval_util.event_detection import evaluate_event_detection, evaluate_event_detection_at_thresholds
            
            # First, get event TPR vs FPR curve at different thresholds
            # Generate thresholds from score distribution
            attack_mask = result_data['attack_name'] == attack_name
            result_data_att = result_data[attack_mask]
            detection_scores = result_data_att[metric].values
            
            # Generate thresholds (percentiles of scores)
            score_min = np.min(detection_scores)
            score_max = np.max(detection_scores)
            num_thresholds = 100
            thresholds = np.linspace(score_min, score_max, num_thresholds)
            
            # Evaluate at multiple thresholds
            event_roc_results = evaluate_event_detection_at_thresholds(
                result_data=result_data,
                gt_labels=gt_comb_att,
                metric=metric,
                attack_name=attack_name,
                thresholds=thresholds,
                early_detection_window=window,
                min_event_length=1
            )
            
            if 'error' not in event_roc_results:
                # Sort FPR and TPR values (FPR must be monotonically increasing for auc)
                event_fprs = np.array(event_roc_results['event_fprs'])
                event_tprs = np.array(event_roc_results['event_tprs'])
                # Sort by FPR (ascending)
                sort_idx = np.argsort(event_fprs)
                event_fprs_sorted = event_fprs[sort_idx]
                event_tprs_sorted = event_tprs[sort_idx]
                # Handle duplicate FPR values by keeping maximum TPR (standard for ROC curves)
                unique_fprs = []
                unique_tprs = []
                for i, fpr in enumerate(event_fprs_sorted):
                    if i == 0 or fpr != unique_fprs[-1]:
                        unique_fprs.append(fpr)
                        unique_tprs.append(event_tprs_sorted[i])
                    else:
                        # Keep maximum TPR for duplicate FPR (optimistic approach for ROC)
                        unique_tprs[-1] = max(unique_tprs[-1], event_tprs_sorted[i])
                unique_fprs = np.array(unique_fprs)
                unique_tprs = np.array(unique_tprs)
                
                # Plot event-level ROC curve (using sorted values)
                plt.figure(figsize=(8, 6))
                plt.plot(unique_fprs, unique_tprs, 
                        'b-', linewidth=2, label=f'Event ROC (Metric: {metric})')
                plt.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random')
                plt.xlabel('Event False Positive Rate')
                plt.ylabel('Event True Positive Rate (Detection Rate)')
                plt.title(f'Event-Level ROC Curve: {attack_name}')
                plt.legend(loc='lower right')
                plt.grid(True, alpha=0.3)
                plt.xlim([0, 1])
                plt.ylim([0, 1])
                
                # Calculate event-level AUROC
                event_auroc = auc(unique_fprs, unique_tprs)
                plt.text(0.6, 0.2, f'Event AUROC = {event_auroc:.4f}', 
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                
                file_dir = event_roc_dir / f"event_roc_{metric}_{attack_name}_{ext}.jpg"
                plt.savefig(file_dir, dpi=300)
                plt.savefig(str(file_dir).replace('.jpg', '.pdf'), dpi=300)
                plt.close()
                
                print(f"\n  Event-Level ROC Curve:")
                print(f"    Event AUROC: {event_auroc:.4f}")
                print(f"    Evaluated at {len(thresholds)} thresholds")
                
                # Save event ROC data (using sorted values)
                event_roc_json = {
                    'attack_name': str(event_roc_results['attack_name']),
                    'metric': str(event_roc_results['metric']),
                    'event_auroc': float(event_auroc),
                    'num_events': int(event_roc_results['num_events']),
                    'thresholds': [float(t) for t in event_roc_results['thresholds']],
                    'event_tprs': [float(tpr) for tpr in unique_tprs],
                    'event_fprs': [float(fpr) for fpr in unique_fprs]
                }
                
                event_roc_file = event_data_dir / f"event_roc_data_{metric}_{attack_name}_{ext}.json"
                with open(event_roc_file, 'w') as f:
                    json.dump(event_roc_json, f, indent=2)
                print(f"    Event ROC data saved to: {event_roc_file}")
            
            # Now evaluate at optimal threshold (single threshold evaluation)
            event_results = evaluate_event_detection(
                result_data=result_data,
                gt_labels=gt_comb_att,
                metric=metric,
                attack_name=attack_name,
                threshold=None,  # Will use optimal threshold
                early_detection_window=window,  # Allow detection window frames before event
                min_event_length=1
            )
            
            if 'error' not in event_results:
                event_metrics = event_results['metrics']
                print(f"\n  Event-Based Detection Results:")
                print(f"    Total events: {event_metrics['num_total_events']}")
                print(f"    Detected events: {event_metrics['num_detected']}")
                print(f"    Missed events: {event_metrics['num_missed']}")
                print(f"    False positive events: {event_metrics['num_false_positives']}")
                print(f"    Event TPR (Detection Rate): {event_metrics['event_tpr']:.4f}")
                print(f"    Event FPR: {event_metrics['event_fpr']:.4f}")
                print(f"    Avg detection delay: {event_metrics['avg_detection_delay']:.2f} frames")
                print(f"    Median detection delay: {event_metrics['median_detection_delay']:.2f} frames")
                print(f"    Early detections (before event start): {event_metrics['early_detections']}")
                print(f"    Late detections (after event start): {event_metrics['late_detections']}")
                if event_metrics['min_detection_delay'] is not None:
                    print(f"    Min delay: {event_metrics['min_detection_delay']:.2f} frames")
                    print(f"    Max delay: {event_metrics['max_detection_delay']:.2f} frames")
                
                # Store event results
                event_results_json = {
                    'attack_name': str(event_results['attack_name']),
                    'metric': str(event_results['metric']),
                    'threshold': float(event_results['threshold']),
                    'num_events': len(event_results['events']),
                    'metrics': {k: float(v) if isinstance(v, (int, float, np.number)) else v 
                               for k, v in event_metrics.items()},
                    'detected_events': [
                        {
                            'event_id': int(e['event_id']),
                            'start': int(e['start']),
                            'end': int(e['end']),
                            'length': int(e['length']),
                            'first_detection_frame': int(e['first_detection_frame']),
                            'detection_delay': float(e['detection_delay']),
                            'max_detection_score': float(e['max_detection_score']),
                            'num_detections': int(e['num_detections'])
                        }
                        for e in event_results['event_detections']['detected_events']
                    ],
                    'missed_events': [
                        {
                            'event_id': int(e['event_id']),
                            'start': int(e['start']),
                            'end': int(e['end']),
                            'length': int(e['length'])
                        }
                        for e in event_results['event_detections']['missed_events']
                    ],
                    'false_positives': [
                        {
                            'start': int(e['start']),
                            'end': int(e['end']),
                            'length': int(e['length'])
                        }
                        for e in event_results['event_detections']['false_positives']
                    ]
                }
                
                # Save event detection results
                event_results_file = event_data_dir / f"event_detection_{metric}_{attack_name}_{ext}.json"
                with open(event_results_file, 'w') as f:
                    json.dump(event_results_json, f, indent=2)
                print(f"  Event detection results saved to: {event_results_file}")
            else:
                print(f"  Event detection evaluation skipped: {event_results.get('error', 'Unknown error')}")


    #======================= Update ==============================================
    # Use 'dtw_area' as the predicted scores and 'total_gt' as ground truth
    for attack_name in result_data["attack_name"].unique():
        filter_attack = result_data['attack_name'] == attack_name
        result_data_att = result_data.where(filter_attack).dropna()


        vis_length = 90 if len(result_data_att) > 90 else len(result_data_att)-1

        plt.figure(figsize=(2.25, 2.25))
        # Create adjusted index starting from 0
        result_data_plot = result_data_att[40:vis_length].copy()
        result_data_plot['index_adj'] = result_data_plot['index'] - result_data_att.iloc[40]['index']
        
        # Line plot for DTW cost
        sns.lineplot(result_data_plot, x='index_adj', y='dtw_cost') #label='DTW Cost'
        # Shade regions based on gt_label (0 = benign, 1 = malicious)
        for i in range(40,vis_length):
            start = result_data_att.iloc[i]['index'] - result_data_att.iloc[40]['index']
            end = result_data_att.iloc[i + 1]['index'] - result_data_att.iloc[40]['index']
            label = result_data_att.iloc[i]['total_gt']
            color = 'green' if label == 0 else 'red'
            alpha = 0.1 if label == 0 else 0.2  # Make benign slightly lighter

            plt.axvspan(start, end, color=color, alpha=alpha)

        modality_type, attack_type = attack_name.split('_')
        # Save the plot
        plt.title(f'{attack_type} Attack') #on {modality_type}
        plt.xlabel('Time Index')
        plt.ylabel('Anomaly Score')
        # plt.legend()
        plt.tight_layout()
        file_dir = lineplot_dir / f"lineplot_{attack_name}"
        plt.savefig(str(file_dir)+".jpg", dpi=300)
        plt.savefig(str(file_dir)+".pdf", dpi=300)
        plt.close()
        #------------------------------------------------------------

    marker_list = ['o', 's', '^', 'D', 'v', 'x']
    idx = 0
    plt.figure(figsize=(4.5,2.5))
    for attack_name in result_data["attack_name"].unique():
        filter_attack = result_data['attack_name'] == attack_name
        result_data_att = result_data.where(filter_attack).dropna()

        modality_type, attack_type = attack_name.split('_')
        if attack_type == 'Benign':
            continue
        if attack_name == 'Both_Constant':
            continue
        #------------------------------------------------------------
        # Plot ROC curve for each attack
        for metric in ['dtw_cost']: #both', 'dtw_area', 
            y_true = (result_data_att['total_gt'].values>window/2).astype(int)
            if metric == 'both':
                # y_scores = result_data_att[['dtw_area', 'dtw_cost']].sum().values
                y_scores = result_data_att[['dtw_area', 'dtw_cost']].sum(axis=1).values

            else:
                y_scores = result_data_att[metric].values

            # Check if both classes are present (required for ROC curve)
            unique_classes = np.unique(y_true)
            if len(unique_classes) < 2:
                print(f"WARNING: attack_name={attack_name}, Metric={metric} has only one class (classes: {unique_classes}). "
                      f"total_gt distribution: min={result_data_att['total_gt'].min():.2f}, "
                      f"max={result_data_att['total_gt'].max():.2f}, "
                      f"mean={result_data_att['total_gt'].mean():.2f}. "
                      f"Skipping ROC calculation.")
                continue

            # Calculate ROC curve and AUROC
            fpr, tpr, thresholds = roc_curve(y_true, y_scores)
            roc_auc = auc(fpr, tpr)
            # Plotting the ROC curve
            # Format the label string with padding
            # label_prefix = f'{attack_type} Delay on {modality_type}'.ljust(30)
            # plt.plot(fpr, tpr, label=f'{label_prefix}: {roc_auc:.2f}', linewidth=1.5)
            plt.plot(fpr, tpr, label=f'{attack_type} Delay on {modality_type}:{roc_auc:.2f}', linewidth=1.5) # marker= marker_list[idx],
            idx += 1
    plt.plot([0, 1], [0, 1], color='gray', linestyle='--')  # Diagonal line
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    # plt.title('ROC Curve')
    plt.legend(loc='lower right')
    plt.grid(True)
    plt.tight_layout()
    file_dir = roc_dir / f"total_roc_{metric}_{attack_name}_{ext}"
    plt.savefig(str(file_dir)+".jpg", dpi=300)
    plt.savefig(str(file_dir)+".pdf", dpi=300)
    plt.show()
    #=================================================================================

    #======================= Combined ROC Curves by Dataset and Modality ====================
    # Generate individual ROC plots for each modality with smaller figure sizes
    attack_types = [attack for attack in cfg.attack_type_list if attack != 'Benign'] 
    modalities = cfg.attack_mod_list
    
    # Define colors for each attack type
    colors = plt.cm.tab10(np.linspace(0, 1, len(attack_types)))
    attack_color_map = {attack: colors[i] for i, attack in enumerate(attack_types)}
    
    # Current dataset from config
    current_dataset = cfg.dataset.lower()
    
    # Get list of metrics to generate plots for
    metrics_to_plot = cfg.eval_metric if cfg.eval_metric else ['dtw_cost']
    
    # Generate combined ROC plots for each metric
    for metric in metrics_to_plot:
        for modality in modalities:
            plt.figure(figsize=(3.75, 2.85))  # Smaller figure size
            
            for attack_type in attack_types:
                attack_name = f"{modality}_{attack_type}"
                
                # Filter data for this attack
                filter_attack = result_data['attack_name'] == attack_name
                result_data_att = result_data.where(filter_attack).dropna()
                
                if len(result_data_att) == 0:
                    print(f"WARNING: No data found for {attack_name}, skipping...")
                    continue
                
                y_true = (result_data_att['total_gt'].values > window*cfg.window_ratio_threshold).astype(int)
                
                if metric == 'both':
                    y_scores = result_data_att[['dtw_area', 'dtw_cost']].sum(axis=1).values
                elif metric == 'all_baselines':
                    # Check which baseline columns are available
                    available_cols = [col for col in ['dtw_cost', 'dtw_area', 'correlation', 'cusum', 'timestamp_sanity', 
                                                       'feature_flow', 'diagonal_distance'] if col in result_data_att.columns]
                    if len(available_cols) > 0:
                        y_scores = result_data_att[available_cols].sum(axis=1).values
                    else:
                        # Fallback to dtw_cost and dtw_area if available
                        y_scores = result_data_att[['dtw_cost', 'dtw_area', 'correlation', 'cusum']].sum(axis=1).values
                else:
                    y_scores = result_data_att[metric].values
                
                # Check if both classes are present
                unique_classes = np.unique(y_true)
                if len(unique_classes) < 2:
                    print(f"WARNING: {attack_name} has only one class, skipping ROC calculation.")
                    continue
                
                # Calculate ROC curve and AUROC
                fpr, tpr, thresholds = roc_curve(y_true, y_scores)
                roc_auc = auc(fpr, tpr)
                
                # Plot ROC curve with label showing AUROC
                plt.plot(fpr, tpr, 
                        color=attack_color_map[attack_type],
                        label=f'{attack_type}: {roc_auc:.4f}',
                        linewidth=1.5)
            
            # Add diagonal line
            plt.plot([0, 1], [0, 1], color='gray', linestyle='--', linewidth=1, label='Random')
            
            # Labels and title
            plt.xlabel('False Positive Rate', fontsize=11)
            plt.ylabel('True Positive Rate', fontsize=11)
            plt.title(f'Attacks on {modality} ({cfg.dataset_dict[current_dataset]})', fontsize=12)
            plt.legend(loc='lower right', fontsize=9, framealpha=0.9)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # Save plot with metric name in filename
            file_dir = roc_dir / f"combined_roc_{current_dataset}_{modality}_{metric}_{ext}"
            plt.savefig(str(file_dir)+".jpg", dpi=300)
            plt.savefig(str(file_dir)+".pdf", dpi=300)
            plt.close()
            print(f"Generated combined ROC plot: {file_dir}")
    
    print(f"\n✓ Generated {len(metrics_to_plot) * len(modalities)} combined ROC plots for {current_dataset.upper()} dataset")
    #=================================================================================



    #======================= Feature Distribution ==========================
    # Plot histograms to visualize the distribution
    plt.figure(figsize=(12, 3))

    # Plot for Image features
    plt.subplot(1, 2, 1)
    plt.hist(image_features.flatten(), bins=50, color='blue', alpha=0.7, label='Image Features')
    plt.title("Distribution of Image Features")
    plt.xlabel("Feature Value")
    plt.ylabel("Frequency")

    # Plot for LiDAR features
    plt.subplot(1, 2, 2)
    plt.hist(lidar_features.flatten(), bins=50, color='orange', alpha=0.7, label='LiDAR Features')
    plt.title("Distribution of LiDAR Features")
    plt.xlabel("Feature Value")
    plt.ylabel("Frequency")

    plt.tight_layout()
    plt.show()

    # Define shifts from -5 to +5
    shifts = range(-5, 5)  # Includes 0 (no shift)
    data = []

    # Compute cosine similarity for each shift
    for shift in shifts:
        for i in range(len(df_cam_ben)):
            j = i + shift
            if 0 <= j < len(df_lid_ben):  # Ensure indices stay within bounds
                sim = cosine_similarity(df_cam_ben.iloc[i].values.reshape(1, -1),
                                        df_lid_ben.iloc[j].values.reshape(1, -1))[0][0]
                data.append({"Shift": shift, "index": i,  "Cosine Similarity": sim})

    # Convert to DataFrame for Seaborn
    df_plot = pd.DataFrame(data)

    # Plot boxplots
    plt.figure(figsize=(15, 6))
    sns.boxplot(x="Shift", y="Cosine Similarity", data=df_plot, palette="coolwarm")

    plt.xlabel("Shift")
    plt.ylabel("Cosine Similarity")
    plt.title("Box Plots of Cosine Similarities for Different Shifts")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(analysis_dir / "boxplot_cosine_similarity.jpg", dpi=300)
    plt.savefig(analysis_dir / "boxplot_cosine_similarity.pdf", dpi=300)
    plt.show()




if __name__ == "__main__":
    attack_evaluate()