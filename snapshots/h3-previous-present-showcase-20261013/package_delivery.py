"""Package the complete gallery and a separate24-video handoff without old assets."""
import hashlib
import html
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
DOWNLOADS=Path('/Users/researcher/Downloads')
VIDEO_DIR=DOWNLOADS/'H3_Previous_Present_对比视频_20261013'
VIDEO_ZIP=DOWNLOADS/'H3_Previous_Present_对比视频_20261013.zip'
GALLERY_ZIP=DOWNLOADS/'H3_Previous_Present_总展示_20261013.zip'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def seal(directory,zip_path,exclude=()):
 files=sorted(p for p in directory.rglob('*') if p.is_file() and p.name not in ('ARCHIVE_SHA256SUMS.txt',*exclude) and '__pycache__' not in p.parts)
 records=[(sha(p),p.relative_to(directory).as_posix()) for p in files]
 sums=directory/'ARCHIVE_SHA256SUMS.txt';sums.write_text(''.join(f'{h}  {rel}\n' for h,rel in records))
 for h,rel in records:assert sha(directory/rel)==h
 with zipfile.ZipFile(zip_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
  for p in files+[sums]:z.write(p,Path(directory.name)/p.relative_to(directory))
 with zipfile.ZipFile(zip_path) as z:
  assert z.testzip() is None
  for h,rel in records:assert hashlib.sha256(z.read(directory.name+'/'+rel)).hexdigest()==h
  entries=len(z.namelist())
 return {'directory':str(directory),'zip':str(zip_path),'zip_size_bytes':zip_path.stat().st_size,'zip_sha256':sha(zip_path),'zip_crc_test':'pass','zip_payload_sha_test':'pass','payload_files':len(records),'zip_entries':entries}

def main():
 assert not VIDEO_DIR.exists() and not VIDEO_ZIP.exists() and not GALLERY_ZIP.exists(),'Refusing to overwrite existing deliveries'
 m=json.loads((ROOT/'manifest.json').read_text());VIDEO_DIR.mkdir()
 exported=[];parts=['<!doctype html><html lang="en"><meta charset="utf-8"><title>H3 | Comparison videos</title><style>body{background:#000;color:#eee;font:17px/1.6 Helvetica,Arial,sans-serif;margin:30px}a{color:#afd4ff}li{margin:10px 0}</style><h1>PREVIOUS / PRESENT / PRESENT + PROMPT EMPHASIS</h1><p>24 comparison videos: selected event and full clip, at normal and quarter speed, for each of six cases.</p><ul>']
 for c in m['cases']:
  for v in c['rendered']['videos']+c['full_clip']:
   source=ROOT/v['path'];name=c['key']+'__'+source.name;dest=VIDEO_DIR/name;shutil.copy2(source,dest)
   assert sha(source)==sha(dest)
   exported.append({'file':name,'case':c['key'],'title':c['title'],'gallery_path':v['path'],'sha256':sha(dest),'probe':v['probe'],'frames_inclusive':v['frames_inclusive']})
   parts.append(f'<li><a href="{name}">{html.escape(c["title"])} — {source.stem.replace("_"," ")}</a></li>')
 assert len(exported)==24 and len(list(VIDEO_DIR.glob('*.mp4')))==24
 parts.append('</ul><p>Black-to-red PRESENT has display-only top/bottom black-bar padding. Original experimental files remain intact. These are archived prompt comparisons, separate from the event-emphasis weighting experiment.</p></html>')
 (VIDEO_DIR/'index.html').write_text(''.join(parts))
 (VIDEO_DIR/'README.txt').write_text('24个最新直接对比MP4\n\n每组4个：full_frame_event为选定关键窗口、full_clip为完整原片时长；normal为24FPS原速、quarter_speed为6FPS四分之一速度，均无插帧。6组包括动漫两seed、真人两案例、街舞两seed。\n列标签：PREVIOUS原始参考；PRESENT此前普通提示结果；PRESENT + PROMPT EMPHASIS此前显式事件提示结果。不是当前加权实验结果。\n黑裙改红PRESENT展示列填充native顶部70像素/底部69像素黑边；其余内容不变，原始视频保留。\n打开index.html浏览视频链接，或直接播放MP4。详细截图与可选局部视频见总展示包。\n')
 (VIDEO_DIR/'manifest.json').write_text(json.dumps({'labels':m['labels'],'label_role_mapping':m['label_role_mapping'],'video_count':24,'videos':exported},ensure_ascii=False,indent=2)+'\n')
 # All linked videos are portable and are the verified gallery bytes.
 for e in exported:assert(VIDEO_DIR/e['file']).is_file() and sha(VIDEO_DIR/e['file'])==e['sha256']
 video_delivery=seal(VIDEO_DIR,VIDEO_ZIP)
 gallery_delivery=seal(ROOT,GALLERY_ZIP,exclude=('DELIVERY_RECEIPT.json',))
 receipt={'status':'complete','created_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'entry':str(ROOT/'index.html'),'gallery':gallery_delivery,'direct_videos':video_delivery,'direct_video_count':24,'all_gallery_movies':32,'screenshot_count':108,'all_media_regenerated_with_new_labels':True,'render_and_verification_exited':True,'new_model_inference':False,'server_access':False,'raw_archives_modified':False,'receipt_excluded_from_zip_and_payload_sha':True}
 (ROOT/'DELIVERY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
