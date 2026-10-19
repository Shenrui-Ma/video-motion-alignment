"""Presentation-only footer replacement; retain frame order and full picture area."""
from pathlib import Path
import fcntl
import hashlib
import json
import subprocess
import time
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SOURCE = Path('/Users/researcher/DevProjects/h3-timing-auto-bedside-r35-20261017/analysis/postrun/captured/r35_s07_seed2026101311_auto/final')
LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    with LOCK.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('BUSY Mac CPU; no media changed')
            return
        footer = Image.new('RGB', (2624, 32), 'black')
        draw = ImageDraw.Draw(footer)
        font = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 20)
        draw.text((10, 4), '角色替换', font=font, fill='white')
        labels = ['1.参考视频', '2.编辑后视频', '3.编辑+固定窗口时序引导', '4.编辑+自动时序引导']
        for column, label in enumerate(labels):
            box = draw.textbbox((0, 0), label, font=font)
            draw.text((column * 656 + (656 - box[2]) / 2, 4), label, font=font, fill='white')
        footer.save(HERE / 'caption.png')
        records = []
        for folder, name in [('media', 'short_comparison.mp4'), ('full_media', 'full_comparison.mp4')]:
            source = SOURCE / folder / 'fixed_clip_comparison.mp4'
            target = HERE / name
            if target.exists():
                raise FileExistsError(target)
            command = ['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '2', '-i', str(source),
                       '-i', str(HERE / 'caption.png'), '-filter_complex_threads', '1',
                       '-filter_complex', '[0:v]crop=2624:368:0:0[picture];[picture][1:v]vstack=inputs=2[out]',
                       '-map', '[out]', '-an', '-c:v', 'libx264', '-threads', '2', '-crf', '18',
                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target)]
            subprocess.run(command, check=True)
            probe = json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe', '-v', 'error',
                '-select_streams', 'v:0', '-show_frames', '-show_entries',
                'stream=width,height,nb_frames,r_frame_rate:frame=best_effort_timestamp_time', '-of', 'json', str(target)]))
            original = json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe', '-v', 'error',
                '-select_streams', 'v:0', '-show_frames', '-show_entries',
                'stream=width,height,nb_frames,r_frame_rate:frame=best_effort_timestamp_time', '-of', 'json', str(source)]))
            assert probe['streams'] == original['streams']
            assert probe['frames'] == original['frames']
            records.append({'input': str(source), 'input_sha256': digest(source), 'output': str(target),
                            'output_sha256': digest(target), 'frames': len(probe['frames']),
                            'geometry_and_pts_exact': True})
        (HERE / 'MANIFEST.json').write_text(json.dumps({'unix': time.time(), 'labels': labels,
            'scope': 'Footer and video re-encoding for presentation; scientific metrics use archived original videos',
            'records': records}, ensure_ascii=False, indent=2) + '\n')
        print('Completed two captioned comparisons; frame counts and PTS verified')

if __name__ == '__main__':
    main()
