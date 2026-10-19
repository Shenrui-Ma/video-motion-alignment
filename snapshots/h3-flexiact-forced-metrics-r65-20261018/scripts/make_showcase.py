"""Embed only completed comparison videos in a portable Chinese HTML file."""
import argparse,base64,html
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--video',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sections=[]
 for v in a.video:
  if not v.is_file() or v.stat().st_size==0:raise ValueError('actual completed video required: '+str(v))
  data=base64.b64encode(v.read_bytes()).decode()
  sections.append('<section><h2>'+html.escape(v.stem)+'</h2><video controls playsinline loop preload="metadata" src="data:video/mp4;base64,'+data+'"></video></section>')
 document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FlexiAct 动作对照</title><style>body{margin:0;background:#111;color:#eee;font:17px system-ui}main{max-width:2400px;margin:auto;padding:24px}h1{font-size:25px}h2{font-size:18px;font-weight:500}p{color:#bbb}section{margin:28px 0}video{display:block;width:100%;background:black;max-height:84vh}button{font:inherit}</style><main><h1>FlexiAct 动作对照</h1><p>从左到右：参考视频、编辑后视频、编辑＋时序引导后视频。各列展示同一物理时刻，可全屏查看。</p>'+''.join(sections)+'</main></html>'
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x') as f:f.write(document)
 print(a.output.resolve())
if __name__=='__main__':main()
