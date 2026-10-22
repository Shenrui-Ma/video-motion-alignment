"""Select exact existing R56 bone vectors; interfaces retain frozen policy names."""
FAMILIES = {'upper': (0, 2), 'forearm': (1, 3)}
NAMES = {'upper': {'arm_direction': ['left_upper_5_7', 'right_upper_6_8'],
                   'left_arm_direction': ['left_upper_5_7'],
                   'right_arm_direction': ['right_upper_6_8']},
         'forearm': {'arm_direction': ['left_forearm_7_9', 'right_forearm_8_10'],
                     'left_arm_direction': ['left_forearm_7_9'],
                     'right_arm_direction': ['right_forearm_8_10']}}


def select(existing, family):
    indices = list(FAMILIES[family])
    result = dict(existing)
    direction = existing['arm_direction'][:, indices]
    confidence = existing['arm_conf'][:, indices]
    result.update(arm_direction=direction, arm_conf=confidence,
                  left_arm_direction=direction[:, :1], left_arm_conf=confidence[:, :1],
                  right_arm_direction=direction[:, 1:], right_arm_conf=confidence[:, 1:])
    return result


def make(helper, family):
    def features(raw, geometry, threshold):
        return select(helper.features(raw, geometry, threshold), family)
    return features
