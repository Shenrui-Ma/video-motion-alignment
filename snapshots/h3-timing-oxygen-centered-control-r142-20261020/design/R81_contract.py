import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def protocol():
    return read(ROOT / 'configs/PROTOCOL.json')


def check_package(root=ROOT):
    for row in read(root / 'FREEZE.json')['files']:
        require(sha(root / row['file']) == row['sha256'], 'package changed: ' + row['file'])
    p = read(root / 'configs/PROTOCOL.json')
    for name, digest in {**p['input_sha256'], **p['vendor_sha256']}.items():
        require(sha(root / name) == digest, 'bound input changed: ' + name)
    require(p['indices'] == list(range(20)), 'full 20 observations required')
    require([Path(x['file']).name for x in p['snapshots']] == [f'x0_step{i:03d}.pt' for i in range(20)], 'snapshot order')
    return p


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


def require_sequence(rows):
    require([r['index'] for r in rows] == list(range(20)), 'missing or reordered observation: never impute UNKNOWN')
    require(all(r['status'] == 'complete' for r in rows), 'technical failure blocks full replay')
