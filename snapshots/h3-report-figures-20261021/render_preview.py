from pathlib import Path
import re,subprocess,sys
ROOT=Path(__file__).resolve().parent
for p in map(Path,sys.argv[1:]):
 s=p.read_text(); vb=re.search(r'viewBox="([^"]+)"',s).group(1).split();w,h=map(float,vb[2:]);side=int(max(w,h))
 start,end=s.index('<svg'),s.index('>')
 tag=s[start:end+1]
 for key,value in [('width',str(side)),('height',str(side)),('viewBox',f'0 0 {side} {side}')]:tag=re.sub(key+r'="[^"]+"',f'{key}="{value}"',tag)
 preview=ROOT/(p.stem+'-preview.svg');preview.write_text(tag+s[end+1:])
 result=subprocess.run(['qlmanage','-t','-s',str(side),'-o',str(ROOT),str(preview)],capture_output=True,text=True)
 if result.returncode:raise RuntimeError(result.stderr)
 print(str(preview)+'.png')
