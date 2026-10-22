"""Low-overhead allocator counters; no synchronization or extra model forward."""
from pathlib import Path
import json,os,time,threading

def install(torch,root,cap):
 created=time.time();directory=Path(root)/'audit/memory';directory.mkdir(parents=True,exist_ok=True);path=directory/f'capacity20_{os.getpid()}.json'
 def tick():
  while True:
   try:
    record={'pid':os.getpid(),'created_unix':created,'updated_unix':time.time(),'cap_bytes':cap,'scope':'whole service including weight loading, sampler and final decode','max_allocated_bytes':torch.cuda.max_memory_allocated(0),'max_reserved_bytes':torch.cuda.max_memory_reserved(0),'allocated_bytes':torch.cuda.memory_allocated(0),'reserved_bytes':torch.cuda.memory_reserved(0)}
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(record,indent=2));tmp.replace(path)
   except Exception as e:
    (directory/f'memory_error_{os.getpid()}.txt').write_text(repr(e));return
   time.sleep(5)
 threading.Thread(target=tick,daemon=True,name='h3-memory-peak').start()
