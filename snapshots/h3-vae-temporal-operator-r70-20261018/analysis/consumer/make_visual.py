"""CPU presentation of verified R70 videos; labels preserve operator meaning."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--verified', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    verified = json.loads(args.verified.read_text())
    assert verified['passed'] and sha(args.run / 'RESULT.json') == verified['result_sha256']
    assert not args.out.exists(), 'preserve previous display'
    args.out.mkdir(parents=True)
    ffmpeg = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
    ffprobe = shutil.which('ffprobe') or '/opt/homebrew/bin/ffprobe'
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 18)
    small = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 14)
    decoded = {}
    for name, entry in verified['products'].items():
        path = args.run / Path(entry['file']).name
        assert sha(path) == entry['sha256']
        folder = args.out / 'frames' / name
        folder.mkdir(parents=True)
        subprocess.run([ffmpeg, '-v', 'error', '-threads', '2', '-i', str(path), '-vf', 'scale=576:384',
            '-fps_mode', 'passthrough', '-start_number', '0', str(folder / '%03d.png')], check=True)
        assert len(list(folder.glob('*.png'))) == 158
        decoded[name] = folder
    binding = {'verified_sha256': sha(args.verified), 'result_sha256': verified['result_sha256'],
        'scope': 'Operator geometry visualization. Offline mapping uses final-output fit, not online guidance.',
        'products': {}, 'fixed_frames': [0,12,24,36,48,60], 'block_boundary_frames': [16,17,18,33,34,35]}
    for name in ['identity', 'shift3', 'offline_mapping']:
        if name == 'identity':
            columns = [('baseline_Dz', '原始 x0 解码 D(z)'), ('identity_RGB_roundtrip', '再编码重建 D(E(D(z)))')]
        else:
            columns = [(name+'_RGB_target', 'RGB 直接时间重排'), (name+'_latent_warp', 'latent 时间重排后解码'),
                (name+'_RGB_roundtrip', 'RGB 重排后再编码、解码')]
        coords = json.loads((args.run / (name + '_coordinates.json')).read_text())
        valid = set(verified['maps'][name]['common_valid_indices'])
        def frame(i, width=576):
            h=width*2//3
            canvas=Image.new('RGB',(len(columns)*width,h+52),'black')
            draw=ImageDraw.Draw(canvas)
            for j,(key,label) in enumerate(columns):
                image=Image.open(decoded[key]/f'{i:03d}.png').convert('RGB')
                if width!=576:image=image.resize((width,h),Image.Resampling.LANCZOS)
                canvas.paste(image,(j*width,0))
                draw.text((j*width+width//2,h+14),label,font=font,fill='white',anchor='mm')
            text=f'{i/24:.3f} s | RGB frame {i} | map to {coords["rgb_positions"][i]/24:.3f} s'
            text+=' | common valid' if i in valid else ' | boundary/padding excluded'
            draw.text((6,h+31),text,font=small,fill='white')
            return canvas
        video=args.out/(name+'_comparison.mp4');size=f'{len(columns)*576}x436'
        child=subprocess.Popen([ffmpeg,'-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',size,'-r','24','-i','pipe:0',
            '-frames:v','158','-an','-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for i in range(158):child.stdin.write(frame(i).tobytes())
            child.stdin.close();error=child.stderr.read().decode();assert child.wait()==0,error
        finally:
            if child.poll() is None:child.kill();child.wait()
            if not child.stdin.closed:child.stdin.close()
            child.stderr.close()
        framesets={'six_times':binding['fixed_frames'],'block_boundaries':binding['block_boundary_frames']}
        if name!='identity':
            framesets['largest_operator_errors']=verified['maps'][name]['comparisons']['latent_warp_vs_target']['highest_error_common_frames']
        for group,indices in framesets.items():
            panes=[frame(i,384) for i in indices]
            sheet=Image.new('RGB',(panes[0].width,panes[0].height*len(panes)),'black')
            for row,pane in enumerate(panes):sheet.paste(pane,(0,row*pane.height))
            sheet.save(args.out/(name+'_'+group+'.png'))
        probe=json.loads(subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0','-count_frames',
            '-show_entries','stream=width,height,nb_read_frames,r_frame_rate','-of','json',str(video)]))
        stream=probe['streams'][0]
        assert (stream['width'],stream['height'],stream['nb_read_frames'],stream['r_frame_rate'])==(len(columns)*576,436,'158','24/1')
        binding['products'][name]={'file':video.name,'sha256':sha(video),'probe':probe,'displayed_frame_sets':framesets}
    (args.out/'BINDING.json').write_text(json.dumps(binding,indent=2)+'\n')
    print(args.out)

if __name__=='__main__':main()
