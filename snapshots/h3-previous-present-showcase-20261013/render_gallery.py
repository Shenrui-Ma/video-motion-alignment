"""Regenerate archived comparisons with PREVIOUS/PRESENT display labels."""
import hashlib
import html
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parent
OLD=Path('/Users/researcher/DevProjects/h3-black-english-showcase-all-20261013')
FF='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
W,H,TOP=656,368,48
LABELS=['PREVIOUS','PRESENT','PRESENT + PROMPT EMPHASIS']
FONT='/System/Library/Fonts/Helvetica.ttc'
MAIN=ImageFont.truetype(FONT,20);TIME=ImageFont.truetype(FONT,16);SMALL=ImageFont.truetype(FONT,12)
BAR_TOP,BAR_BOTTOM=70,69

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def probe(p):
 return json.loads(subprocess.check_output([FP,'-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration','-of','json',str(p)]))['streams'][0]

def fit(im):
 im=ImageOps.contain(im,(W,H),Image.Resampling.BICUBIC)
 canvas=Image.new('RGB',(W,H),'black');canvas.paste(im,((W-im.width)//2,(H-im.height)//2));return canvas

def decode(p,n,detail=None,overlay=False):
 """Mask native RGB only when requested, then use the shared display resize/crop."""
 pr=probe(p);width,height=pr['width'],pr['height'];assert(width,height)==(1312,736)
 proc=subprocess.Popen([FF,'-v','error','-threads','2','-i',str(p),'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
 full=[];details=[];audit=[];row_bytes=width*3;size=row_bytes*height
 try:
  for i in range(n):
   raw=proc.stdout.read(size);assert len(raw)==size,(str(p),i,len(raw))
   shown=bytearray(raw)
   if overlay:
    shown[:BAR_TOP*row_bytes]=b'\0'*(BAR_TOP*row_bytes)
    shown[(height-BAR_BOTTOM)*row_bytes:]=b'\0'*(BAR_BOTTOM*row_bytes)
   shown=bytes(shown)
   outside_before=raw[BAR_TOP*row_bytes:(height-BAR_BOTTOM)*row_bytes]
   outside_after=shown[BAR_TOP*row_bytes:(height-BAR_BOTTOM)*row_bytes]
   assert outside_before==outside_after
   if not overlay:assert raw==shown
   audit.append({'frame':i,'native_decoded_sha256':hashlib.sha256(raw).hexdigest(),
                 'display_native_sha256':hashlib.sha256(shown).hexdigest(),
                 'outside_overlay_before_sha256':hashlib.sha256(outside_before).hexdigest(),
                 'outside_overlay_after_sha256':hashlib.sha256(outside_after).hexdigest(),
                 'outside_overlay_exact_equal':True,'whole_native_exact_equal':raw==shown})
   im=Image.frombytes('RGB',(width,height),shown);full.append(fit(im))
   if detail:
    x,y,w,h=detail;details.append(fit(im.crop((x,y,x+w,y+h))))
  assert not proc.stdout.read(1),'unexpected extra frame'
  assert proc.wait()==0
 finally:
  proc.stdout.close()
  if proc.poll() is None:proc.kill();proc.wait()
 return full,details,audit

def row(seqs,i,detail=False):
 im=Image.new('RGB',(W*3,H+TOP),'black');d=ImageDraw.Draw(im)
 for col,label in enumerate(LABELS):
  x=col*W;im.paste(seqs[col][i],(x,TOP))
  d.text((x+10,3),label,font=MAIN,fill='white')
  d.text((x+10,27),f'frame {i:03d} | {i/24:.3f}s',font=TIME,fill='white')
  if detail:d.text((x+W-96,29),'DETAIL CROP',font=SMALL,fill='white')
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
  p=folder/f'{prefix}_event_{suffix}.mp4';pr=encode(rows,p,fps)
  videos.append({'path':p.relative_to(ROOT).as_posix(),'probe':pr,'frames_inclusive':[lo,hi]})
 images=[]
 for ids in c['screens']:
  im=Image.new('RGB',(W*3,(H+TOP)*len(ids)),'black')
  for j,i in enumerate(ids):im.paste(row(seqs,i,detail),(0,j*(H+TOP)))
  p=folder/f'{prefix}_frames_{ids[0]:03d}-{ids[-1]:03d}.jpg';im.save(p,quality=97,subsampling=0)
  images.append({'path':p.relative_to(ROOT).as_posix(),'frames':ids})
 pages=[]
 for start in range(0,len(rows),3):
  part=rows[start:start+3];im=Image.new('RGB',(W*3,(H+TOP)*len(part)),'black')
  for j,v in enumerate(part):im.paste(v,(0,j*(H+TOP)))
  p=folder/f'{prefix}_dense_{lo+start:03d}-{lo+start+len(part)-1:03d}.jpg';im.save(p,quality=95,subsampling=0)
  pages.append({'path':p.relative_to(ROOT).as_posix(),'frames':list(range(lo+start,lo+start+len(part)))})
 return {'videos':videos,'key_screenshots':images,'dense_pages':pages,'detail_crop':c['detail'] if detail else None}

def build_html(m):
 parts=['''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>H3 | Previous and present</title><style>body{background:#000;color:#eee;margin:0;font:17px/1.6 Helvetica,Arial,sans-serif}main{max-width:1500px;margin:auto;padding:26px}h1{font-size:29px}h2{font-size:23px}section{border-top:1px solid #444;margin:30px 0;padding:18px 0}video,img{width:100%;height:auto;background:#000}a{color:#a4cef8;margin-right:14px}p{color:#ccc}summary{cursor:pointer;padding:10px 0;color:#ddd}.pages{display:flex;flex-wrap:wrap;gap:10px}small{color:#aaa}</style><main><h1>H3 | Previous and present</h1><p>PREVIOUS &nbsp;|&nbsp; PRESENT &nbsp;|&nbsp; PRESENT + PROMPT EMPHASIS</p><p>PREVIOUS: original reference. PRESENT: general motion-preservation prompt. PRESENT + PROMPT EMPHASIS: explicit event and timing prompt.</p><p>Previously archived prompt comparisons; separate from the ongoing event-emphasis weighting experiment. Matched frame indices; quarter speed uses the same frames at 6 FPS.</p><nav>''']
 for c in m['cases']:parts.append(f'<a href="#{c["key"]}">{html.escape(c["title"])}</a>')
 parts.append('</nav>')
 for c in m['cases']:
  r=c['rendered'];lo,hi=c['bounds']
  parts.append(f'<section id="{c["key"]}"><h2>{html.escape(c["title"])}</h2><p>{html.escape(c["note"])}</p><small>Selected frames {lo}-{hi} inclusive | original timestamps | preview at 0.25x</small><video controls preload="metadata" src="{r["videos"][1]["path"]}"></video><p><a href="{r["videos"][0]["path"]}">Normal speed</a><a href="{r["videos"][1]["path"]}">Quarter speed</a></p>')
  for im in r['key_screenshots']:parts.append(f'<a href="{im["path"]}"><img loading="lazy" src="{im["path"]}" alt="Three-column frames {im["frames"]}"></a>')
  parts.append('<details><summary>Every frame in the selected window</summary><div class="pages">')
  for im in r['dense_pages']:parts.append(f'<a target="_blank" href="{im["path"]}">Frames {im["frames"][0]}-{im["frames"][-1]}</a>')
  parts.append('</div></details>')
  if c['detail_rendered']:
   d=c['detail_rendered'];parts.append(f'<details><summary>Optional detail crop</summary><video controls preload="none" src="{d["videos"][1]["path"]}"></video>')
   for im in d['key_screenshots']:parts.append(f'<a href="{im["path"]}"><img loading="lazy" src="{im["path"]}" alt="Fixed detail crop"></a>')
   parts.append('</details>')
  parts.append(f'<details><summary>Full clip | {c["frames"]} frames | context retained</summary><video controls preload="none" src="{c["full_clip"][1]["path"]}"></video><p><a href="{c["full_clip"][0]["path"]}">Full clip normal speed</a><a href="{c["full_clip"][1]["path"]}">Full clip quarter speed</a></p></details></section>')
 parts.append('<footer><small>Display-only black-bar padding on Black to red / PRESENT: 70 pixels at the top and 69 at the bottom of the native frame. Original files remain intact. Selected-window mismatch alone does not establish whole-clip action omission; full clips and supplementary seeds are included.</small></footer></main></html>')
 (ROOT/'index.html').write_text(''.join(parts))

def main():
 old=json.loads((OLD/'manifest.json').read_text());records=[];display_audits=[]
 for previous in old['cases']:
  c={k:previous[k] for k in ['key','case','seed','archive','frames','title','bounds','screens','detail','note']}
  # Replace shorthand in visible prose, while retaining precise archive role mapping in metadata.
  c['note']=c['note'].replace('A/B','the edited outputs').replace('both outputs','both edited outputs').replace(' B ',' the prompt-emphasis output ').replace(' A ',' the standard output ')
  folder=ROOT/c['key'];folder.mkdir(exist_ok=True)
  paths=[Path(i['path']) for i in previous['inputs']]
  av=json.loads((Path(c['archive'])/'analysis/archive_validation.json').read_text())
  expected={x['output_file']:x['output_sha256'] for x in av['formal_runs']}
  for j,p in enumerate(paths):
   assert sha(p)==previous['inputs'][j]['sha256']
   if j:assert sha(p)==expected[p.relative_to(c['archive']).as_posix()]
   pr=probe(p);assert int(pr['nb_read_frames'])==c['frames'] and pr['avg_frame_rate']=='24/1'
  seqs=[];detailseqs=[]
  for col,p in enumerate(paths):
   overlay=c['case']=='05_real_megumi_v' and c['seed']==1 and col==1
   full,detail,audit=decode(p,c['frames'],c['detail'],overlay)
   seqs.append(full);detailseqs.append(detail)
   if c['case']=='05_real_megumi_v':display_audits.append({'case':c['key'],'column':LABELS[col],'path':str(p),'overlay':overlay,'frames':audit})
  rendered=render_set(c,seqs,folder)
  full=[]
  for fps,suffix in [(24,'normal'),(6,'quarter_speed')]:
   p=folder/f'full_clip_{suffix}.mp4';pr=encode([row(seqs,i) for i in range(c['frames'])],p,fps)
   full.append({'path':p.relative_to(ROOT).as_posix(),'probe':pr,'frames_inclusive':[0,c['frames']-1]})
  detail=render_set(c,detailseqs,folder,True) if c['detail'] else None
  record={**c,'inputs':[{'path':str(p),'sha256':sha(p),'display_label':LABELS[j],'archive_role':['source','A','B'][j]} for j,p in enumerate(paths)],'rendered':rendered,'detail_rendered':detail,'full_clip':full,'new_model_inference':False}
  if c['case']=='05_real_megumi_v':record['display_adjustment']={'column':'PRESENT','type':'native RGB black overlay','top_rows_half_open':[0,70],'bottom_rows_half_open':[667,736],'native_geometry':[1312,736],'resize_for_adjustment':False,'common_display_panel':[656,368],'detail_crop_intersects_overlay':False}
  records.append(record);print('DONE',c['key'],flush=True)
 manifest={'style':'black background, English white labels; label and frame/time on two lines','labels':LABELS,'label_role_mapping':dict(zip(LABELS,['original source video','previous generic-prompt A result','previous explicit-event-prompt B result'])),'panel_pixels':[W,H+TOP],'frame_numbering':'zero-based original24FPS timestamps','no_interpolation':True,'no_per_column_time_alignment':True,'new_model_inference':False,'provenance_note':'All results are prior prompt comparisons, not the ongoing event-emphasis weighting experiment.','cases':records}
 (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 (ROOT/'DISPLAY_PIXEL_AUDIT.json').write_text(json.dumps({'stage':'native decoded RGB before common display resize','overlay_region':{'top':[0,70],'bottom':[667,736]},'source_and_prompt_emphasis_unchanged':True,'standard_output_outside_overlay_unchanged':True,'cases':display_audits},indent=2)+'\n')
 build_html(manifest)
 (ROOT/'README.txt').write_text('H3 Previous / Present 总展示\n\n所有截图、关键片段和完整片段均使用黑底英文标签：PREVIOUS=原始参考；PRESENT=此前普通动作保留提示A；PRESENT + PROMPT EMPHASIS=此前显式事件提示B。均非当前事件加权实验结果。\n\n6组：动漫seed2、黑裙改红seed1、白衣改蓝seed1、街舞seed2；补充动漫seed1与街舞seed1。关键截图和连续窗口与上一版保持一致。每组保留完整原时长、原帧数的正常与四分之一速度对比。慢放为同帧6FPS，无插帧或分别调整各列时间。\n\n黑裙改红PRESENT列仅在展示衍生帧上填黑native顶部70像素、底部69像素；不缩放或拉伸来补边。其余内容像素在共同展示缩放前逐帧完全相同。PREVIOUS与提示强化结果不加遮挡，原始水印和已有黑边保留。原始视频只读未改。DETAIL裁切由同一显示帧导出；该案例裁切y120–560不覆盖新黑边。所有面板统一缩小为656×368展示。\n\n动漫目标是早期39–44帧短眼旁动作，41–42帧最清楚；后置长眼旁动作54–68帧是独立事件。真人窗口说明对应时刻姿态不一致；街舞说明动作内部相位/姿态错位。全时长上下文保留。\n')

if __name__=='__main__':main()
