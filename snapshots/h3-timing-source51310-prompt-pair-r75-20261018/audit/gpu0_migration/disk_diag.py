from pathlib import Path
import os,subprocess,json,time
uid=os.getuid(); home=Path.home()
owned=[]
for e in Path('/tmp').iterdir():
 try:
  s=e.lstat()
  if s.st_uid==uid and not e.is_symlink():owned.append(str(e))
 except OSError:pass
cache=[]
for parent in [home/'.cache',home/'.local/share',home/'.triton',home/'.nv']:
 if parent.is_dir():
  cache.extend(str(p) for p in parent.iterdir() if not p.is_symlink() and p.stat().st_uid==uid)
rows=[]
for group in [owned,cache]:
 if not group:continue
 try:
  p=subprocess.run(['du','-x','-s','-B1','--',*group],capture_output=True,text=True,timeout=50)
  for line in p.stdout.splitlines():
   a,_,b=line.partition('\t')
   if a.isdigit():rows.append({'path':b,'allocated_bytes':int(a)})
  if p.stderr:rows.append({'du_stderr':p.stderr[:3000]})
 except subprocess.TimeoutExpired as exc:rows.append({'timeout':True,'partial_stdout':str(exc.stdout)[:3000]})
processes=[]
for d in Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:
  if d.stat().st_uid!=uid:continue
  cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  refs=[]
  for fd in (d/'fd').iterdir():
   try:
    target=os.readlink(fd)
    if target.startswith('/tmp/') or target.startswith(str(home/'\.cache').replace('\\','')):refs.append(target)
   except OSError:pass
  cwd=os.readlink(d/'cwd')
  if refs or cwd.startswith('/tmp/'):processes.append({'pid':int(d.name),'cmdline':cmd[:800],'cwd':cwd,'open_temp_cache':refs[:30]})
 except (OSError,PermissionError):pass
print(json.dumps({'unix':time.time(),'uid':uid,'home':str(home),'owned_tmp_top_level':owned,'measured_sizes':sorted(rows,key=lambda x:x.get('allocated_bytes',0),reverse=True),'active_references':processes,'scope':'current uid only; tmp top level and home cache children, no root filesystem recursion'},ensure_ascii=False))
