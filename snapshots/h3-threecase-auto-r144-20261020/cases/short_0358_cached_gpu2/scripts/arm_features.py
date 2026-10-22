"""CPU candidate: expose existing scale-free arm features without torso features.

The arm calculation is copied verbatim from R55 timing_metrics.pose_features.
This module is not connected to any producer or official evaluation runtime.
"""
import numpy as np

ARMS = [(5, 7), (7, 9), (6, 8), (8, 10)]
ARM_FIELDS = ('arm_direction', 'arm_conf', 'left_arm_direction', 'left_arm_conf',
              'right_arm_direction', 'right_arm_conf')


def arm_features(xy, conf, times, frames, raw, threshold):
    valid = conf >= threshold
    directions, direction_conf = [], []
    for a, b in ARMS:
        difference = xy[:, b]-xy[:, a]
        length = np.linalg.norm(difference, axis=-1)
        okay = valid[:, a] & valid[:, b] & (length > 1e-8)
        vector = difference / np.maximum(length[:, None], 1e-8)
        vector[~okay] = np.nan
        directions.append(vector)
        direction_conf.append(np.minimum(conf[:, a], conf[:, b]))
    arm_direction = np.stack(directions, axis=1)
    return {'raw': raw, 'xy': xy, 'conf': conf, 'times': times, 'frames': frames,
            'threshold': threshold,
            'arm_direction': arm_direction, 'arm_conf': np.stack(direction_conf, axis=1),
            'left_arm_direction': arm_direction[:, :2], 'left_arm_conf': np.stack(direction_conf, axis=1)[:, :2],
            'right_arm_direction': arm_direction[:, 2:], 'right_arm_conf': np.stack(direction_conf, axis=1)[:, 2:]}


def features(raw, geometry, threshold):
    """Use the exact valid-prefix intake used by R55 pose_domain.features."""
    records = raw['frames'][:geometry.valid_frames]
    xy = np.full((len(records), 17, 2), np.nan)
    conf = np.zeros((len(records), 17))
    for i, record in enumerate(records):
        selected = record['selected_person']
        if selected is not None:
            person = record['persons'][selected]
            xy[i] = person['coco17_xy']
            conf[i] = person['coco17_score']
    return arm_features(xy, conf, np.array([r['time_s'] for r in records]),
                        np.array([r['frame'] for r in records]), raw, threshold)
