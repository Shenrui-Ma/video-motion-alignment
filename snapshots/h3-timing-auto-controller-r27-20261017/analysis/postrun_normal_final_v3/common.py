"""Limited archive recovery; no model, media decoder, or numerical metric import."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def require(v,m):
 if not v:raise ValueError(m)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save_new(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(json.dumps(d,indent=2,allow_nan=False)+'\n')
def files(p):return {str(x.relative_to(p)) for x in Path(p).rglob('*') if x.is_file()}
def checked_partial(folder,expected,extra=()):
 require(files(folder)==set(expected)|set(extra),'partial final exact inventory differs')
 for rel,row in expected.items():
  p=folder/rel;require(not p.is_symlink() and p.resolve().is_relative_to(folder.resolve()),'unsafe partial path')
  require(p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'partial final changed '+rel)

def scope_fields():
 return {'completion_scope':'archive_integrity_and_existing_measurements_with_failed_RGB_replay','original_outcome_gate_passed':False,'all_OFF_141RGB_equal':False,'final_AV_latent_exact':True,'pixel_difference_origin':'undetermined','new_model_invocations':0,'new_metric_invocations':0}
def check_scope(d):
 for k,v in scope_fields().items():require(type(d.get(k)) is type(v) and d[k]==v,'limited completion scope differs '+k)
 return True

def bootstrap(remote=False):
 p=read(HERE/'PROTOCOL.json');root=Path(p['root_remote'] if remote else p['root_local']);old=root/p['old_postrun']
 require(sha(old/'FREEZE.json')==p['old_freeze_sha256'],'old recovery seal changed')
 for rel,d in read(old/'FREEZE.json')['files'].items():require(sha(old/rel)==d,'old sealed dependency changed '+rel)
 require(sha(old/'BINDING.json')==p['old_binding_sha256'],'old approved binding changed')
 # The old failure is local-only; its preserved frozen copy is shipped without overwriting it.
 require(sha(HERE/'RECOVERY_V2_CONSUMER_FAILURE.json')==p['old_failure_sha256'],'failure evidence changed')
 require(sha(HERE/'INPUT_EVIDENCE.json')==p['input_evidence_sha256'] and sha(HERE/'RESULTS.json')==p['rgb_results_sha256'],'RGB diagnostic changed')
 for rel,d in read(HERE/'FREEZE.json')['files'].items():require(sha(HERE/rel)==d,'new recovery seal changed '+rel)
 sys.path.insert(0,str(old));import remote_consume as legacy
 return p,root,old,legacy

def approve(p):
 b=read(HERE/'BINDING.json');require(b.get('approved') is True and b.get('protocol_sha256')==sha(HERE/'PROTOCOL.json') and b.get('old_binding_sha256')==p['old_binding_sha256'] and b.get('scope')==p['scope'],'root approval scope absent');return b
