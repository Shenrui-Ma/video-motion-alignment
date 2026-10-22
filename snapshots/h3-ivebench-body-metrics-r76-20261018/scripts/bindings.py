"""Adapt source/provenance dimensions; preserve all official numerical functions."""
import math
import sys
from pathlib import Path
from common import ROOT, RUNTIME, SELECTION, PAIRS, read, sha, entry, require
sys.path.insert(0, str(RUNTIME / 'metric_runtime'))
import ive_mf_adapter as official

def validate_full(info, total):
    require((info['width'], info['height'], info['count']) == (1312, 736, total), 'full media geometry/length differs')
    require(info['avg_frame_rate'] == '24/1' and len(info['pts_s']) == total and all(math.isfinite(t) and abs(t - i / 24) <= 1e-6 for i, t in enumerate(info['pts_s'])), 'full media physical time differs')

def validate_provenance(record, expected, prepared_sha, decoded):
    protocol = expected['input_protocol']
    total, count = protocol['h3_frame_count'], protocol['effective_frame_count']
    mapping = protocol['input_to_original_frame']
    fields = {'schema': 'r76-ivebench-source-extension-input-v1', 'pair_id': expected['pair_id'],
              'selection_sha256': sha(SELECTION), 'source_sha256': expected['source']['sha256'],
              'video_sha256': prepared_sha, 'prompt': expected['edit_prompt'], 'reference_images': [],
              'geometry': [1312, 736], 'content_rectangle_xywh': [16, 8, 1280, 720],
              'frames': total, 'fps': 24, 'effective_frame_count': count,
              'evaluate_indices': list(range(count)), 'input_to_original_frame': mapping,
              'padding_indices': list(range(count, total)), 'decoded_pixel_mapping_exact': True}
    for key, value in fields.items():
        require(record.get(key) == value, 'source provenance differs: ' + key)
    hashes = record['original_transformed_frame_md5']
    require(len(hashes) == expected['source']['frame_count'], 'original source frame count differs')
    require(record['input_frame_md5'] == decoded == [hashes[i] for i in mapping], 'source pixel/frame mapping differs')

def validate_source_row(row, expected, ffprobe, ffmpeg):
    protocol = expected['input_protocol']
    count, total = protocol['effective_frame_count'], protocol['h3_frame_count']
    original = official.bound_file(row['source_original'])
    require(sha(original) == expected['source']['sha256'], 'original source differs')
    require(row['score_frame_indices'] == list(range(count)), 'effective prefix differs')
    require(row['input_to_original_frame'] == protocol['input_to_original_frame'], 'original time map differs')
    prepared = official.bound_file(row['source_prepared_video'])
    validate_full(official.media_info(prepared, ffprobe), total)
    provenance = read(official.bound_file(row['source_preparation_record']))
    validate_provenance(provenance, expected, sha(prepared), official.frame_hashes(prepared, ffmpeg))
    score = official.bound_file(row['source_score_video'])
    official.validate_time_view(official.media_info(score, ffprobe), count)
    require(official.frame_hashes(score, ffmpeg) == official.frame_hashes(prepared, ffmpeg, crop_filter(count)), 'source score pixels differ')

def crop_filter(count):
    return f'crop=1280:720:16:8,trim=end_frame={count},setsar=1'

def validate_edited(entry_row, count, ffprobe, ffmpeg, total):
    target = official.bound_file(entry_row['score_video'])
    official.validate_time_view(official.media_info(target, ffprobe), count)
    for role in ('generation_record', 'release_record'):
        official.bound_file(entry_row[role])
    full = official.bound_file(entry_row['full_video'])
    validate_full(official.media_info(full, ffprobe), total)
    require(official.frame_hashes(target, ffmpeg) == official.frame_hashes(full, ffmpeg, crop_filter(count)), 'edited score pixels differ')

def select_pair(manifest, source, selection):
    require(sha(selection) == sha(SELECTION), 'source selection differs')
    expected = entry(source)
    row = read(manifest)
    require(row['pair_id'] == source and row['selection_sha256'] == sha(SELECTION), 'input manifest source binding differs')
    return row, expected

def configure_tracker(source):
    import run_tracks
    from common import checkpoint
    expected = entry(source)
    total = expected['input_protocol']['h3_frame_count']
    run_tracks.SELECTION_SHA = sha(SELECTION)
    run_tracks.select_pair = select_pair
    run_tracks.validate_source_row = validate_source_row
    run_tracks.validate_edited_entry = lambda row, count, probe, ff: validate_edited(row, count, probe, ff, total)
    path = checkpoint()
    require(path.name == 'baseline_offline.pth' and path.parent.name == 'weights', 'checkpoint path layout differs')
    run_tracks.LITERATURE = path.parent.parent
    return run_tracks

def configure_score():
    import score_cached_tracks
    score_cached_tracks.SELECTION_SHA = sha(SELECTION)
    return score_cached_tracks
