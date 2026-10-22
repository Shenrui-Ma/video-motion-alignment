#!/usr/bin/env python3
"""Export self-contained research reports to an offline, deduplicated media folder.

Original HTML is read-only. Uses streaming base64 extraction, stable content hashes,
and redaction of machine-specific paths/identifiers in the exported HTML only.
"""
from __future__ import annotations
import argparse,base64,hashlib,io,json,mmap,os,re,shutil,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAX_BLOB=95*1024*1024
EVENT=re.compile(rb'data:(?P<mime>[A-Za-z0-9.+/-]+);base64,|(?P<script><script\b[^>]*\btype=[\"\']application/octet-stream[\"\'][^>]*>)',re.I)
PAYLOAD=re.compile(rb'[A-Za-z0-9+/=\r\n]+')
EXT={'video/mp4':'.mp4','image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','image/gif':'.gif','image/svg+xml':'.svg','audio/mpeg':'.mp3','audio/wav':'.wav','video/webm':'.webm','font/woff2':'.woff2'}
SECRET_PATTERNS=[re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'),re.compile(r'\bgithub_pat_[A-Za-z0-9_]{30,}\b'),re.compile(r'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{30,}\b'),re.compile(r'https?://[^\s/:@]+:[^\s/@]+@')]
ASSET_URL="function assetURL(id){return 'data:'+DATA.asset_types[id]+';base64,'+$('asset_'+id).textContent;}"
ASSET_URL_EXTERNAL="function assetURL(id){return $('asset_'+id).textContent.trim();}"

def file_sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()

def atom_write(p,data):
 p.parent.mkdir(parents=True,exist_ok=True); t=p.with_name(p.name+'.tmp');t.write_bytes(data);t.replace(p)

def redact(text):
 counts={}
 def sub(name,pattern,replacement):
  nonlocal text
  text,n=re.subn(pattern,replacement,text);counts[name]=n
 # Preserve all scientific numeric values; redact full paths / concrete machines.
 sub('absolute_user_paths',r'(?:file://)?/(?:Users/[^/\s"\'<>]+|home/(?:shenrui\.ma|mashenrui)|data\d*/(?:shenrui\.ma|mashenrui))[^"\'<>\r\n]*','[local-path]')
 sub('encoded_user_paths',r'(?:file%3A%2F%2F)?%2FUsers%2F[^\s"\'<>]+','[local-path]')
 sub('ssh_aliases',r'\bCASIA_[A-Za-z0-9_.-]+','[server]')
 sub('gpu_uuids',r'\bGPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b','[GPU]')
 def ip(m):
  return '[server-address]' if all(int(n)<=255 for n in m.group().split('.')) else m.group()
 sub('ip_addresses',r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',ip)
 for pattern in SECRET_PATTERNS:
  if pattern.search(text):raise ValueError('Potential credential/private key found; export stopped without printing it')
 return text,counts

def extract_asset(mm,start,end,mime,out):
 h=hashlib.sha256();size=0;carry=b''
 fd,name=tempfile.mkstemp(prefix='.asset-',dir=out/'assets');temp=Path(name)
 try:
  with os.fdopen(fd,'wb') as f:
   for pos in range(start,end,1024*1024):
    chunk=carry+re.sub(rb'\s+',b'',mm[pos:min(pos+1024*1024,end)])
    usable=(len(chunk)//4)*4;part=chunk[:usable];carry=chunk[usable:]
    if part:
     decoded=base64.b64decode(part,validate=True);h.update(decoded);f.write(decoded);size+=len(decoded)
   if carry:raise ValueError('Invalid base64 alignment')
  digest=h.hexdigest(); ext=EXT.get(mime.lower(),'.bin');matches=list((out/'assets').glob(digest+'.*'));target=matches[0] if matches else out/'assets'/(digest+ext)
  if size>MAX_BLOB:raise ValueError(f'Asset exceeds 95MiB limit ({size} bytes); no large Git blob written')
  if target.exists():
   if target.stat().st_size!=size or file_sha(target)!=digest:raise ValueError('Existing asset integrity mismatch')
   temp.unlink()
  else:temp.replace(target)
  if file_sha(target)!=digest:raise ValueError('Written asset SHA mismatch')
  return {'path':target.relative_to(out).as_posix(),'sha256':digest,'bytes':size,'mime':mime}
 finally:
  temp.unlink(missing_ok=True)

def export_one(src,out):
 before=src.stat();source_hash=file_sha(src);references=[];parts=io.BytesIO();script_count=0
 with src.open('rb') as f:
  mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  types_match=re.search(rb'"asset_types"\s*:\s*(\{[^}]+\})',mm)
  types=json.loads(types_match.group(1)) if types_match else {}
  pos=0
  while (match:=EVENT.search(mm,pos)):
   parts.write(mm[pos:match.start()])
   if match.group('script'):
    opened=match.group('script');ident=re.search(rb'\bid=[\"\']asset_([^\"\']+)[\"\']',opened)
    if not ident:raise ValueError('Unrecognized media script id')
    close=mm.find(b'</script>',match.end())
    if close<0:raise ValueError('Unterminated media script')
    aid=ident.group(1).decode();mime=types.get(aid,'application/octet-stream')
    asset=extract_asset(mm,match.end(),close,mime,out);parts.write(opened+asset['path'].encode()+b'</script>');pos=close+9;script_count+=1;kind='script'
   else:
    payload=PAYLOAD.match(mm,match.end())
    if not payload:raise ValueError('Empty media data URL')
    mime=match.group('mime').decode();asset=extract_asset(mm,payload.start(),payload.end(),mime,out);parts.write(asset['path'].encode());pos=payload.end();kind='data_url'
   references.append({**asset,'kind':kind})
  parts.write(mm[pos:]);mm.close()
 text=parts.getvalue().decode('utf-8')
 if script_count:
  if text.count(ASSET_URL)!=1:raise ValueError('Historical assetURL implementation changed; inspect before export')
  text=text.replace(ASSET_URL,ASSET_URL_EXTERNAL)
 text,redactions=redact(text)
 if re.search(r'data:[A-Za-z0-9.+/-]+;base64,[A-Za-z0-9+/=]{100}',text):raise ValueError('Embedded base64 media remains')
 after=src.stat()
 if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or file_sha(src)!=source_hash:raise ValueError('Source changed during export; retry after editing finishes')
 data=text.encode();assert len(data)<MAX_BLOB;target=out/src.name;atom_write(target,data)
 for a in references:
  if not (out/a['path']).is_file():raise ValueError('Missing relative media')
 return {'file':src.name,'source_sha256':source_hash,'source_bytes':before.st_size,'export_sha256':hashlib.sha256(data).hexdigest(),'export_bytes':len(data),'asset_references':references,'script_media_count':script_count,'redactions':redactions}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--exclude',action='append',default=[]);args=parser.parse_args()
 reports=ROOT/'reports';out=reports/'cloud';(out/'assets').mkdir(parents=True,exist_ok=True)
 previous={}
 if (out/'manifest.json').exists():previous={x['file']:x for x in json.loads((out/'manifest.json').read_text())['reports']}
 sources=sorted(p for p in reports.glob('*.html') if p.name not in args.exclude);records=[];by_source={}
 for src in sources:
  source_hash=file_sha(src);prior=previous.get(src.name)
  if prior and prior['source_sha256']==source_hash and (out/src.name).exists() and file_sha(out/src.name)==prior['export_sha256'] and all((out/a['path']).exists() and file_sha(out/a['path'])==a['sha256'] for a in prior['asset_references']):
   record=prior
  elif source_hash in by_source:
   other=by_source[source_hash];atom_write(out/src.name,(out/other['file']).read_bytes());record={**other,'file':src.name}
  else:record=export_one(src,out)
  by_source[source_hash]=record;records.append(record);print(src.name,record['source_bytes'],'->',record['export_bytes'],'media',len(record['asset_references']),flush=True)
 assets={a['path']:a for x in records for a in x['asset_references']};total=sum(a['bytes'] for a in assets.values())
 manifest={'format':'offline-report-media-v1','reports':records,'unique_assets':list(assets.values()),'counts':{'reports':len(records),'unique_assets':len(assets),'media_references':sum(len(x['asset_references']) for x in records),'unique_media_bytes':total,'largest_asset_bytes':max((a['bytes'] for a in assets.values()),default=0)},'security':'Machine paths, server IP/SSH aliases and GPU UUIDs redacted from HTML; credential/private-key patterns checked. Original reports and media unchanged.'}
 atom_write(out/'manifest.json',(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
 readme='''# 离线研究展示\n\n下载整个 `cloud` 文件夹，保持 HTML 与 `assets` 的相对位置，在浏览器中打开任一 HTML 即可查看。只下载一个 HTML 时，图片和视频不会随它一起下载。\n\n这些网页是本地单文件报告的媒体分离副本。相同媒体按 SHA-256 去重，保留原始媒体字节；原始报告保持原样。服务器标识与本地绝对路径已在此副本中隐藏。\n\n`manifest.json` 记录每份原始报告、导出网页和所有媒体的 SHA-256。可运行 `python3 tools/export_reports.py` 增量更新。\n\n## 报告\n\n'''+''.join('- ['+x['file']+']('+x['file'].replace(' ','%20')+')\n' for x in records)
 atom_write(out/'README.md',readme.encode())
 print(json.dumps(manifest['counts'],ensure_ascii=False))
if __name__=='__main__':main()
