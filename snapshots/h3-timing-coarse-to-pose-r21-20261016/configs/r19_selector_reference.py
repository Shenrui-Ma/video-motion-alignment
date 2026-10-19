"""Frozen R19 selector; scientific unknown is distinct from transport failure."""
import math

def select(physical, measurement):
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
