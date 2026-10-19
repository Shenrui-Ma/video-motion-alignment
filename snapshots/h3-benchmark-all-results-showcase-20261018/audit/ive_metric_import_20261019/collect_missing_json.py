import base64,hashlib,json,shlex,subprocess
from pathlib import Path
from import_scores import AUDIT,MAP
issues=json.loads((AUDIT/'DRY_RUN.json').read_text())['issues'];hosts={};paths=[]
for value in issues.values():
 if not value.startswith('missing JSON '):continue
 local=Path(value[len('missing JSON '):]);remote=None
 for r,p in sorted(MAP.items(),key=lambda x:-len(str(x[1]))):
  if local.is_relative_to(p):remote=str(Path(r)/local.relative_to(p));break
 if remote is None:continue
 if not remote.endswith('.json'):raise ValueError('only JSON allowed')
 host='H3_SERVER_A' if remote.startswith('/data5/') else 'H3_SERVER_B';hosts.setdefault(host,[]).append(remote)
receipts=[]
for host,files in hosts.items():
 files=sorted(set(files));code='import json,base64,hashlib;from pathlib import Path;out={}\nfor x in '+repr(files)+':\n p=Path(x)\n if not p.is_file():out[x]={"missing":True};continue\n if p.stat().st_size>5000000:raise ValueError("JSON too large")\n b=p.read_bytes();json.loads(b);out[x]={"sha256":hashlib.sha256(b).hexdigest(),"base64":base64.b64encode(b).decode()}\nprint(json.dumps(out))'
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',host,shlex.join(['python3','-c',code])],capture_output=True,text=True,timeout=60,check=True)
 for remote,item in json.loads(result.stdout).items():
  if item.get('missing'):receipts.append({'host':host,'remote':remote,'missing':True});continue
  b=base64.b64decode(item['base64']);assert hashlib.sha256(b).hexdigest()==item['sha256'];dest=AUDIT/'collected_json'/remote.lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert dest.read_bytes()==b
  else:dest.write_bytes(b)
  receipts.append({'host':host,'remote':remote,'local':str(dest),'sha256':item['sha256'],'bytes':len(b)})
name=AUDIT/('COLLECTED_'+str(len(list(AUDIT.glob('COLLECTED_*.json')))+1)+'.json');name.write_text(json.dumps(receipts,indent=2)+'\n');print(json.dumps({'files':len(receipts),'bytes':sum(r.get('bytes',0) for r in receipts),'missing':[r['remote'] for r in receipts if r.get('missing')]}))
