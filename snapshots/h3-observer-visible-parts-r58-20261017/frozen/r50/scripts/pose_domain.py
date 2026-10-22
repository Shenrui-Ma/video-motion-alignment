"""Explicit feature view over valid clip time, retaining the complete raw pose."""
import json
import math
from pathlib import Path

import numpy as np
import timing_metrics as m


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _validate_joints(person):
    xy, scores = person['coco17_xy'], person['coco17_score']
    if (not isinstance(xy, list) or len(xy) != 17 or
            any(not isinstance(point, list) or len(point) != 2 for point in xy) or
            not isinstance(scores, list) or len(scores) != 17):
        raise ValueError('malformed pose joints')
    if not all(_finite_number(x) for point in xy for x in point) or not all(_finite_number(x) for x in scores):
        raise ValueError('nonfinite or nonnumeric pose coordinate/score')


def validate_pose(path, geometry):
    raw = json.loads(Path(path).read_text(),
                     parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + x)))
    v = raw['video']
    if (v['fps'], v['width'], v['height'], v['container_frame_count']) != (
            geometry.fps, geometry.width, geometry.height, geometry.frames):
        raise ValueError('pose geometry/timebase mismatch')
    records = raw['frames']
    if len(records) != geometry.frames:
        raise ValueError('pose frame count mismatch')
    for i, row in enumerate(records):
        if type(row['frame']) is not int or row['frame'] != i:
            raise ValueError('pose frame index mismatch')
        time = row['time_s']
        if type(time) not in (int, float) or not math.isfinite(time) or abs(time - i / geometry.fps) > 1e-8:
            raise ValueError('pose physical time mismatch')
        selected = row['selected_person']
        # Validate the complete intake, including unselected people and padded frames.
        for person in row['persons']:
            _validate_joints(person)
        if selected is not None:
            if type(selected) is not int or not 0 <= selected < len(row['persons']):
                raise ValueError('pose person index mismatch')
    return raw


def features(raw, geometry, threshold):
    """Use the unchanged metric on selected records; raw still describes all frames."""
    records = raw['frames'][:geometry.valid_frames]
    xy = np.full((len(records), 17, 2), np.nan)
    conf = np.zeros((len(records), 17))
    for i, record in enumerate(records):
        selected = record['selected_person']
        if selected is not None:
            person = record['persons'][selected]
            xy[i] = person['coco17_xy']
            conf[i] = person['coco17_score']
    return m.pose_features(xy, conf, np.array([r['time_s'] for r in records]),
                           np.array([r['frame'] for r in records]), raw, threshold)
