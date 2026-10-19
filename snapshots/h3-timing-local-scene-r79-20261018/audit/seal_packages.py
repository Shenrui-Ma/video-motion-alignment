from pathlib import Path
import hashlib,json,time,sys,shutil,tarfile
P=Path(__file__).resolve().parents[1];C=P/'analysis/evaluation';sys.path.insert(0,str(P/'scripts'))
import execution_gate
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
files={}
for folder in ['scripts','tests','configs','runtime']:
 for p in (C/folder).rglob('*'):
  if p.is_file() and (folder=='runtime' or '__pycache__' not in p.parts):files[str(p.relative_to(C))]=sha(p)
put(C/'CONSUMER_FREEZE.json',dict(schema='r79-consumer-freeze-v1',files=files,created_unix=time.time(),numeric_inheritance='Exact R76/R63 runtime bytes, separate registered2 full source tasks. Prompt P1-local-v1 paired.'))
x=execution_gate.seal(P)
# Preserve source-only evidence inside this new run for independent review.
S=Path('/Users/researcher/DevProjects/h3-ivebench-expanded-metrics-r73-20261018/audit/benchmark_task_scope_20261018/source_candidate_review')
for name in ['INPUT_RECORDS.json','SOURCE_REVIEW.json','MANIFEST.json']:
 d=P/'audit/source_review'/name;d.parent.mkdir(exist_ok=True);shutil.copyfile(S/name,d)
for sid in ['short_0144','short_0166']:shutil.copyfile(S/'six_frames'/f'{sid}.jpg',P/'audit/source_review'/f'{sid}.jpg')
put(P/'audit/LOCAL_CPU_VALIDATION.json',dict(producer_tests=52,consumer_tests=31,producer_test_log_sha256=sha(P/'audit/CPU_TESTS_final.log'),consumer_test_log_sha256=sha(C/'audit/CPU_TESTS_final.log'),producer_seal_sha256=sha(P/'deploy_manifest.json'),consumer_freeze_sha256=sha(C/'CONSUMER_FREEZE.json'),input_map_pixel_equal=True,original_pts_verified=True,gpu_calls=0))
# Bundle immutable producer, full official inputs, small consumer runtime and prepared source videos.
rels=set(x['files'])|{'deploy_manifest.json','configs/admission.json','configs/queue.json'}
rels|={str(p.relative_to(P)) for p in (P/'inputs').glob('*') if p.is_file()}
for folder in ['scripts','tests','configs','runtime','prepared']:
 rels|={str(p.relative_to(P)) for p in (C/folder).rglob('*') if p.is_file() and (folder=='runtime' or '__pycache__' not in p.parts)}
rels.add('analysis/evaluation/CONSUMER_FREEZE.json')
rels|={str(p.relative_to(P)) for p in (P/'audit/source_review').glob('*') if p.is_file()}
for p in [P/'audit/LOCAL_CPU_VALIDATION.json',P/'audit/PARENT_INHERITANCE.json',P/'audit/CPU_TESTS_final.log',C/'audit/CPU_TESTS_final.log']:rels.add(str(p.relative_to(P)))
record={rel:dict(sha256=sha(P/rel),bytes=(P/rel).stat().st_size) for rel in sorted(rels)}
put(P/'audit/DEPLOY_FILES.json',record)
with tarfile.open(P/'audit/CPU_DEPLOY_BUNDLE.tar.gz','w:gz',compresslevel=1) as archive:
 for rel in sorted(rels):archive.add(P/rel,arcname=rel,recursive=False)
 archive.add(P/'audit/DEPLOY_FILES.json',arcname='audit/DEPLOY_FILES.json',recursive=False)
print(json.dumps(dict(producer_seal_sha256=sha(P/'deploy_manifest.json'),producer_files=len(x['files']),consumer_freeze_sha256=sha(C/'CONSUMER_FREEZE.json'),consumer_files=len(files),bundle_bytes=(P/'audit/CPU_DEPLOY_BUNDLE.tar.gz').stat().st_size,bundle_sha256=sha(P/'audit/CPU_DEPLOY_BUNDLE.tar.gz'))))
