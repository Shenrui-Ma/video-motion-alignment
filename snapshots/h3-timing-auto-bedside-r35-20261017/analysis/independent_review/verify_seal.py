from pathlib import Path
import hashlib,json,tarfile
R=Path(__file__).resolve().parents[2];H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();J=lambda p:json.loads(Path(p).read_text())
seal=J(R/'audit/SEAL_v1.json');m=J(R/'audit/deploy_manifest_v1.json');assert H(R/'audit/deploy_manifest_v1.json')==seal['producer_manifest_sha256'];assert len(m['files'])==98
for n,v in m['files'].items():assert H(R/n)==v['sha256'] and (R/n).stat().st_size==v['bytes'],n
bundle=R/'audit/runtime_bundle_v1.tar.gz';assert H(bundle)==seal['runtime_bundle_sha256']
with tarfile.open(bundle) as f:
 names=[x.name for x in f.getmembers()];expected=set(m['files'])|{'deploy_manifest.json','configs/admission.json','configs/queue.json'};assert len(names)==len(set(names)) and set(names)==expected
 for n in names:assert hashlib.sha256(f.extractfile(n).read()).hexdigest()==H(R/('audit/deploy_manifest_v1.json' if n=='deploy_manifest.json' else n)),n
parent=R.parent/'h3-timing-auto-controller-r27-20261017';reuse=J(R/'configs/r27_inheritance.json');assert len(reuse['exact_numerical_files'])==17
for n,h in reuse['exact_numerical_files'].items():assert H(R/n)==H(parent/n)==h,n
stage=J(R/'audit/cpu_stage_attempt6_manifest.json');mismatch=[n for n,h in stage['files'].items() if H(R/n)!=h];assert not mismatch,mismatch
cpu=J(R/'audit/CPU_EVIDENCE.json');assert H(R/'audit/CPU_EVIDENCE.json')==seal['actual_cpu_evidence_sha256'];assert H(R/'audit/real_comfy_cpu_attempt6.log')==cpu['log_sha256'];assert H(R/'audit/cpu_stage_attempt6_manifest.json')==cpu['stage_source_manifest_sha256'];assert cpu['result']['exit']==0
for c,nfe in zip(cpu['smoke_cases'],(20,36)):
 assert c['success'] and c['CUDA_initialized'] is False and c['cases'][0]['NFE']==nfe and c['cases'][0]['callbacks']==20 and c['cases'][0]['all20_chosen_and_final_equal_singleforward_expected_mask']
res={'status':'PASS','scope':'producer immutable bytes and actual CPU source/log evidence; postrun v2 review pending','producer_files':len(m['files']),'tar_exact_members':len(names),'numerical_files_exact_R27':17,'actual_cpu_stage_files_equal':len(stage['files']),'producer_manifest_sha256':H(R/'audit/deploy_manifest_v1.json'),'bundle_sha256':H(bundle),'cpu_evidence_sha256':H(R/'audit/CPU_EVIDENCE.json'),'cpu_cases_NFE':[c['cases'][0]['NFE'] for c in cpu['smoke_cases']],'CPU_test_counts':cpu['unit_tests'],'no_GPU_or_rerun':True}
(R/'analysis/independent_review/PRODUCER_BYTE_REVIEW.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps(res,indent=2))
