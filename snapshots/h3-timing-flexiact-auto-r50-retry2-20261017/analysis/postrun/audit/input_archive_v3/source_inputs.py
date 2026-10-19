"""Register the exact five inputs already bound by each frozen R49 parent."""
import hashlib
import json
from pathlib import Path

read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def expected_inputs(case, provenance, parent):
    source = case['source_id']
    expected = {'inputs/' + case['video']: case['video_sha256'],
                'inputs/' + case['portrait']: case['portrait_sha256'],
                'inputs/' + case['provenance']: case['provenance_sha256'],
                f'inputs/source_{source}_original.mp4': provenance['source_original_sha256'],
                f'inputs/source_{source}_official_caption.txt': provenance['caption_sha256']}
    assert provenance['video_sha256'] == case['video_sha256']
    assert provenance['portrait_sha256'] == case['portrait_sha256']
    assert provenance['source_id'] == source
    for name, digest in expected.items():
        assert parent[name]['sha256'] == digest, 'R49 parent and retry input binding differ'
    return expected


def checked_inputs(root, cases):
    root = Path(root)
    manifest = read(root / 'deploy_manifest.json')['files']
    science = root / 'configs/scientific_contract.json'
    assert sha(science) == manifest['configs/scientific_contract.json']['sha256']
    declared = {c['run_id']: c for c in read(science)['cases']}
    paths = []
    for case in cases:
        assert declared[case['run_id']] == case
        parent_rel = case['parent_file_inventory']
        assert sha(root / parent_rel) == manifest[parent_rel]['sha256']
        provenance = root / 'inputs' / case['provenance']
        assert sha(provenance) == case['provenance_sha256']
        parent = read(root / parent_rel)
        for name, digest in expected_inputs(case, read(provenance), parent).items():
            path = root / name
            assert sha(path) == digest and path.stat().st_size == parent[name]['bytes']
            paths.append(path)
    return paths


def install(consumer):
    original = consumer.inventory

    def inventory(cases=None):
        selected = consumer.P['cases'] if cases is None else cases
        return sorted(set(original(cases)) | set(checked_inputs(consumer.ROOT, selected)))

    consumer.inventory = inventory
