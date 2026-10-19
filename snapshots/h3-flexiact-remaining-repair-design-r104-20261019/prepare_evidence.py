#!/usr/bin/env python3
"""CPU-only source/target inspection artifacts; never creates inference jobs."""
import csv
import hashlib
import json
import pathlib
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
PROJECTS = ROOT.parent
METADATA = PROJECTS / 'h3-flexiact-expanded-selection-20261018/metadata'
WANTED = [('crouch', 'movie_man_4'), ('human2animal_1', 'movie_man_11'),
          ('fitness', 'game_man_4'), ('human2animal_3', 'game_man_4'),
          ('human2animal_2', 'movie_man_11'), ('crouch', 'movie_man_5')]

def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def binding(path):
    p = pathlib.Path(path)
    return {'file': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size}

def write(name, value):
    p = ROOT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def probe(path):
    return json.loads(subprocess.check_output([
        '/opt/homebrew/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries',
        'stream=width,height,avg_frame_rate,r_frame_rate,nb_read_frames,duration',
        '-of', 'json', str(path)]))['streams'][0]

def source_sheet(path, source):
    folder = ROOT / 'review'
    folder.mkdir(exist_ok=True)
    w, h = 288, 192
    raw = subprocess.check_output([
        '/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '2', '-i', str(path),
        '-map', '0:v:0', '-an', '-vf', f'scale={w}:{h}:flags=lanczos',
        '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    n = len(raw) // (w * h * 3)
    assert n == 49 and len(raw) == n * w * h * 3, (source, n)
    out = Image.new('RGB', (w * 7, (h + 24) * 7), '#101218')
    draw = ImageDraw.Draw(out)
    font = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 16)
    for i in range(n):
        x, y = (i % 7) * w, (i // 7) * (h + 24)
        draw.text((x + 4, y + 3), f'{source}  f{i:02d}  {i/8:.3f}s', font=font, fill='white')
        out.paste(Image.frombytes('RGB', (w, h), raw[i*w*h*3:(i+1)*w*h*3]), (x, y + 24))
    dest = folder / f'{source}_all49.jpg'
    out.save(dest, quality=95)
    return {'image': binding(dest), 'frame_indices': list(range(49)),
            'source_pts_seconds': [i / 8 for i in range(49)],
            'view_status': 'pending_actual_visual_review'}

def main():
    for name in ['prompts', 'metadata', 'review', 'audit']:
        (ROOT / name).mkdir(exist_ok=True)
    queue_file = PROJECTS / 'h3-task-repair-queue-audit-20261019/FAILURE_ROW_MAPPING.json'
    rows = json.loads(queue_file.read_text())['rows']
    result = {'schema': 'r104-source-prompt-design-evidence-v1',
              'scope': 'CPU-only preparation. Six prior tasks; five unique motion sources; no new inference.',
              'failure_queue': binding(queue_file), 'items': [], 'source_review_artifacts': {}}
    for source, target in WANTED:
        row = next(r for r in rows if r['task_key'] == f'FlexiAct::{source}::{target}')
        parent = pathlib.Path(row['source_contract']['path']).parents[1]
        contract_file = parent / 'configs/scientific_contract.json'
        contract = json.loads(contract_file.read_text())
        case = next(c for c in contract['cases'] if c['run_id'] == row['run_id'])
        graph_file = parent / 'configs/graphs' / f'{row["run_id"]}.json'
        graph = json.loads(graph_file.read_text())
        ref = graph['5']['inputs']
        assert ref['ref_image'] == ['21', 0] and ref['ref_video'] == ['23', 0]
        assert graph['23']['inputs']['video'] == ['22', 0]
        video = parent / 'inputs' / graph['22']['inputs']['file']
        image = parent / 'inputs' / graph['21']['inputs']['image']
        original = parent / 'inputs' / f'source_{source}_original.mp4'
        provenance_file = parent / 'inputs' / f'source_{source}_provenance.json'
        provenance = json.loads(provenance_file.read_text())
        assert sha(image) == row['reference_image']['sha256']
        assert sha(video) == provenance['video_sha256']
        assert sha(original) == provenance['source_original_sha256']
        assert provenance['input_to_original'] == [i // 3 for i in range(147)] + [48] * 11
        assert provenance['all158_decoded_frames_match_declared_source_exactly']
        op, vp = probe(original), probe(video)
        assert int(op['nb_read_frames']) == 49 and op['avg_frame_rate'] == '8/1'
        assert (vp['width'], vp['height'], int(vp['nb_read_frames']), vp['avg_frame_rate']) == (1152, 768, 158, '24/1')
        prompt = ref['prompt']
        assert prompt == row['actual_prompt'] == case['prompt']
        previous_prompt = ROOT / 'prompts' / f'{source}__{target}_previous.txt'
        previous_prompt.write_text(prompt)
        assert sha(previous_prompt) == hashlib.sha256(prompt.encode()).hexdigest()
        csv_info = {}
        for kind in ['crop', 'val_image']:
            p = METADATA / f'flexiact_hf__benchmark__captions__human__{source}__{kind}.csv'
            data = list(csv.DictReader(p.open()))
            dest = ROOT / 'metadata' / p.name
            shutil.copyfile(p, dest)
            selected = [{'row_zero_based': i, 'row': r} for i, r in enumerate(data)
                        if kind == 'crop' and i == 0 or kind == 'val_image' and target + '.' in r['path']]
            csv_info[kind] = {'file': binding(dest), 'source': binding(p),
                              'matching_rows': selected,
                              'all_rows': data if kind == 'val_image' else None}
        item = {'case_id': f'{source}__{target}', 'source_id': source, 'target_id': target,
                'previous_version': row['prompt_version'], 'previous_run': row['run_id'],
                'previous_contract': binding(contract_file), 'previous_graph': binding(graph_file),
                'previous_case': case, 'source_original': binding(original),
                'source_prepared': binding(video), 'target_image': binding(image),
                'provenance': binding(provenance_file), 'previous_prompt': binding(previous_prompt),
                'previous_prompt_actual_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                'historical_failure_record': row, 'official_metadata': csv_info,
                'official_pair_exact': bool(csv_info['val_image']['matching_rows']),
                'input_graph_reference_edges': {k: graph[k] for k in ['5', '21', '22', '23']},
                'source_properties': op, 'prepared_properties': vp,
                'timeline': {'source_frames': 49, 'source_fps': 8, 'valid_frames': 147,
                             'total_frames': 158, 'output_fps': 24, 'terminal_padding': 11,
                             'evaluation_indices': list(range(0, 147, 3))}}
        result['items'].append(item)
        if source not in result['source_review_artifacts']:
            result['source_review_artifacts'][source] = source_sheet(original, source)
    guide = PROJECTS / 'h3-timing-flexiact-character-repair-r98-20261019/design/official_ref-en.md'
    readme = PROJECTS / 'h3-timing-auto-motion-r26-20261017/literature/benchmark_selection_20261017/sources/flexiact_readme.txt'
    for p in [guide, readme]:
        shutil.copyfile(p, ROOT / 'metadata' / p.name)
    result['official_guide'] = binding(ROOT / 'metadata' / guide.name)
    result['official_flexiact_readme'] = binding(ROOT / 'metadata' / readme.name)
    result['official_dataset_revision'] = '69d7747f93e1b913a3dca306bf8e91ee74fea7d4'
    write('EVIDENCE.json', result)
    print(json.dumps({'cases': [x['case_id'] for x in result['items']],
                      'sources': list(result['source_review_artifacts']),
                      'evidence': binding(ROOT / 'EVIDENCE.json')}, indent=2))

if __name__ == '__main__':
    main()
