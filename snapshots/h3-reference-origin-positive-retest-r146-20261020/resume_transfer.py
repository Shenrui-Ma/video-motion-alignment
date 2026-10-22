from pathlib import Path
import subprocess,json,hashlib,shlex,time
R=Path(__file__).resolve().parent
rows=json.loads((R/'HOST9_INPUTS.json').read_text());old='/home/researcher/h3_runs/timing_oxygen_generic_retention_r141b_host9_20261020';new='/data4/researcher/h3_runs/reference_origin_positive_retest_r146_20261020/parents/short_0252'
def ssh(host,code,data=None):
 p=subprocess.run(['ssh','-T','-o','ConnectTimeout=10','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=3',host,'python3 -c '+shlex.quote(code)],input=data,capture_output=True,timeout=50)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
 return p.stdout
receipts=[]
for row in rows:
 relative=row['file'][len(old)+1:];local=R/'transfer'/relative;target=new+'/'+relative;local.parent.mkdir(parents=True,exist_ok=True)
 if not local.exists() or local.stat().st_size!=row['bytes'] or hashlib.sha256(local.read_bytes()).hexdigest()!=row['sha256']:
  value=ssh('H3_SERVER_A','import sys;sys.stdout.buffer.write(open('+repr(row['file'])+',"rb").read())')
  assert len(value)==row['bytes'] and hashlib.sha256(value).hexdigest()==row['sha256'];local.write_bytes(value)
 content=local.read_bytes()
 status=json.loads(ssh('H3_SERVER_B','from pathlib import Path;import json,hashlib;p=Path('+repr(target)+');p.parent.mkdir(parents=True,exist_ok=True);v=p.read_bytes() if p.exists() else b"";print(json.dumps({"size":len(v),"sha256":hashlib.sha256(v).hexdigest()}))'))
 offset=status['size'];assert offset<=len(content) and hashlib.sha256(content[:offset]).hexdigest()==status['sha256']
 while offset<len(content):
  chunk=content[offset:offset+2**20]
  code='from pathlib import Path;import sys,hashlib;p=Path('+repr(target)+');v=sys.stdin.buffer.read();assert len(v)=='+str(len(chunk))+' and hashlib.sha256(v).hexdigest()=='+repr(hashlib.sha256(chunk).hexdigest())+';assert (p.stat().st_size if p.exists() else 0)=='+str(offset)+';f=p.open("ab");f.write(v);f.close();print(p.stat().st_size)'
  got=int(ssh('H3_SERVER_B',code,chunk));assert got==offset+len(chunk);offset=got
 final=ssh('H3_SERVER_B','import hashlib;print(hashlib.sha256(open('+repr(target)+',"rb").read()).hexdigest())').decode().strip();assert final==row['sha256']
 receipts.append(dict(source=row['file'],target=target,bytes=len(content),sha256=final));print(relative,'verified',len(content),flush=True)
(R/'TRANSFER_RECEIPT.json').write_text(json.dumps({'passed':True,'files':receipts,'private_hosts':['192.0.2.1','192.0.2.1'],'proxy':False,'unix':time.time()},indent=2)+'\n')
