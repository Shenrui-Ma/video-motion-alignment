"""Frozen R19 selector; scientific unknown is distinct from transport failure."""
import math

def pose_select(physical, measurement):
    if type(physical) is not int or not 0 <= physical < 20:
        raise ValueError('physical index outside frozen20 steps')
    if physical < 6:
        return {'physical_index':physical,'chosen_full':False,'reason':'PREFIX_NATIVE'}
    if physical < 10:
        return {'physical_index':physical,'chosen_full':True,'reason':'FORCED_PREFIX_FULL'}
    if not isinstance(measurement,dict) or measurement.get('status')!='complete':
        raise ValueError('missing/failed actual measurement; ABORT')
    report=measurement['observer']
    gate=report['observability']['50:65']
    diag=report['diagnostics']['50:65']
    values=[diag[t][f]['reliable_lag_frames'] for f in ('arm_direction','wrist_relative') for t in ('0.3','0.5')]
    valid=not gate['reasons'] and all(type(x) is int and math.isfinite(x) for x in values)
    if not valid:reason='UNKNOWN'
    elif all(x>2 for x in values):reason='ON_LATE'
    elif all(-2<=x<=2 for x in values):reason='OFF_ALIGNED'
    elif all(x < -2 for x in values):reason='OFF_ADVANCED'
    else:reason='UNKNOWN'
    return {'physical_index':physical,'chosen_full':reason=='ON_LATE','reason':reason,
            'four_values':values,'original_gate':gate,'measurement_request_sha256':measurement['request_sha256'],
            'measurement_response_sha256':measurement['response_sha256'],'observer_branch':'current_native'}


from .observer import next_decision

def select(physical, measurement, observation=None, previous_actual_full=False):
    if type(physical) is not int or not 0 <= physical < 20:
        raise ValueError('physical index outside frozen20 steps')
    if type(previous_actual_full) is not bool:
        raise ValueError('previous actual selection must be boolean')
    if physical < 6:
        return {'physical_index':physical,'chosen_full':False,'reason':'PREFIX_NATIVE',
                'stage':'prefix','previous_actual_full':previous_actual_full}
    if physical < 10:
        if observation is None:
            raise ValueError('missing current native gap5 observation')
        active, reason = next_decision(observation, previous_actual_full)
        return {'physical_index':physical,'chosen_full':active,'reason':reason,
                'stage':'gap5','previous_actual_full':previous_actual_full,
                'observer_branch':'current_native'}
    result=pose_select(physical,measurement)
    result.update(stage='pose',previous_actual_full=previous_actual_full)
    return result
