"""Render the user's original black/English three-column evidence layout."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
SWITCH=Path('/Users/researcher/DevProjects/h3-short-event-switching-20261013')
BREAK=Path('/Users/researcher/DevProjects/h3-fast-motion-followup-20261013')
FF='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
W,H,TOP=656,368,48
FONT=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',20)
LABELS=['SOURCE','A: appearance edit','B: explicit event']
CASES=[
 dict(key='01_black_to_red',case='05_real_megumi_v',seed=1,archive=SWITCH,frames=141,
      title='Black to red | seed 1',bounds=[46,64],screens=[[55,56,57]],detail=[480,120,560,440],
      note='At the source event time, the source hand is near the eye while A/B show a lower hand position.'),
 dict(key='02_white_to_blue',case='07_real_ary_v',seed=1,archive=SWITCH,frames=141,
      title='White to blue | seed 1',bounds=[50,69],screens=[[60,61,62]],detail=[440,0,560,440],
      note='At the source event time, the source hand is near the upper face while A/B are raising their arms.'),
 dict(key='03_breakdance_seed2',case='04_fast_motion',seed=2,archive=BREAK,frames=107,
      title='Breakdance | seed 2',bounds=[42,68],screens=[[48,49,50],[60,61,62]],detail=None,
      note='Source and A/B show opposing body orientations within the second leg-sweep cycle. This is phase/pose mismatch.'),
 dict(key='04_breakdance_seed1_supplement',case='04_fast_motion',seed=1,archive=BREAK,frames=107,
      title='Breakdance | seed 1 | supplementary',bounds=[42,68],screens=[[48,49,50],[60,61,62]],detail=None,
      note='At the same location, A is mismatched while B is closer to the source. Prompt emphasis can help in this seed.'),
]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def probe(p):
 return json.loads(subprocess.check_output([FP,'-v','error','-count_frames','-select_streams','v:0',
  '-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration','-of','json',str(p)]))['streams'][0]


def decode(p,n,crop=None):
 filters=[]
 if crop:
  x,y,w,h=crop;filters.append(f'crop={w}:{h}:{x}:{y}')
 filters+=['scale=656:368:force_original_aspect_ratio=decrease','pad=656:368:(ow-iw)/2:(oh-ih)/2:black']
 raw=subprocess.check_output([FF,'-v','error','-threads','2','-i',str(p),'-filter_threads','1',
  '-vf',','.join(filters),'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'])
 size=W*H*3;assert len(raw)==n*size,(p,len(raw),n)
 return [Image.frombytes('RGB',(W,H),raw[i*size:(i+1)*size]) for i in range(n)]


def row(seqs,i,detail=False):
 im=Image.new('RGB',(W*3,H+TOP),'black');d=ImageDraw.Draw(im)
 for col,label in enumerate(LABELS):
  x=col*W;im.paste(seqs[col][i],(x,TOP));d.text((x+10,5),f'{label} | frame {i:03d} | {i/24:.3f}s',font=FONT,fill='white')
  if detail:d.text((x+10,27),'DETAIL CROP',font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',14),fill='white')
 return im


def encode(rows,p,fps):
 proc=subprocess.Popen([FF,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W*3}x{H+TOP}',
  '-r',str(fps),'-i','-','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(p)],stdin=subprocess.PIPE)
 try:
  for im in rows:proc.stdin.write(im.tobytes())
  proc.stdin.close();assert proc.wait()==0
 finally:
  if proc.poll() is None:proc.kill();proc.wait()
 pr=probe(p);assert int(pr['nb_read_frames'])==len(rows) and pr['avg_frame_rate']==f'{fps}/1'
 return pr


def render_set(c,seqs,folder,detail=False):
 prefix='detail' if detail else 'full_frame';lo,hi=c['bounds'];rows=[row(seqs,i,detail) for i in range(lo,hi+1)]
 videos=[]
 for fps,suffix in [(24,'normal'),(6,'quarter_speed')]:
  p=folder/f'{prefix}_event_{suffix}.mp4';pr=encode(rows,p,fps);videos.append({'path':p.relative_to(ROOT).as_posix(),'probe':pr})
 images=[]
 for ids in c['screens']:
  im=Image.new('RGB',(W*3,(H+TOP)*len(ids)),'black')
  for j,i in enumerate(ids):im.paste(row(seqs,i,detail),(0,j*(H+TOP)))
  p=folder/f'{prefix}_frames_{ids[0]:03d}-{ids[-1]:03d}.jpg';im.save(p,quality=97,subsampling=0)
  images.append({'path':p.relative_to(ROOT).as_posix(),'frames':ids})
 # Every frame in the selected short interval, three rows per screenshot page.
 pages=[]
 for start in range(0,len(rows),3):
  part=rows[start:start+3];im=Image.new('RGB',(W*3,(H+TOP)*len(part)),'black')
  for j,v in enumerate(part):im.paste(v,(0,j*(H+TOP)))
  p=folder/f'{prefix}_dense_{lo+start:03d}-{lo+start+len(part)-1:03d}.jpg';im.save(p,quality=95,subsampling=0)
  pages.append({'path':p.relative_to(ROOT).as_posix(),'frames':list(range(lo+start,lo+start+len(part)))})
 return {'videos':videos,'key_screenshots':images,'dense_pages':pages,'detail_crop':c['detail'] if detail else None}


def main():
 records=[]
 for c in CASES:
  folder=ROOT/c['key'];folder.mkdir(exist_ok=True)
  paths=[c['archive']/'inputs'/f"{c['case']}.mp4"]+[c['archive']/'outputs'/f"{c['case']}_{arm}_s{c['seed']}_00001_.mp4" for arm in ['a','b']]
  av=json.loads((c['archive']/'analysis/archive_validation.json').read_text())
  expected={x['output_file']:x['output_sha256'] for x in av['formal_runs']}
  for p in paths[1:]:assert sha(p)==expected[p.relative_to(c['archive']).as_posix()]
  for p in paths:
   pr=probe(p);assert int(pr['nb_read_frames'])==c['frames'] and pr['avg_frame_rate']=='24/1'
  seqs=[decode(p,c['frames']) for p in paths];rendered=render_set(c,seqs,folder)
  full=[]
  for fps,suffix in [(24,'normal'),(6,'quarter_speed')]:
   p=folder/f'full_clip_{suffix}.mp4';pr=encode([row(seqs,i) for i in range(c['frames'])],p,fps);full.append({'path':p.relative_to(ROOT).as_posix(),'probe':pr})
  detail=None
  if c['detail']:detail=render_set(c,[decode(p,c['frames'],c['detail']) for p in paths],folder,True)
  records.append({**{k:str(v) if isinstance(v,Path) else v for k,v in c.items()},'inputs':[{'path':str(p),'sha256':sha(p)}for p in paths],'rendered':rendered,'detail_rendered':detail,'full_clip':full})
  print('DONE',c['key'],flush=True)
 manifest={'style':'original black background, English white labels, three same-time columns','labels':LABELS,
  'panel_pixels':[W,H+TOP],'frame_numbering':'zero-based, original24FPS timestamp','no_interpolation':True,
  'no_per_column_time_alignment':True,'new_model_inference':False,'cases':records}
 (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 build_html(manifest)
 (ROOT/'README.txt').write_text('黑底英文三列展示版\n\nindex.html：主展示为黑裙改红、白衣改蓝、街舞seed2；街舞seed1作为补充。\n全部截图/视频沿用SOURCE / A: appearance edit / B: explicit event，黑底白字、同帧同时间，不再使用白底中文样式。\nfull_frame_*保留全画面；detail_*仅两个人物案例的固定局部裁切（画面标DETAIL CROP）；full_clip_*保留完整原时长上下文。*_dense_*是短窗口每一帧，三行一页。\n黑裙改红：f55–57；白衣改蓝：f60–62；街舞：f48–50与f60–62。\n慢放为同帧以6FPS播放，无插帧、无独立时间配准。真人只说明对应时刻手脸姿态不一致，不凭短片断定整段遗漏；街舞说明环扫内部姿态/相位不保真。\n未生成新推理结果，原封存文件只读。\n')


def build_html(m):
 parts=['''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>H3 | Same-time motion comparisons</title><style>body{background:#000;color:#eee;margin:0;font:17px/1.6 Helvetica,Arial,sans-serif}main{max-width:1500px;margin:auto;padding:26px}h1{font-size:29px}h2{font-size:23px}section{border-top:1px solid #444;margin:30px 0;padding:18px 0}video,img{width:100%;height:auto;background:#000}a{color:#a4cef8;margin-right:14px}p{color:#ccc}summary{cursor:pointer;padding:10px 0;color:#ddd}.pages{display:flex;flex-wrap:wrap;gap:10px}small{color:#aaa}</style><main><h1>H3 | Same-time motion comparisons</h1><p>SOURCE &nbsp;|&nbsp; A: appearance edit &nbsp;|&nbsp; B: explicit event</p><p>Black background / English labels / matched frame indices. Quarter speed uses the same frames at 6 FPS, without interpolation.</p>''']
 for c in m['cases']:
  r=c['rendered'];lo,hi=c['bounds']
  parts.append(f'<section id="{c["key"]}"><h2>{c["title"]}</h2><p>{c["note"]}</p><small>Selected frames {lo}–{hi} inclusive | original timestamps shown in the panels | preview at 0.25x</small><video controls preload="metadata" src="{r["videos"][1]["path"]}"></video><p><a href="{r["videos"][0]["path"]}">Normal speed</a><a href="{r["videos"][1]["path"]}">Quarter speed</a></p>')
  for im in r['key_screenshots']:parts.append(f'<a href="{im["path"]}"><img loading="lazy" src="{im["path"]}" alt="Three-column frames {im["frames"]}"></a>')
  parts.append('<details><summary>Every frame in the selected window</summary><div class="pages">')
  for im in r['dense_pages']:parts.append(f'<a target="_blank" href="{im["path"]}">Frames {im["frames"][0]}–{im["frames"][-1]}</a>')
  parts.append('</div></details>')
  if c['detail_rendered']:
   d=c['detail_rendered'];parts.append(f'<details><summary>Optional detail crop | same black / English layout</summary><video controls preload="none" src="{d["videos"][1]["path"]}"></video>')
   for im in d['key_screenshots']:parts.append(f'<a href="{im["path"]}"><img loading="lazy" src="{im["path"]}" alt="Fixed detail crop"></a>')
   parts.append('</details>')
  parts.append(f'<details><summary>Full clip | {c["frames"]} frames | context retained</summary><video controls preload="none" src="{c["full_clip"][1]["path"]}"></video><p><a href="{c["full_clip"][0]["path"]}">Full clip normal speed</a><a href="{c["full_clip"][1]["path"]}">Full clip quarter speed</a></p></details></section>')
 parts.append('<small>Selected-window mismatches do not by themselves establish whole-clip action omission. Breakdance is a phase/pose example within a large movement. Full sequences and both breakdance seeds remain available.</small></main></html>')
 (ROOT/'index.html').write_text(''.join(parts))


if __name__=='__main__':main()
