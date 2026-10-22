from pathlib import Path
import importlib.util, json, html, shutil, zipfile, gc, sys
sys.dont_write_bytecode = True
from PIL import Image, ImageChops
BASE=Path('/Users/researcher')
TASK=Path(__file__).resolve().parent
RAW=BASE/'Downloads/H3_四组完整原视频_Musk_Sam_20261015'
SHORT=BASE/'Downloads/H3_四组短动作对照_Musk_Sam_20261015'
OUT=BASE/'Downloads/H3_四组完整版横向对比_Musk_Sam_20261015'
MODULE=BASE/'DevProjects/h3-musk-bedside-pair-20261014/scripts/render_comparison.py'
spec=importlib.util.spec_from_file_location('previous_renderer',MODULE)
r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
OUT.mkdir(parents=True,exist_ok=True)
CASES=[('01_Musk_真人书记舞','01_Musk05',56,'Musk · 真人书记舞'),('02_Musk_床边舞','02_Musk07',61,'Musk · 床边舞'),('03_Sam_真人书记舞','03_Sam05',56,'Sam · 真人书记舞'),('04_Sam_床边舞','04_Sam07',61,'Sam · 床边舞')]
NAMES=['1_参考原视频.mp4','2_编辑后视频_未加权.mp4','3_编辑后视频_短时动作三倍加权.mp4']
records=[]
for folder,key,preview_frame,title in CASES:
    inputs=[RAW/folder/name for name in NAMES]
    sequences=[r.decode(path) for path in inputs]
    preview=r.compose(sequences,preview_frame)
    with Image.open(SHORT/f'{key}_preview.png') as reference:
        assert preview.size==reference.size
        assert ImageChops.difference(preview,reference.convert('RGB')).getbbox() is None, f'Existing short-preview mismatch: {key}'
    preview_name=f'{folder}_preview.png'
    preview.save(OUT/preview_name)
    rows=[r.compose(sequences,index) for index in range(141)]
    output=OUT/f'{folder}_完整版横向对比.mp4'
    info=r.encode(rows,output,24)
    # Decode all frames and verify presentation timestamps independently.
    timing=r.check_timestamps(output)
    records.append({'title':title,'video':output.name,'preview':preview_name,'preview_matches_existing_short_exactly':True,'source_frames_inclusive':[0,140],'inputs':[{'path':str(p),'sha256':r.fingerprint(p)} for p in inputs],**info,'timestamps':timing})
    del sequences,rows,preview
    gc.collect()
    print(json.dumps({'completed':key,**info},ensure_ascii=False),flush=True)
manifest={'status':'complete','videos':records,'caption_style':r.caption_metadata(),'audio':'Silent comparison derivatives, same as existing short versions.','alignment':'Same index for all columns; full 0–140 frames at original 24 fps, no retiming/interpolation; complete frames equally scaled.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
(OUT/'README.txt').write_text('四组完整版横向对比视频\n\n每个 MP4 均横向拼接三列：参考视频 / 编辑后视频（未加权） / 编辑后视频（短时动作三倍加权）。\n包含 Musk 真人书记舞、Musk 床边舞、Sam 真人书记舞、Sam 床边舞，共4个完整横向对比视频。\n每条141帧，24fps，5.875秒，1968×416；采用完整实验片段而非原网站长视频。\n延续短版的黑底中文底部标注；相同帧号并排，不插帧、不变速，不做每列独立的时间调整。展示视频静音。\n人物替换画面是AI编辑实验，不是真人跳舞记录。来源信息见CREDITS.txt。\n')
shutil.copy2(SHORT/'CREDITS.txt',OUT/'CREDITS.txt')
body='<h1>四组完整版横向对比</h1><p>完整141帧 · 24 fps · 5.875秒。三列：参考视频／未加权编辑／短时动作三倍加权编辑。</p>'
for row in records:
    body+=f'<section><h2>{html.escape(row["title"])}</h2><video controls preload="metadata" poster="{html.escape(row["preview"])}" src="{html.escape(row["video"])}"></video><p><a download href="{html.escape(row["video"])}">下载完整横向对比视频</a></p></section>'
(OUT/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>四组完整版横向对比</title><style>body{background:#000;color:#fff;font:16px system-ui;max-width:1800px;margin:auto;padding:24px}video{width:100%;display:block}a{color:#ddd}section{margin:32px 0}</style><body>'+body+'</body></html>')
files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='SHA256SUMS')
(OUT/'SHA256SUMS').write_text(''.join(f'{r.fingerprint(p)}  {p.name}\n' for p in files))
zip_path=OUT.with_suffix('.zip')
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for p in sorted(OUT.iterdir()):
        if p.is_file():z.write(p,p.relative_to(OUT.parent))
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
(TASK/'verification.json').write_text(json.dumps({'status':'pass','video_count':4,'frame_count_each':141,'duration_each':5.875,'preview_pixel_match':'all four exact matches to existing short version','zip_sha256':r.fingerprint(zip_path),'directory':str(OUT)},ensure_ascii=False,indent=2)+'\n')
print('COMPLETE: '+str(OUT),flush=True)
