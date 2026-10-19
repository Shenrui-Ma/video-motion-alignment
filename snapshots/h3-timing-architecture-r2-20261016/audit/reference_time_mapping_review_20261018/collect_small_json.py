import subprocess,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
cases=[('r85','timing_flexiact_expanded_r85_20261018','one_leg__movie_man_9'),('r89','timing_ive_subject_capacity_r89_20261018','short_0131'),('r89','timing_ive_subject_capacity_r89_20261018','short_0343'),('r73','timing_ivebench_expanded_r73_20261018','short_0252')]
paths=[]
for prefix,run,source in cases:
 for arm in ['native','forced']:
  paths.append('/data5/researcher/h3_runs/'+run+'/audit/'+prefix+'_'+source+'_seed2026101701_'+arm+'_conditioning.json')
script='import pathlib,json,hashlib\npaths='+repr(paths)+'\nresult={}\nfor name in paths:\n p=pathlib.Path(name); b=p.read_bytes(); assert len(b)<2000000; result[name]={"sha256":hashlib.sha256(b).hexdigest(),"text":b.decode()}\nprint(json.dumps(result))\n'
r=subprocess.run(['ssh','-o','ConnectTimeout=30','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=6','H3_SERVER_A','python3 -'],input=script,text=True,capture_output=True,timeout=90);(ROOT/'COLLECT_STDERR.txt').write_text(r.stderr);r.check_returncode();result=json.loads(r.stdout);manifest={}
for name,item in result.items():
 out=ROOT/'actual'/Path(name).name;out.parent.mkdir(exist_ok=True);out.write_text(item['text']);assert hashlib.sha256(out.read_bytes()).hexdigest()==item['sha256'];manifest[str(out.relative_to(ROOT))]={'remote':name,'sha256':item['sha256'],'bytes':out.stat().st_size}
(ROOT/'ACTUAL_JSON_BINDINGS.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Saved',len(manifest),'small actual conditioning JSONs')
