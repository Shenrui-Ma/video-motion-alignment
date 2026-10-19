"""Process each frozen source once its verified transfer completes; CPU only."""
from pathlib import Path
import hashlib,json,os,subprocess,time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
protocol=json.loads((HERE/'PROTOCOL.json').read_text())
identity={'pid':os.getpid(),'uid':os.getuid(),'start_ticks':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
          'cmdline_sha256':sha('/proc/self/cmdline'),'started_unix':time.time()}
(HERE/'watch_owner.json').write_text(json.dumps(identity,indent=2)+'\n')
deadline=time.monotonic()+7200
while True:
    complete=[]
    for row in protocol['cases']:
        receipt=HERE/('COMPLETE_'+row['pair_id']+'.json')
        if receipt.exists():
            data=json.loads(receipt.read_text())
            assert data['protocol_sha256']==sha(HERE/'PROTOCOL.json')
            complete.append(row['pair_id']);continue
        video=ROOT/'inputs'/row['video'];provenance=ROOT/'inputs'/row['provenance']
        if not video.exists() or not provenance.exists():continue
        if sha(provenance)!=row['provenance_sha256'] or sha(video)!=row['video_sha256']:continue
        print('extracting '+row['pair_id'],flush=True)
        subprocess.run([PYTHON,str(HERE/'run.py'),'--pair',row['pair_id']],check=True,timeout=900)
        complete.append(row['pair_id'])
    (HERE/'watch_status.json').write_text(json.dumps({'unix':time.time(),'complete':complete,'pending':[r['pair_id'] for r in protocol['cases'] if r['pair_id'] not in complete]},indent=2)+'\n')
    if len(complete)==len(protocol['cases']):
        subprocess.run([PYTHON,str(HERE/'run.py')],check=True,timeout=900)
        print('all five CPU source poses complete',flush=True);break
    if time.monotonic()>deadline:raise TimeoutError('source transfer wait exceeded two hours')
    time.sleep(30)
