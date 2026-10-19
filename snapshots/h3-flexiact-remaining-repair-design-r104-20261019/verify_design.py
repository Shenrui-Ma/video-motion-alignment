#!/usr/bin/env python3
"""Necessary local CPU checks for six source-grounded text proposals."""
import fractions
import hashlib
import json
import pathlib
import re
import subprocess
from prepare_evidence import ROOT, sha, binding, write

def pts(path):
    j = json.loads(subprocess.check_output([
        '/opt/homebrew/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_frames', '-show_streams', '-show_entries',
        'stream=time_base:frame=best_effort_timestamp', '-of', 'json', str(path)]))
    tb = fractions.Fraction(j['streams'][0]['time_base'])
    return [int(f['best_effort_timestamp']) * tb for f in j['frames']]

def main():
    e = json.loads((ROOT / 'EVIDENCE.json').read_text())
    a = json.loads((ROOT / 'ACCEPTANCE.json').read_text())
    r = json.loads((ROOT / 'SOURCE_TARGET_REVIEW.json').read_text())
    assert len(e['items']) == len(a['items']) == 6
    assert len(r['source_review']) == 5 and len(r['target_review']) == 4
    files = {}
    timeline = {}
    checks = []
    sections = ['subject_definitions', 'summary', 'retention_analysis',
                'detailed_description', 'overall_soundscape', 'non_diegetic_music']
    for item in e['items']:
        for field in ['previous_contract', 'previous_graph', 'source_original',
                      'source_prepared', 'target_image', 'provenance',
                      'previous_prompt', 'candidate_prompt']:
            b = item[field]
            if b['file'] not in files:
                assert sha(b['file']) == b['sha256'], (item['case_id'], field)
                files[b['file']] = b
        old = json.loads(pathlib.Path(item['previous_graph']['file']).read_text())
        assert pathlib.Path(item['previous_prompt']['file']).read_text() == old['5']['inputs']['prompt']
        assert old['21']['inputs']['image'] == pathlib.Path(item['target_image']['file']).name
        assert old['22']['inputs']['file'] == pathlib.Path(item['source_prepared']['file']).name
        for field, count, fps in [('source_original', 49, 8), ('source_prepared', 158, 24)]:
            path = item[field]['file']
            if path not in timeline:
                p = pts(path)
                assert p == [fractions.Fraction(i, fps) for i in range(count)], (item['case_id'], field)
                timeline[path] = {'frame_count': count, 'fps': fps,
                                  'pts_rationals': [str(x) for x in p]}
        text = pathlib.Path(item['candidate_prompt']['file']).read_text()
        headers = re.findall(r'^([a-z_]+):$', text, flags=re.M)
        assert headers == sections, (item['case_id'], headers)
        assert '[reference generation]' in text and '[Shot 1]' in text
        assert all(f'<Subject {i}>' in text for i in [1,2,3])
        assert '<Picture 1>' in text and '<Video 1>' in text
        assert not re.search(r'\d+:\d{2}|\bf\d{2}\b', text)
        detail = text.split('detailed_description:\n',1)[1].split('\noverall_soundscape:',1)[0]
        assert 300 <= len(detail.split()) <= 500
        assert text != pathlib.Path(item['previous_prompt']['file']).read_text()
        checks.append({'case_id': item['case_id'], 'actual_old_prompt_exact': True,
                       'input_image_identity_exact': True, 'six_sections_in_order': True,
                       'detail_word_count': len(detail.split()), 'no_manual_event_timestamps_in_prompt': True,
                       'original_and_prepared_pts_exact': True, 'candidate_sha256': item['candidate_prompt']['sha256']})
    for s, v in r['source_review'].items():
        assert v['view_status'] == 'all49_viewed' and v['frame_indices'] == list(range(49))
        assert sha(v['image']['file']) == v['image']['sha256']
    assert all(v['view_status'] == 'full_original_image_viewed' for v in r['target_review'].values())
    assert sum(x['official_pair_exact'] for x in e['items']) == 3
    write('audit/ACTUAL_PTS.json', timeline)
    write('PREPARATION_VERIFIED.json', {'status': 'PASS', 'checks': checks,
         'media_and_evidence_bindings_checked': len(files),
         'official_exact_pairs': 3, 'official_asset_crosspairs': 3,
         'source_review_scope': '245 original frames in five complete49-frame contact sheets, four full target images.',
         'timeline_evidence': binding(ROOT / 'audit/ACTUAL_PTS.json'),
         'inference_executed': False, 'new_dependencies': False,
         'scope': 'Proposal and source binding verification, not a model outcome or prompt efficacy test.'})
    print(json.dumps({'status':'PASS', 'cases':len(checks), 'bound_files':len(files),
                      'actual_video_timelines':len(timeline)}, indent=2))

if __name__ == '__main__':
    main()
