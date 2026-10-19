"""Resume only R54 frozen input uploads, verifying every prefix and chunk."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
DEST = '/data3/researcher/h3_runs/timing_ivebench_native_r54_20261017/inputs/'
SSH = ['ssh', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=10',
       '-o', 'ServerAliveCountMax=2', 'H3_SERVER_B']

def remote(code, data=None):
    p = subprocess.run(SSH + ['python3 -c ' + shlex.quote(code)], input=data,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=35)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors='replace')[-1000:])
    return json.loads(p.stdout)

def state(path):
    return remote('from pathlib import Path; import hashlib,json; p=Path(' + repr(path) +
                  '); b=p.read_bytes() if p.exists() else b""; print(json.dumps({"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}))')

def main():
    results=[]
    for src in sorted((ROOT/'inputs').iterdir()):
        if not src.is_file():
            continue
        data=src.read_bytes(); dst=DEST+src.name; s=state(dst); offset=s['bytes']
        assert offset<=len(data) and hashlib.sha256(data[:offset]).hexdigest()==s['sha256'], src.name
        failures=0
        while offset<len(data):
            chunk=data[offset:offset+128*1024]; digest=hashlib.sha256(chunk).hexdigest()
            code='''from pathlib import Path
import hashlib,json,sys
p=Path(PATH); offset=OFFSET; n=SIZE; expected=DIGEST
b=sys.stdin.buffer.read(n)
assert len(b)==n and hashlib.sha256(b).hexdigest()==expected
p.parent.mkdir(parents=True,exist_ok=True)
with p.open('r+b' if p.exists() else 'w+b') as f:
 f.seek(0,2); size=f.tell(); assert size in (offset,offset+n)
 f.seek(offset)
 if size==offset+n: assert f.read(n)==b
 else: f.write(b); f.flush()
print(json.dumps({'bytes':offset+n,'chunk_sha256':expected}))
'''.replace('PATH',repr(dst)).replace('OFFSET',str(offset)).replace('SIZE',str(len(chunk))).replace('DIGEST',repr(digest))
            try:
                result=remote(code,chunk)
                assert result=={'bytes':offset+len(chunk),'chunk_sha256':digest}
                offset+=len(chunk); failures=0
            except (subprocess.TimeoutExpired,RuntimeError):
                failures+=1
                if failures>=5: raise
                time.sleep(2)
        final=state(dst)
        assert final=={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        results.append(dict(file=src.name,**final))
        print(json.dumps(results[-1]),flush=True)
    (ROOT/'audit/REMOTE_INPUTS_VERIFIED.json').write_text(json.dumps({'files':results,'verified_unix':time.time()},indent=2)+'\n')

if __name__=='__main__': main()
