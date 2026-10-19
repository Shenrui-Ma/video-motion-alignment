"""Bounded CPU postrun contracts; no process control or GPU."""
import hashlib,json,re,time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()


def read(p):return json.loads(Path(p).read_text())


def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');tmp.replace(p)


def require(v,msg):
 if not v:raise ValueError(msg)


def safe(root,rel):
 root=Path(root);r=Path(rel);require(not r.is_absolute() and '..' not in r.parts,'unsafe relative path')
 p=root/r;require(not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),'symlink/outside path');return p


def relative(root,path):
 p=Path(path);require(p.is_absolute() and p.resolve().is_relative_to(root.resolve()) and not p.is_symlink(),'outside producer path');return str(p.relative_to(root))


def output_file(root,h,run):
 rows=h.get('outputs',{}).get('14',{}).get('images',[]);require(len(rows)==1,'exactly one output')
 r=rows[0];require(r['type']=='output' and not r.get('subfolder') and re.fullmatch(re.escape(run)+r'_\d+_\.mp4',r['filename']),'output identity')
 return safe(root,'output/'+r['filename'])


def verify_source_archive(root,arc,owner,run):
 before=read(arc/'FILE_INVENTORY.json');changes=[]
 for rel,item in before.items():
  require(sha(safe(arc,rel))==item['sha256'],'archive changed '+rel)
  if sha(safe(root,rel))!=item['sha256']:changes.append(rel)
 if not changes:return None
 require(changes==['configs/queue.json'],'producer scientific files changed '+repr(changes))
 old=read(arc/'configs/queue.json');new=read(root/'configs/queue.json')
 require(old.get('finalize') is False and new.get('finalize') is True and new==dict(old,finalize=True),'not solely false->true finalize')
 gatepath=arc/'RUN_GATE.json';gate=read(gatepath);require(gate.get('passed') is True and gate.get('run_id')==run and gate.get('owner')==owner,'release gate binding')
 rpath=root/'audit/root_release_request.json';r=read(rpath)
 require(r.get('pid')==owner['pid'] and r.get('owner')==owner['identity'],'release owner binding')
 require(r.get('gate_file')==str(gatepath) and r.get('gate_sha256')==sha(gatepath),'release exact gate binding')
 require(isinstance(r.get('unix'),(float,int)) and r['unix']>=gatepath.stat().st_mtime,'release predates archive gate')
 result={'change':'queue.finalize false->true','owner':owner,'run':run,'old_queue_sha256':before['configs/queue.json']['sha256'],'new_queue_sha256':sha(root/'configs/queue.json'),'root_release_record':r,'root_release_sha256':sha(rpath),'all_other_scientific_files_unchanged':True}
 p=arc/'ADMIN_RELEASE_ACCEPTANCE.json'
 if p.exists():require(read(p)==result,'release acceptance changed')
 else:save(p,result)
 return result


def check_binding(root,b,p):
 require(str(root)==p['root_remote'] and b['remote_root']==str(root) and b['approved_for_consumer_start'] is True,'root consumer authorization/root')
 require(b['protocol_sha256']==sha(HERE/'PROTOCOL.json') and b['consumer_freeze_sha256']==sha(HERE/'FREEZE.json'),'postrun protocol/code binding')
 require(b['producer_manifest_sha256']==p['producer_manifest_sha256']==sha(root/'deploy_manifest.json'),'producer seal binding')
 check_declared_cases(p,read(root/'configs/scientific_contract.json'))
 owner=read(root/'processes/service.json');require(owner==b['service_record'],'service generation changed')
 for case in p['cases']:
  jp=root/'logs'/f'{case["run_id"]}_job.json'
  if jp.exists():
   j=read(jp);require(j['service_pid']==owner['pid'] and j['service_identity']==owner['identity'],'job generation differs')
 return owner


def check_declared_cases(protocol,producer):
 fields=('run_id','source_id','seed','identity','prompt','video','video_sha256','portrait','portrait_sha256','provenance','provenance_sha256')
 planned=protocol['cases'];actual=producer['cases']
 require(len(planned)==len(actual)==5,'five declared cases required')
 require([c['run_id'] for c in planned]==producer['case_order'],'producer case order differs')
 for case,source in zip(planned,actual):
  require(all(case[k]==source[k] for k in fields),'source/identity/input binding differs')
 require(protocol['geometry']==producer['geometry']=={'width':1152,'height':768,'frames':158,'fps':24},'geometry differs')
 require(protocol['score_output_indices']==producer['evaluation']['score_output_indices']==list(range(0,147,3)),'49frame scoring map differs')
 return True


def check_case_summary(summary,case):
 require(summary.get('passed') is True,'case incomplete')
 for field in ('run_id','source_id','seed','identity','portrait_sha256'):
  require(summary.get(field)==case[field],'case result identity differs '+field)
 require(summary.get('source_video_sha256')==case['video_sha256'],'case source video differs')
 require(summary.get('NFE')==20 and summary.get('actual_routed_blocks')==0 and summary.get('padding_evaluated') is False and summary.get('decoded_frame_md5_equal') is True and summary.get('score_output_indices')==list(range(0,147,3)),'Native counts/49frame-map contract differs')
 return True


def canonical_sha(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def verify_phase_dependencies(root,arc,rels):
 """A phase checks its actual copied and producer dependencies, not unrelated PT."""
 inventory=read(arc/'FILE_INVENTORY.json');checked={}
 for rel in sorted(set(rels)):
  require(rel in inventory,'unregistered phase dependency '+rel)
  expected=inventory[rel]
  for base in (arc,root):
   p=safe(base,rel);require(p.stat().st_size==expected['bytes'] and sha(p)==expected['sha256'],'phase dependency changed '+rel)
  checked[rel]=expected
 return checked


def verify_producer_sources(root,manifest_sha256,all_files=False):
 """Pin executable imports per phase; full immutable inventory at boundaries."""
 manifest_path=Path(root)/'deploy_manifest.json'
 require(sha(manifest_path)==manifest_sha256,'producer manifest changed')
 entries=read(manifest_path)['files'];checked={}
 for rel,expected in entries.items():
  if not all_files and not (rel.endswith('.py') and rel.split('/')[0] in ('scripts','extensions')):continue
  p=safe(root,rel);require(p.stat().st_size==expected['bytes'] and sha(p)==expected['sha256'],'producer source changed '+rel)
  checked[rel]=expected['sha256']
 require(bool(checked),'producer dependency inventory empty')
 return checked


def verify_archive_anchor(arc,run,owner):
 receipt=read(arc.parent.parent/'archive_receipts'/f'{run}.json')
 require(receipt['run_id']==run and receipt['owner']==owner,'archive receipt identity')
 require(sha(arc/'RUN_GATE.json')==receipt['run_gate_sha256'] and sha(arc/'FILE_INVENTORY.json')==receipt['inventory_sha256'],'archive anchor changed')
 gate=read(arc/'RUN_GATE.json')
 require(gate['passed'] is True and gate['run_id']==run and gate['owner']==owner and gate['file_inventory_sha256']==receipt['inventory_sha256'],'archive gate identity')
 return gate

