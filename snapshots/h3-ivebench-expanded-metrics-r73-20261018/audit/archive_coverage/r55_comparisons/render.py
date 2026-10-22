"""CPU presentation of five completed R55 all-OFF cases and their exact R54 parents."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
AUDIT = ROOT.parent
DEST = Path('/Users/researcher/Downloads/H3_IVEBench_R55自动检测_五条完整对比_20261018')
LABELS = ['1.参考视频', '2.普通编辑', '3.自动检测后编辑']
FONT = Path('/System/Library/Fonts/STHeiti Light.ttc')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def info(path):
    result = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames:frame=best_effort_timestamp_time', '-show_frames', '-of', 'json', str(path)])
    value = json.loads(result)
    return value['streams'][0], [float(row['best_effort_timestamp_time']) for row in value['frames']]


def main():
    cases = read(AUDIT / 'COVERAGE.json')['omitted_completed_generation_cases']
    assert [row['case'] for row in cases] == ['short_0210', 'short_0230', 'short_0263', 'short_0352', 'short_0370']
    DEST.mkdir(exist_ok=False)
    cap = Image.new('RGB', (3840, 88), 'black')
    draw = ImageDraw.Draw(cap)
    font = ImageFont.truetype(str(FONT), 28)
    draw.text((14, 9), '视频编辑', font=ImageFont.truetype(str(FONT), 21), fill='white')
    for i, label in enumerate(LABELS):
        draw.text((i * 1280 + (1280 - draw.textlength(label, font=font)) / 2, 42), label, font=font, fill='white')
    caption = ROOT / 'caption.png'
    cap.save(caption)
    records = []
    for row in cases:
        source, count = row['case'], row['valid_frames']
        evidence = row['equality_evidence']
        assert sha(evidence['file']) == evidence['sha256']
        identity = read(evidence['file'])
        assert identity['all_off'] is True
        assert all(identity['proofs'][key]['exact'] is True for key in ('full_video', 'score_video'))
        files = [row[key] for key in ('source', 'raw_native_R54', 'raw_auto')]
        for item in files:
            assert sha(item['file']) == item['sha256']
            stream, pts = info(item['file'])
            assert (stream['width'], stream['height'], stream['avg_frame_rate'], int(stream['nb_read_frames'])) == (1312, 736, '24/1', 90)
            assert len(pts) == 90 and all(abs(t - i / 24) < 1e-6 for i, t in enumerate(pts))
        dest = ROOT / (source + '_full_valid.mp4')
        command = ['ffmpeg', '-v', 'error', '-nostdin', '-n']
        for item in files:
            command += ['-threads', '2', '-i', item['file']]
        command += ['-framerate', '24', '-loop', '1', '-i', str(caption)]
        filters = [f'[{i}:v]crop=1280:720:16:8,trim=end_frame={count},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(3)]
        filters += ['[v0][v1][v2]hstack=inputs=3[top]', '[top][3:v]vstack=inputs=2[out]']
        command += ['-filter_complex_threads', '1', '-filter_complex', ';'.join(filters), '-map', '[out]', '-frames:v', str(count), '-an', '-fps_mode', 'vfr', '-c:v', 'libx264', '-crf', '17', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-threads', '2', '-movflags', '+faststart', str(dest)]
        subprocess.run(command, check=True, timeout=180)
        stream, pts = info(dest)
        assert (stream['width'], stream['height'], stream['avg_frame_rate'], int(stream['nb_read_frames'])) == (3840, 808, '24/1', count)
        assert len(pts) == count and all(abs(t - i / 24) < 1e-6 for i, t in enumerate(pts))
        published = DEST / dest.name
        shutil.copy2(dest, published)
        records.append({'source': source, 'valid_frames': count, 'fps': 24, 'physical_indices': list(range(count)), 'crop_xywh': [16, 8, 1280, 720], 'inputs': files, 'labels': LABELS, 'ON_steps': 0, 'R55_R54_exact_RGB_PTS_evidence': evidence, 'video': {'file': str(dest), 'sha256': sha(dest), 'bytes': dest.stat().st_size}, 'download': str(published), 'command': command})
        print(json.dumps({'complete': source, 'valid_frames': count, 'file': str(published)}), flush=True)
    manifest = {'schema': 'r55-five-complete-auto-comparisons-v1', 'fixed_denominator': 5, 'completed': 5, 'total_ON_steps': 0, 'exact_equivalence_scope': 'Each R55 Auto equals its own R54 Native decoded RGB and PTS. This does not assert equivalence to fresh R63/R69 outputs.', 'coverage_evidence_sha256': sha(AUDIT / 'COVERAGE.json'), 'videos': records}
    (ROOT / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    shutil.copy2(ROOT / 'MANIFEST.json', DEST / 'MANIFEST.json')
    note = 'R55：五条已完成的自动检测策略对照\n\n三列：参考视频 / R54普通编辑 / R55自动检测后编辑。\n五例均完成20步采样，实际引导次数为0。原始450帧与414个有效评测帧均已验证：R55输出RGB和PTS逐帧等同各自R54普通编辑。这说明本批自动策略没有触发，不构成引导有效的证据。该相同关系限于R54，不能扩展到后来fresh R69输出。\n\n各视频统一24fps，同一物理帧横拼，裁掉固定画布padding[16,8]；有效帧数依次87、86、74、78、89，尾部补齐帧未展示。原始90帧完整输出保持原位置，MANIFEST列出源、两版原件、SHA及逐帧相同证明。\n'
    (ROOT / 'README.txt').write_text(note)
    (DEST / 'README.txt').write_text(note)


if __name__ == '__main__':
    main()
