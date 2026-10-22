"""Add actual human-review notes to the frozen consumer's generated report."""
from pathlib import Path
import html
import json
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import read, sha, verify_runtime
import make_showcase


def compatible_read(path):
    """Translate the independently authored root review in memory only."""
    value = read(path)
    if Path(path).name == 'HUMAN_REVIEW.json' and 'source_selection_sha256' not in value:
        source = value['source']
        assert value['reviewer'] == 'root' and source in ('short_0126', 'short_0392')
        if source == 'short_0126':
            assert value['requested_object_added'] is True
            assert value['source_action_preserved'] is False
            edit = 'PARTIAL_CAT_ADDED_SCENE_CHANGED'
            motion = 'FAILED_ACTION_CHANGED'
        else:
            assert value['edit_goal_visibly_achieved'] is False
            assert value['source_action_preserved'] == 'coarsely yes in sixframes'
            edit = 'FAILED_FIREPLACE_REMAINS'
            motion = 'SIMILAR_AT_FIXED_SIX_VIEWS'
        evidence = Path(value['evidence'])
        assert evidence == ROOT / 'showcase' / source / 'six_times.png'
        assert evidence.is_file()
        adapted = dict(value)
        adapted.update({
            'source_selection_sha256': sha(make_showcase.SELECTION),
            'editing_success': {'native': edit, 'forced': edit},
            'motion_preservation': {'native': motion, 'forced': motion},
        })
        receipt = {'source_review_sha256': sha(Path(path)), 'evidence_sha256': sha(evidence),
                   'adaptation': 'In-memory display schema translation; original root review is unchanged.',
                   'display_review': adapted}
        Path(__file__).with_name(source + '_ROOT_REVIEW_DISPLAY_ADAPTATION.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
        return adapted
    return value

if __name__ == '__main__':
    verify_runtime()
    destination = Path('/Users/researcher/Downloads/H3_IVEBench_四条新素材_固定引导_20261018.html')
    make_showcase.read = compatible_read
    make_showcase.build(destination)
    document = destination.read_text()
    report = read(destination.with_suffix('.json'))
    if all(report['means'][method]['valid_count'] == 4 for method in ('native', 'forced')):
        native = report['means']['native']['mean_if_all_four_valid']
        forced = report['means']['forced']['mean_if_all_four_valid']
        summary = f'<p>四条任务均已完成成对生成与 MF 评测。MF 平均值：普通编辑 {native:.4f}，固定时序引导 {forced:.4f}，变化 {forced-native:+.4f}。逐例检查显示，前三条存在动作或场景改变，第四条未完成删除壁炉的编辑要求；这些结果尚未显示固定引导恢复原动作的效果。</p>'
        document = document.replace('<section>', summary + '<section>', 1)
    for source, note in read(Path(__file__).with_name('DISPLAY_NOTES.json')).items():
        review = ROOT / 'results' / source / 'HUMAN_REVIEW.json'
        if not review.exists():
            raise ValueError('Display assessment lacks an actual review: ' + source)
        start = document.index('<h2>' + source + ' · ')
        end = document.index('</h2>', start) + len('</h2>')
        document = document[:end] + '<p>' + html.escape(note) + '</p>' + document[end:]
    destination.write_text(document)
    print({'html': str(destination), 'sha256': sha(destination), 'embedded_videos': document.count('data:video/mp4;base64,')})
