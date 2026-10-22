"""R81 source-specified adult selection; time detection remains online."""
import copy

def require(ok,message):
 if not ok:raise ValueError(message)

def validate_pose_shape(raw, geometry):
    v = raw['video']
    require([v[k] for k in ('width', 'height', 'container_frame_count', 'fps')] ==
            [geometry[k] for k in ('width', 'height', 'frames', 'fps')], 'pose geometry')
    require(len(raw['frames']) == geometry['frames'], 'pose frame count')
    for index, row in enumerate(raw['frames']):
        require(row['frame'] == index and abs(row['time_s'] - index / geometry['fps']) < 1e-8, 'pose physical time')

def adult_only(raw, geometry, bounds=(.4, .75)):
    validate_pose_shape(raw, geometry)
    result = copy.deepcopy(raw)
    rejected = []
    for row in result['frames']:
        index = row['selected_person']
        if index is None:
            continue
        box = row['persons'][index]['box_xyxy']
        centre = (box[0] + box[2]) / (2 * geometry['width'])
        if not bounds[0] <= centre <= bounds[1]:
            rejected.append(row['frame'])
            row['selected_person'] = None
    return result, rejected
