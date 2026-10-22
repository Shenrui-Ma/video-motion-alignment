"""Private SSH transfer in bounded chunks; no local large tensor copy."""
import subprocess,json,pathlib,shlex,hashlib,time
BASE=pathlib.Path(__file__).resolve().parent
old='/data5/researcher/h3_runs/timing_autoresearch_20261016'
new='/data4/researcher/h3_runs/timing_phase_combined_r148_20261020/parents/05_real_megumi_v'
audit=json.loads((BASE/'SAM_ORIGINAL_CACHE_AUDIT.json').read_text())
files=[(old+'/audit/'+k,new+'/audit/'+k,v['bytes'],v['file_sha256']) for k,v in audit.items() if 'file_sha256' in v and ('latent' in k or k.startswith('tensor_blobs/') and v['bytes']<20_000_000 or k.endswith('_noise.pt') or k.endswith('_conditioning.json')) and not k.startswith('tensor_blobs/611c')]
files.append(('/data5/researcher/h3_runs/timing_window_location_r33_20261017/audit/tensor_blobs/e75942ff5de6f8978671163245e6a4c9298c027077c239a1316e52cd9a511873.pt',new+'/audit/tensor_blobs/e75942ff5de6f8978671163245e6a4c9298c027077c239a1316e52cd9a511873.pt',142542536,'2e9f910012cfcb972f824b93035a1872bad516d1f004273e3f968c7bcfc87d9c'))
def ssh(host,script,data=None):
 p=subprocess.run(['ssh','-o','ConnectTimeout=10',host,'python3 -c '+shlex.quote(script)],input=data,capture_output=True,timeout=90)
 if p.returncode:raise RuntimeError(p.stderr.decode().replace('Permission denied','AUTH_REJECTED'))
 return p.stdout
receipts=[]
for src,dst,size,digest in files:
 state=json.loads(ssh('H3_SERVER_B',f'import pathlib,json,hashlib;p=pathlib.Path({dst!r});q=p.with_suffix(".part");p.parent.mkdir(parents=True,exist_ok=True);print(json.dumps({{"done":p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()=={digest!r},"offset":q.stat().st_size if q.exists() else 0}}))'))
 if not state['done']:
  offset=state['offset'];assert 0<=offset<=size
  while offset<size:
   count=min(4*1024*1024,size-offset)
   block=ssh('H3_SERVER_A',f'import sys;f=open({src!r},"rb");f.seek({offset});sys.stdout.buffer.write(f.read({count}))');assert len(block)==count
   blockhash=hashlib.sha256(block).hexdigest()
   ssh('H3_SERVER_B',f'import pathlib,sys,hashlib;p=pathlib.Path({dst!r}).with_suffix(".part");data=sys.stdin.buffer.read();assert len(data)=={count} and hashlib.sha256(data).hexdigest()=={blockhash!r};assert (p.stat().st_size if p.exists() else 0)=={offset};f=p.open("ab");f.write(data);f.close()',block)
   offset+=count;print(json.dumps({'file':pathlib.Path(dst).name,'bytes':offset,'total':size}),flush=True)
  ssh('H3_SERVER_B',f'import pathlib,hashlib;p=pathlib.Path({dst!r});q=p.with_suffix(".part");assert q.stat().st_size=={size} and hashlib.sha256(q.read_bytes()).hexdigest()=={digest!r};q.rename(p)')
 receipts.append({'source_host':'H3_SERVER_A','source':src,'target_host':'H3_SERVER_B','target':dst,'bytes':size,'sha256':digest,'verified':True});(BASE/'SAM_TRANSFER_RECEIPT.json').write_text(json.dumps(receipts,indent=2)+'\n')
print('COMPLETE',flush=True)
