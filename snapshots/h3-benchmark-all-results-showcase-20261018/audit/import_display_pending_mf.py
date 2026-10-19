"""Bind completed tracker scores to exact inventory media; preserve visual reviews."""
from pathlib import Path
import argparse, copy, hashlib, json, os, time

ROOT = Path(__file__).resolve().parents[1]
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    return json.loads(Path(path).read_text())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--proof-sha', required=True)
    args = parser.parse_args()
    content = args.proof.read_bytes()
    assert hashlib.sha256(content).hexdigest() == args.proof_sha
    proof = json.loads(content)
    paths = {name: ROOT/'inventory'/name for name in ('flexiact.json', 'ivebench.json')}
    original = {name: path.read_bytes() for name, path in paths.items()}
    values = {name: json.loads(data) for name, data in original.items()}
    index = {row['id']: row for value in values.values() for row in value['items']}
    folder = ROOT/'audit'/('pending_mf_import_'+args.proof_sha[:12])
    assert not folder.exists()
    snapshot = folder/'RESULTS_VERIFIED_SNAPSHOT.json'
    changes = []
    field_media = {'native':'ordinary_video_path', 'guided':'guided_video_path',
                   'alternative_native':'alternative_video_path'}
    for entry in proof['results']:
        score_path = Path(entry['result_file'])
        release_path = Path(entry['release_file'])
        assert sha(score_path) == entry['result_sha256']
        assert sha(release_path) == entry['release_sha256']
        score = read(score_path)
        release = read(release_path)
        score_field = {'FlexiAct':'score', 'IVEBench':'motion_fidelity'}[entry['benchmark']]
        assert score['benchmark'] == entry['benchmark']
        assert score[score_field] == entry['score']
        assert release['passed'] and release['process_absent'] and release['CUDA_absent']
        assert release['returncode'] == 0
        assert score['official_numerics_unchanged']
        for binding in entry['inventory_bindings']:
            row = index[binding['id']]
            field = binding['field']
            assert field in field_media
            assert sha(row[field_media[field]]) == entry['actual_generated_video_sha256']
            assert sha(row['reference_video_path']) == score['source_full_sha256']
            assert row['valid_frames'] == score['valid_frames'] == entry['valid_frames']
            previous_row = copy.deepcopy(row)
            mf = row['quantitative_metrics']['motion_fidelity']
            if mf.get(field) is not None:
                assert mf[field] == entry['score']
                assert mf.get('source_sha256', {}).get(str(score_path)) == entry['result_sha256']
                continue
            mf[field] = entry['score']
            mf['evaluation_frames'] = score['evaluation_frames']
            mf['evaluation_fps'] = score['evaluation_fps']
            needed = ['native']
            if row.get('guided_video_path'): needed.append('guided')
            if row.get('alternative_video_path'): needed.append('alternative_native')
            mf['status'] = 'complete' if all(mf.get(key) is not None for key in needed) else 'partial'
            mf['delta'] = (mf['guided']-mf['native']) if row['comparison_kind']=='guided_pair' and all(mf.get(key) is not None for key in ('native','guided')) else None
            mf['scope'] = '官方MF按本条实际视频、原参考及有效帧域评分；复用参考轨迹时保留原运行环境记录。动作和任务完成情况另见逐帧审阅。'
            mf.setdefault('actual_score_bindings', {})[field] = {
                'result_file':str(score_path), 'sha256':entry['result_sha256'],
                'source_score_sha256':score['source_score_sha256'],
                'source_cache_reused':score['source_cache_reused'],
                'runtime_provenance':score['runtime_provenance'],
            }
            evidence = {str(score_path):entry['result_sha256'], str(release_path):entry['release_sha256'],
                        str(snapshot):args.proof_sha}
            mf.setdefault('source_files', [])
            mf.setdefault('source_sha256', {}).update(evidence)
            row.setdefault('evidence_paths', [])
            row.setdefault('evidence_sha256', {}).update(evidence)
            for path in evidence:
                if path not in mf['source_files']: mf['source_files'].append(path)
                if path not in row['evidence_paths']: row['evidence_paths'].append(path)
            for key in previous_row:
                if key not in ('quantitative_metrics','evidence_paths','evidence_sha256'):
                    assert row[key] == previous_row[key]
            changes.append({'id':row['id'], 'field':field, 'score':entry['score']})
    assert changes
    folder.mkdir()
    snapshot.write_bytes(content)
    changed_ids = {entry['id'] for entry in changes}
    updated = {}
    for name, path in paths.items():
        before = json.loads(original[name])
        for old, new in zip(before['items'], values[name]['items']):
            if old['id'] not in changed_ids: assert old == new
        assert path.read_bytes() == original[name]
        (folder/('PREVIOUS_'+name)).write_bytes(original[name])
        if values[name] != before:
            temp = path.with_suffix('.json.pendingmf.tmp')
            temp.write_text(json.dumps(values[name],ensure_ascii=False,indent=2)+'\n')
            os.replace(temp,path)
        updated[name] = sha(path)
    receipt = {'changes':changes,'inventory_sha256':updated,'proof_snapshot':str(snapshot),
               'proof_sha256':args.proof_sha,'visual_verdicts_preserved':True,'UI_unchanged':True,
               'created_unix':time.time()}
    (folder/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__ == '__main__': main()
