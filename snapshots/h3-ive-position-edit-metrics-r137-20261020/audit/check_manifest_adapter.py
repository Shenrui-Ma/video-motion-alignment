"""Bounded manifest/loader checks; no model imports or new scoring framework."""
from pathlib import Path
from fractions import Fraction
import copy, hashlib, json, math, sys

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
import common, review, paired, metric_inputs, render_native, render_pair

contract = common.validate_static()
source = contract['source_order'][0]
row = common.info(source)
science = common.read(root / 'configs/producer_scientific_contract.json')
actual = next(case for case in science['cases'] if case['arm'] == 'native')
provenance = common.read(root / row['provenance']['file'])
original = actual['original_source']
pts = [Fraction(value) for value in original['actual_pts_rational']]
assert len(pts) == original['frame_count']
duration = Fraction(actual['clip']['duration_rational'])
assert row['valid_frames'] == math.ceil(duration * 24)
mapping = provenance['input_to_original_frame']
for index in range(row['valid_frames']):
    t = Fraction(actual['clip']['start_pts_rational']) + Fraction(index, 24)
    expected = min(range(actual['clip']['start_frame'], actual['clip']['end_frame_inclusive']+1), key=lambda i: (abs(pts[i] - t), i))
    assert mapping[index] == expected
assert provenance['padding_indices'] == list(range(row['valid_frames'], row['geometry']['frames']))
assert all(index == actual['clip']['end_frame_inclusive'] for index in mapping[row['valid_frames']:])
checks = ['shared_helper_hashes', 'static_manifest', 'all_valid_nearest_physical_PTS', 'pure_padding_split']

def rejects(name, operation):
    try:
        operation()
    except (ValueError, AssertionError):
        checks.append(name)
    else:
        raise AssertionError('mutation accepted: ' + name)

rejects('foreign_source_rejected', lambda: common.info('not_registered'))
mutated = copy.deepcopy(row); mutated['prompt'] += ' additional action'
rejects('changed_prompt_rejected', lambda: common.verify_official_prompt(mutated))
graph = common.read(root / 'configs/graphs' / (row['run_id'] + '.json'))
common.verify_official_prompt(row, graph)
graph['5']['inputs']['prompt'] += ' additional action'
rejects('changed_actual_graph_rejected', lambda: common.verify_official_prompt(row, graph))
rejects('past_valid_event_rejected', lambda: review.checked_event({'status':'OBSERVED','frames':[row['valid_frames'],row['valid_frames']]}, row['valid_frames']))
cues = review.mapped_cues(source)
assert cues and all(cue['prepared_frame_cue'] for cue in cues)
for cue in cues:
    assert min(cue['prepared_frame_cue']) >= 0 and max(cue['prepared_frame_cue']) < row['valid_frames']
checks.append('source_event_mapping')
assert common.ROOT == root and 'torch' not in sys.modules
result = {'passed':True, 'checks':checks, 'namespace':contract['namespace'], 'source_id':source,
          'valid_frames':row['valid_frames'], 'total_frames':row['geometry']['frames'],
          'original_frame_count':original['frame_count'], 'original_fps':original['fps_rational'],
          'mapped_cues':cues, 'consumer_freeze':common.bound(root/'CONSUMER_FREEZE.json'),
          'CUDA_initialized':False, 'GPU_started':False}
common.save(root / 'audit/TARGETED_MANIFEST_CHECK.json', result)
print(json.dumps(result, ensure_ascii=False))
