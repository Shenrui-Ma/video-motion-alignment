"""Bind all five completed source sidecars without altering original pose JSON."""
from pathlib import Path
from remote_one import read, require, save, sha, validate_pose

HERE = Path(__file__).resolve().parent


def finalize():
    protocol = read(HERE / 'PROTOCOL.json')
    freeze = read(HERE / 'FREEZE.json')
    for rel, digest in freeze['files'].items():
        require(sha(HERE / rel) == digest, 'code freeze')
    sources = {}
    for source_id, input_item in protocol['sources'].items():
        folder = HERE / source_id
        complete = read(folder / 'COMPLETE.json')
        require(complete['source_id'] == source_id and complete['status'] == 'complete', 'source completion identity')
        require(complete['code_freeze_sha256'] == sha(HERE / 'FREEZE.json'), 'completion code freeze')
        require({p.name for p in folder.iterdir()} == set(complete['files']) | {'COMPLETE.json'}, 'exact source inventory')
        for rel, digest in complete['files'].items():
            require(sha(folder / rel) == digest, 'source output hash')
        pose = folder / ('source_' + source_id + '_video.pose.json')
        raw = validate_pose(read(pose), input_item['video_sha256'], protocol)
        provenance = folder / 'PROVENANCE.json'
        p = read(provenance)
        require(p['source_id'] == source_id and p['pose_sha256'] == sha(pose), 'provenance identity')
        sources[source_id] = {'source_id': source_id, 'status': 'complete', 'pose_path': str(pose), 'pose_sha256': sha(pose), 'remote_pose_path': p['pose_path'], 'video_path': str(Path(protocol['root_local']) / input_item['video']), 'remote_video_path': p['video_path'], 'video_sha256': input_item['video_sha256'], 'geometry': protocol['geometry'], 'extraction': raw['extraction'], 'provenance_path': str(provenance), 'provenance_sha256': sha(provenance), 'elapsed_seconds': p['elapsed_seconds'], 'valid_observation_frames': [0, 146], 'padding_frames': [147, 157], 'original_sample_indices': protocol['original_sample_indices'], 'complete_sha256': sha(folder / 'COMPLETE.json')}
    value = {'schema': protocol['schema'], 'status': 'complete', 'sources': sources, 'producer_manifest_sha256': protocol['producer_manifest_sha256'], 'code_freeze_sha256': sha(HERE / 'FREEZE.json'), 'protocol_sha256': sha(HERE / 'PROTOCOL.json'), 'raw_pose_preserved': True, 'statistics_domain': 'Full158 raw extraction; downstream R50 explicitly uses0..146. No timing score computed here.'}
    require(not (HERE / 'MANIFEST.json').exists(), 'manifest already exists')
    save(HERE / 'MANIFEST.json', value)
    print('Completed five fixed sources:', HERE / 'MANIFEST.json', sha(HERE / 'MANIFEST.json'))


if __name__ == '__main__': finalize()
