"""CPU scientific viewing copies from pixel-verified RGB8 inputs."""
import argparse
import base64
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from compare import RGBReader, read, write, require, sha

FIXED = [0,12,24,36,48,60]
BOUNDARY = [16,17,18,33,34,35]
FONT = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
LABELS = {'RGB_target':'RGB 直接时间重排', 'RGB_roundtrip':'RGB 重排后再编码、解码',
          'latent_warp':'latent 时间重排后解码','anchor':'原坐标残差补偿（anchor）',
          'transport':'随时间重排的残差补偿（transport）'}
SETS = {'latent_transport':['RGB_target','latent_warp','transport'],
        'reencode_anchor':['RGB_target','RGB_roundtrip','anchor'],
        'reencode_transport':['RGB_target','RGB_roundtrip','transport']}


def pane(frames, columns, index, coords, valid, width=576):
    height=width*2//3
    canvas=Image.new('RGB',(width*3,height+52),'black');draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype(FONT,18 if width==576 else 13)
    small=ImageFont.truetype(FONT,14 if width==576 else 12)
    for j,key in enumerate(columns):
        image=Image.fromarray(frames[key]).resize((width,height),Image.Resampling.LANCZOS)
        canvas.paste(image,(width*j,0))
        draw.text((j*width+width//2,height+14),LABELS[key],font=font,fill='white',anchor='mm')
    line=f'{index/24:.3f} s | frame {index} | mapped source {coords["rgb_positions"][index]/24:.3f} s'
    line += ' | common valid' if valid[index] else ' | boundary / padding'
    draw.text((6,height+32),line,font=small,fill='white')
    return canvas


def main():
    p=argparse.ArgumentParser();p.add_argument('--verified',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();v=read(args.verified)
    require(v['passed'] is True and not args.out.exists(),'verified results and new output')
    args.out.mkdir(parents=True)
    ffmpeg=shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
    ffprobe=shutil.which('ffprobe') or '/opt/homebrew/bin/ffprobe'
    binding={'verified_sha256':sha(args.verified),'fixed_frames':FIXED,'boundary_frames':BOUNDARY,'videos':{},'images':{},
             'scope':v['scope'],'frame_alignment':'same original RGB frame, 24fps, all columns same scale'}
    for mapping in ['shift3','offline_mapping']:
        spec=v['maps'][mapping];names=list(LABELS)
        for name in names:require(sha(v['products'][mapping+'_'+name]['file'])==v['products'][mapping+'_'+name]['sha256'],'actual video hash')
        readers={n:RGBReader(v['products'][mapping+'_'+n]) for n in names}
        children={};sheets={key:{} for key in SETS}
        for key in SETS:
            path=args.out/(mapping+'_'+key+'.mp4')
            children[key]=subprocess.Popen([ffmpeg,'-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1728x436','-r','24',
                '-i','pipe:0','-frames:v','158','-an','-c:v','libx264','-threads','2','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(path)],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for i in range(158):
                frames={n:r.next() for n,r in readers.items()}
                for key,columns in SETS.items():
                    children[key].stdin.write(pane(frames,columns,i,spec['coordinates'],spec['masks']['common_valid147']).tobytes())
                    if i in FIXED or i in BOUNDARY:
                        sheets[key][i]=pane(frames,columns,i,spec['coordinates'],spec['masks']['common_valid147'],384)
            for r in readers.values():r.finish()
            for key,child in children.items():
                child.stdin.close();error=child.stderr.read().decode();require(child.wait()==0,error)
        finally:
            for r in readers.values():r.close()
            for child in children.values():
                if child.poll() is None:child.kill();child.wait()
                if not child.stdin.closed:child.stdin.close()
                child.stderr.close()
        for key,columns in SETS.items():
            stem=mapping+'_'+key;path=args.out/(stem+'.mp4')
            stream=json.loads(subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0','-count_frames',
                '-show_entries','stream=width,height,nb_read_frames,r_frame_rate','-of','json',str(path)]))['streams'][0]
            require((stream['width'],stream['height'],stream['nb_read_frames'],stream['r_frame_rate'])==(1728,436,'158','24/1'),'display geometry')
            binding['videos'][stem]={'file':path.name,'sha256':sha(path),'columns':columns,'probe':stream}
            for group,indices in [('six_times',FIXED),('block_boundaries',BOUNDARY)]:
                panel=sheets[key][indices[0]];sheet=Image.new('RGB',(panel.width,panel.height*len(indices)),'black')
                for row,i in enumerate(indices):sheet.paste(sheets[key][i],(0,row*panel.height))
                output=args.out/(stem+'_'+group+'.png');sheet.save(output)
                binding['images'][output.stem]={'file':output.name,'sha256':sha(output),'frames':indices,'columns':columns}
        print(json.dumps({'mapping':mapping,'videos':3,'sheets':6}),flush=True)
    write(args.out/'BINDING.json',binding)
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R70 残差补偿算子对照</title>',
           '<style>body{background:#111;color:#ddd;font:17px/1.6 system-ui;max-width:1500px;margin:32px auto;padding:0 20px}video,img{width:100%;height:auto}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #444;text-align:left}details{margin:20px 0}a{color:#8cf}</style>',
           '<h1>R70：时间重排与 VAE 残差补偿</h1><p>同一份 Native index 6 预测，比较直接 RGB 时间重排、latent 重排、RGB 重编码，以及两种已有的残差补偿方式。下表为统一 RGB8 误差，越小表示越接近对应的 RGB 重排目标。</p>',
           '<p>anchor = z + (e<sub>φ</sub> − e<sub>id</sub>)；transport = L<sub>φ</sub>(z) + (e<sub>φ</sub> − L<sub>φ</sub>(e<sub>id</sub>))。</p>',
           '<p>残差补偿沿用 <a href="https://arxiv.org/html/2504.08902v1#S4.SS1">LookingGlass</a> 与 <a href="https://arxiv.org/html/2607.08770v1">LongE2V</a> 的相关思路。本页检验 H3 的重排几何与重建误差。offline mapping 使用最终成片拟合的开发集映射。</p>']
    for mapping,title in [('shift3','固定提前 3 帧'),('offline_mapping','离线拟合的单调时间映射')]:
        parts.append('<h2>'+title+'</h2><table><tr><th>方法</th><th>共同有效帧</th><th>RGB8 MAE</th></tr>')
        for suffix in ['latent_warp','RGB_roundtrip','anchor','transport']:
            value=v['maps'][mapping]['methods'][mapping+'_'+suffix]['groups']['common_valid147']
            parts.append(f'<tr><td>{LABELS[suffix]}</td><td>{value["frames"]}</td><td>{value["normalized_rgb8_mae"]:.6f}</td></tr>')
        parts.append('</table>')
        for key in SETS:
            stem=mapping+'_'+key;video=args.out/(stem+'.mp4');image=args.out/(stem+'_six_times.png')
            parts.append('<h3>'+' / '.join(LABELS[n] for n in SETS[key])+'</h3>')
            parts.append('<video controls loop playsinline preload="metadata" src="data:video/mp4;base64,'+base64.b64encode(video.read_bytes()).decode()+'"></video>')
            parts.append('<details><summary>固定六时刻截图</summary><img src="data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode()+'"></details>')
    parts.append('<p>同帧、同速度、同尺寸显示。158 帧完整片长 6.583 秒；量化表使用各映射的共同有效区域。光度误差反映算子保真度，动作时间效果需另行测量。</p></html>')
    (args.out/'index.html').write_text('\n'.join(parts))
    print(args.out/'index.html')


if __name__=='__main__':main()
