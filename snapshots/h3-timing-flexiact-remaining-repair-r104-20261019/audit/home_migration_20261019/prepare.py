from pathlib import Path
import json,hashlib,shutil,time
D=Path('/Users/researcher/DevProjects');P=D/'h3-timing-flexiact-remaining-repair-r104-20261019';C=D/'h3-flexiact-remaining-repair-metrics-r104-20261019'
A=P/'audit/home_migration_20261019';B=C/'audit/home_migration_20261019'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text());write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
A.mkdir(exist_ok=True);B.mkdir(exist_ok=True)
seal=read(P/'deploy_manifest.json');freeze=read(C/'CONSUMER_FREEZE.json')
assert not(P/'processes/service.json').exists() and not any((C/'incoming').rglob('*'))
assert not (A/'prior_sealed').exists() and not (B/'prior_sealed').exists()
assert all(sha(P/k)==v['sha256'] for k,v in seal['files'].items())
assert all(sha(C/k)==v for k,v in freeze['files'].items())
for base,out,files in [(P,A,list(seal['files'])+['deploy_manifest.json']),(C,B,list(freeze['files'])+['CONSUMER_FREEZE.json'])]:
 for rel in files:
  dest=out/'prior_sealed'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(base/rel,dest)
old='/data5/researcher/h3_runs/timing_flexiact_remaining_repair_r104_20261019';new='/home/researcher/h3_runs/timing_flexiact_remaining_repair_r104_20261019'
runtime=read(P/'configs/runtime.json');assert runtime['remote_root']==old;runtime['remote_root']=new;write(P/'configs/runtime.json',runtime)
for path in (P/'configs/graphs').glob('*.json'):
 before=path.read_text();assert old in before;path.write_text(before.replace(old,new))
pre=read(P/'configs/predecessor.json');r90=next(x for x in pre['required'] if x['key']=='r90');assert r90['producer_seal_sha256']=='56a8cc22313e1fd038c3faceb732fddb5a53e851e03257c496bc09745d6ba169';r90['producer_seal_sha256']=sha(D/'h3-timing-flexiact-p1-control-r90-20261018/deploy_manifest.json');write(P/'configs/predecessor.json',pre)
p=P/'audit/root_run_batch.py';s=p.read_text();before="require(root!=ROOT and root.parent==ROOT.parent,'peer must be a distinct root in the same managed run directory')";assert before in s
s=s.replace(before,"managed={p.resolve() for p in [ROOT.parent,Path('/data5/researcher/h3_runs'),Path('/home/researcher/h3_runs')]}\n        require(root!=ROOT and root.parent in managed,'peer must be a distinct root in an authorized managed run directory')");p.write_text(s)
test=(D/'h3-timing-flexiact-p1-control-r90-20261018/tests/test_managed_peer_roots.py').read_text().replace('root_run_native','root_run_batch');(P/'tests/test_managed_peer_roots.py').write_text(test)
changes=[]
for rel,row in seal['files'].items():
 if sha(P/rel)!=row['sha256']:changes.append(rel)
expected={'configs/runtime.json','configs/predecessor.json','audit/root_run_batch.py'}|{str(p.relative_to(P)) for p in (P/'configs/graphs').glob('*.json')}
assert set(changes)==expected
assert sha(P/'configs/scientific_contract.json')==sha(A/'prior_sealed/configs/scientific_contract.json')
for p in (P/'configs/graphs').glob('*.json'):
 assert p.read_text().replace(new,old)==(A/'prior_sealed'/p.relative_to(P)).read_text()
c=read(C/'configs/contract.json');assert c['producer_remote']==old;c['producer_remote']=new;write(C/'configs/contract.json',c)
p=C/'scripts/prepare_freeze.py';s=p.read_text();assert old in s;p.write_text(s.replace(old,new))
# Preserve the old freeze in the backup and clear only its unexecuted administrative binding.
assert sha(C/'CONSUMER_FREEZE.json')==sha(B/'prior_sealed/CONSUMER_FREEZE.json');(C/'CONSUMER_FREEZE.json').unlink()
write(A/'PLAN.json',{'created_unix':time.time(),'old_remote':old,'new_remote':new,'reason':'data5 free20GiB while current R90/R108 captures continue; home free130GiB. Parent authorized managed-directory migration.','old_producer_seal_sha256':sha(A/'prior_sealed/deploy_manifest.json'),'changed_existing_files':changes,'new_test':'tests/test_managed_peer_roots.py','scientific_contract_identical':True,'graphs_differ_only_administrative_root':True,'r90_new_seal':r90['producer_seal_sha256'],'old_remote_retained':True})
print(json.dumps({'changed':changes,'new_remote':new}))
