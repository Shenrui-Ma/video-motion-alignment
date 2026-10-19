"""Input-only adapter around byte-frozen v1 mathematical kernel."""
import importlib.util
from pathlib import Path
import numpy as np

BASE=Path(__file__).resolve().parents[1]
KERNEL=BASE/'phase_shape_profile_candidate_v1/profile.py'
CONVERTER=BASE/'phase_consistent_segmentation_execution/vendor/timing_metrics.py'
THRESHOLDS=(.3,.5)
ARMS=((5,7),(7,9),(6,8),(8,10))


def module_at(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def blank():
    return {'directions':np.full((141,4,2),np.nan),'confidence':np.zeros((141,4)),
            'times':np.arange(141)/24}


def from_features(value):
    result={'directions':value['arm_direction'].copy(),'confidence':value['arm_conf'].copy(),
            'times':value['times'].copy()}
    for bone,(a,b) in enumerate(ARMS):
        finite=np.isfinite(value['conf'][:,[a,b]]).all(axis=1)&np.isfinite(value['xy'][:,[a,b]]).all(axis=(1,2))
        result['directions'][~finite,bone]=np.nan
        result['confidence'][~finite,bone]=0
    return result


def load(path,converter=None):
    converter=converter or module_at(CONVERTER,'frozen_r27_pose_converter')
    values,failures={},{}
    for threshold in THRESHOLDS:
        try:values[threshold]=from_features(converter.load_pose(path,threshold))
        except ValueError as exc:
            if str(exc)!='Insufficient reliable torso anchors for scale normalization':raise
            values[threshold]=blank();failures[str(threshold)]=str(exc)
    return values,failures


def analyze(source,target):
    # Module-local replacement routes input representation only. No code mutation.
    core=module_at(KERNEL,'frozen_v1_core_private')
    frozen_grid=core.grid
    extra={}
    def threshold_grid(a,b,part,threshold):
        result=frozen_grid(a[threshold],b[threshold],part,threshold)
        for key in ('raw_zero','mask','weight'):
            extra[f'{part}__h{threshold}__{key}']=result[key]
        return result
    core.grid=threshold_grid
    result,evidence=core.analyze(source,target)
    evidence.update(extra)
    return result,evidence
