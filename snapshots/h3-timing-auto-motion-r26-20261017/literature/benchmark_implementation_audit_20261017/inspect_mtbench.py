import fcntl,hashlib,json,pathlib,zipfile,csv,time
b=pathlib.Path(__file__).resolve().parent
lock=open('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('BUSY');raise SystemExit(75)
start=time.time();z=zipfile.ZipFile(b/'downloads/MTBench.zip');infos=z.infolist();names=[i.filename for i in infos]
(b/'MTBENCH_ZIP_INVENTORY.json').write_text(json.dumps([{'path':i.filename,'bytes':i.file_size,'compressed_bytes':i.compress_size,'CRC':i.CRC} for i in infos],indent=2))
print('entries',len(names),'video',[n for n in names if n.lower().endswith('.mp4')][:6]);print('txt',[n for n in names if n.lower().endswith(('.txt','.json','.yaml','.yml','.csv'))][:20]);print('license',[n for n in names if any(s in n.lower() for s in ['license','readme','term'])])
d=b/'mtbench_metadata';d.mkdir(exist_ok=True)
for i in infos:
 p=pathlib.PurePosixPath(i.filename)
 if '..' in p.parts or p.is_absolute():raise ValueError('bad path')
 if i.filename.endswith(('.txt','.json','.yaml','.yml','.csv')) and i.file_size<1_000_000:
  out=d/i.filename;out.parent.mkdir(exist_ok=True,parents=True);out.write_bytes(z.read(i))
print('seconds',time.time()-start)
