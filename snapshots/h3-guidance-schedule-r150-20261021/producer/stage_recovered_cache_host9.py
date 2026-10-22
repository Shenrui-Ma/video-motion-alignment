"""Stream a verified recovered cache between internal hosts; no local tensor copy."""
import argparse,hashlib,json,shlex,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('candidate',choices=['musk05','firefly06','sam07']);a=ap.parse_args();r=P/'condition_recovery'/a.candidate
cfg=json.loads((r/'config.json').read_text());result=json.loads((r/'CACHE_RECOVERY_RESULT.json').read_text());assert result['passed']
source=cfg['remote_root'];target='/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/condition_recovery/'+a.candidate
rows=[{'file':x['file'],'sha256':x['sha256']} for x in cfg['roles'] if x['role'] in ['reference_image_latent','reference_vae_latent','conditioning_tags','conditioning_position']]
rows += [{'file':result['embedding_file'],'sha256':result['embedding_file_sha256']},{'file':result['metadata_file'],'sha256':result['metadata_sha256']},{'file':cfg['noise_file'],'sha256':cfg['noise_sha256']}]
assert all(Path(x['file']).parent==Path(source) for x in rows)
script="import hashlib,json,pathlib\nrows="+repr(rows)+"\nfor x in rows:\n p=pathlib.Path(x['file']);assert p.is_file() and not p.is_symlink();assert hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']\nprint('source hashes pass')\n"
subprocess.run(['ssh','H3_SERVER_B','python3 -'],input=script,text=True,check=True)
subprocess.run(['ssh','H3_SERVER_A','mkdir -p '+shlex.quote(target)],check=True)
scmd='tar -cf - -C '+shlex.quote(source)+' '+' '.join(shlex.quote(Path(x['file']).name) for x in rows)
tcmd='tar -xf - -C '+shlex.quote(target)
with subprocess.Popen(['ssh','H3_SERVER_B',scmd],stdout=subprocess.PIPE) as src:
 dst=subprocess.run(['ssh','H3_SERVER_A',tcmd],stdin=src.stdout);src.stdout.close();assert dst.returncode==0 and src.wait()==0
files={x['file']:{'target_file':target+'/'+Path(x['file']).name,'sha256':x['sha256']} for x in rows}
script="import hashlib,json,pathlib\nrows="+repr(files)+"\nfor old,x in rows.items():\n p=pathlib.Path(x['target_file']);assert p.is_file() and not p.is_symlink();assert hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']\nprint('target hashes pass')\n"
subprocess.run(['ssh','H3_SERVER_A','python3 -'],input=script,text=True,check=True)
out={'passed':True,'candidate_id':a.candidate,'source_host':'H3_SERVER_B','target_host':'H3_SERVER_A','source_root':source,'target_root':target,'files':files,'result_sha256':hashlib.sha256((r/'CACHE_RECOVERY_RESULT.json').read_bytes()).hexdigest(),'local_tensors_written':False,'transport':'SSH internal host stream','created_unix':time.time()};(r/'HOST9_CACHE_BINDING.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'passed':True,'files':len(files),'target_root':target}))
