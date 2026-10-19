"""Describe frozen correspondence displacement against existing source tracks."""
from pathlib import Path
import hashlib
import json
import time
import numpy as np

root = Path(__file__).resolve().parent
rows = np.load(root / 'points.npz')['rows']
rows = rows[rows['status'] == 0]
# The stored prediction preserves the point's within-cell offset.
jump = np.hypot(rows['predicted_x'] - rows['source_x'],
                rows['predicted_y'] - rows['source_y'])
cell_jump = 32 * np.hypot(rows['target_cell'] % 41 - rows['source_cell'] % 41,
                         rows['target_cell'] // 41 - rows['source_cell'] // 41)
assert np.allclose(jump, cell_jump, atol=1e-9, rtol=0)
result = {
    'created_unix': time.time(),
    'points_sha256': hashlib.sha256((root / 'points.npz').read_bytes()).hexdigest(),
    'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'Post-hoc source-track diagnostic. Counts repeat source observations across layers. No changed routing or new inference. Source CoTracker is a noisy reference.',
    'patch_size_pixels': 32,
    'displacement_definition': 'Euclidean distance between matched token cell centers; preserves source point sub-cell offset.',
    'cell_point_displacement_agreement': True,
    'groups': [],
}
for label, mask in [('all_matched', np.ones(len(rows), bool)),
                    ('source_person_tracks', rows['region'] == 1)]:
    for lo, hi in [(0, 32), (32, 64), (64, 128), (128, 256), (256, float('inf'))]:
        x = rows[mask & (cell_jump >= lo) & (cell_jump < hi)]
        if len(x) == 0:
            continue
        result['groups'].append({
            'subset': label,
            'displacement_px': [lo, hi if np.isfinite(hi) else None],
            'count_repeated_observations': len(x),
            'mean_error_px': float(x['error_px'].mean()),
            'median_error_px': float(np.median(x['error_px'])),
            'identity_mean_error_same_points_px': float(x['identity_error_px'].mean()),
            'fraction_better_than_identity': float((x['error_px'] < x['identity_error_px']).mean()),
            'PCK32': float((x['error_px'] <= 32).mean()),
        })
path = root / 'DISPLACEMENT_TAIL_DIAGNOSTIC.json'
path.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
