"""CPU binding for later official IVE motion scoring, with physical-time provenance."""
from common import *
from paired import verify_pair_intake

def prepare(source, paired=False):
    validate_static()
    p = info(source)
    gate = verify_pair_intake(source) if paired else verify_intake(source)
    directory = ROOT/('incoming_pairs' if paired else 'incoming')/source
    rows = {'source':bound(ROOT/p['source']['file'])}
    for mode in (('native','forced') if paired else ('native',)):
        rows[mode] = bound(directory/f'{mode}.mp4')
        require(rows[mode]['sha256'] == gate['runs'][mode]['video']['sha256'], 'actual metric media differs')
    provenance = read(ROOT/p['provenance']['file'])
    valid = p['valid_frames']
    data = {'schema':'r121-ive-mf-input-binding-v1', 'source_id':source,
        'status':'inputs_ready_score_pending', 'protocol':'IVE official motion fidelity; runtime and evaluator bound by separate scoring attempt',
        'evaluation_indices':list(range(valid)), 'fps':24, 'valid_frames':valid, 'total_frames':p['geometry']['frames'],
        'crop_xywh':p['crop_xywh'], 'raw_videos':rows, 'reference_image_used':False,
        'original_source':p['original_media'], 'clip':p['clip'], 'original_task':p['original_task'],
        'evaluation_scope':p['evaluation_scope'], 'input_to_original_frame':provenance['input_to_original_frame'][:valid],
        'original_pts_rational':provenance['original_pts_rational'],
        'producer_seal_sha256':config()['producer_seal_sha256'],
        'gate':bound(directory/('PAIR_RUNTIME_GATE.json' if paired else 'NATIVE_RUNTIME_GATE.json')),
        'collection':bound(directory/'COLLECTION.json'), 'provenance':bound(ROOT/p['provenance']['file']),
        'task_acceptance':'reviewed separately', 'GPU_started':False, 'score':None}
    dest = ROOT/'prepared'/source/('paired' if paired else 'native')/'MF_INPUTS.json'
    if dest.exists(): require(read(dest) == data, 'existing metric binding changed')
    else: save(dest, data)
    return bound(dest)
