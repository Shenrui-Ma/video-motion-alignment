"""CPU candidate: reject pose endpoints outside the recorded content rectangle.

Reuse the frozen arm descriptor and its confidence thresholds. Raw pose records
remain available for inspection; no active producer imports this module.
"""
import numpy as np


def features(raw, geometry, threshold, crop_xywh, base):
    rect = np.asarray(crop_xywh, dtype=float)
    if rect.shape != (4,) or not np.isfinite(rect).all():
        raise ValueError('content rectangle must contain four finite values')
    x, y, width, height = rect
    if (x < 0 or y < 0 or width <= 0 or height <= 0
            or x + width > geometry.width or y + height > geometry.height):
        raise ValueError('content rectangle must lie inside the video frame')
    original = base.features(raw, geometry, threshold)
    xy, conf = original['xy'], original['conf'].copy()
    inside = (np.isfinite(xy).all(axis=-1)
              & (xy[..., 0] >= x) & (xy[..., 0] < x + width)
              & (xy[..., 1] >= y) & (xy[..., 1] < y + height))
    conf[~inside] = 0
    result = base.arm_features(xy, conf, original['times'], original['frames'],
                               raw, threshold)
    result['joint_inside_content'] = inside
    result['content_xywh'] = rect.tolist()
    return result
