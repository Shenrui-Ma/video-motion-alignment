from pathlib import Path
import sys,time,ast,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from common import ROOT,read,write,bound,verify_record
from finalize_composite import validate_migration
from hardware_prefix import hardware_files,verify_hardware_prefix
prefix=ROOT/'audit/hardware_recovery/prefix_evidence'
migration=read(prefix/'MIGRATION_MANIFEST.json');deployment=read(prefix/'MIGRATION_DEPLOYMENT.json');partial=read(prefix/'PREFIX_PARTIAL_RELEASE.json')
case=next(c for c in read(ROOT/'EVALUATION_MANIFEST.json')['cases'] if c['source_id']=='short_0358')
bindings={a:read(ROOT/'runtime/short_0358'/f'{a}.json') for a in ['early','late','split','global_weak']}
runs={a:read(ROOT/'actual/short_0358'/a/'GATE.json') for a in ['early','late']}
record={'migration':bound(prefix/'MIGRATION_MANIFEST.json'),'deployment':bound(prefix/'MIGRATION_DEPLOYMENT.json'),'partial_release':bound(prefix/'PREFIX_PARTIAL_RELEASE.json'),'partial_artifacts':{k:bound(prefix/r) for k,r in hardware_files(migration).items()},'job_gates':{a:bound(ROOT/'actual/short_0358'/a/'GATE.json') for a in ['early','late']}}
for b in [record['migration'],record['deployment'],record['partial_release'],*record['partial_artifacts'].values(),*record['job_gates'].values()]:verify_record(b)
validate_migration(migration,deployment,record,case,bindings)
verify_hardware_prefix(migration,deployment,partial,record,bindings,runs)
write(ROOT/'audit/hardware_recovery/PREFIX_VALIDATED.json',{'passed':True,'scope':'Actual historical two-job prefix plus approved pending recovery bindings only','completed_roles':['early','late'],'recovery_outputs_validated':False,'composite_finalized':False,'process_generation_absent':True,'CUDA_allocation_absent':None,'release_state':'processes_exited_gpu_unqueryable','evidence':record,'binding_update':bound(ROOT/'audit/hardware_recovery/BINDING_UPDATE.json'),'created_unix':time.time()})
files=['finalize_composite.py','hardware_prefix.py','test_hardware_release.py','test_segmented_release.py','mf_preparation/prepare_batch.py','mf_preparation/admin/final_release.py','mf_preparation/test_preparation.py']
for f in files:ast.parse((ROOT/f).read_text())
# Independently validate every CPU-sealed MF file, source-cache identity and exact target list.
package=ROOT/'mf_preparation/batches/short_0252';seal=read(package/'SEAL.json')
for rel,sha in seal['files'].items():assert bound(package/rel)['sha256']==sha,rel
assert read(package/'configs/RUNTIME.json')['gpu']=='GPU-REDACTED'
assert read(package/'configs/EXISTING_SERVICES.json')['processes']==[]
assert read(package/'configs/EXISTING_SERVICES.json')['max_owned_active_gpus_including_selected']==1
assert read(package/'configs/PLAN.json')['new_source_trackers']==0
assert len(read(package/'cases/short_0252/INPUTS.json')['targets'])==4
write(ROOT/'audit/hardware_recovery/VERIFICATION.json',{'passed':True,'tests':44,'CPU_test_log':bound(ROOT/'audit/hardware_recovery/CPU_TESTS.log'),'syntax_checked':[bound(ROOT/f) for f in files],'actual_drink_prefix':bound(ROOT/'audit/hardware_recovery/PREFIX_VALIDATED.json'),'GPU_parser':bound(ROOT/'audit/hardware_recovery/MF_GPU_PARSER_CPU_CHECK.json'),'cabin_MF_seal':bound(package/'SEAL.json'),'sealed_files_verified':len(seal['files']),'GPU_execution':False,'network_operations':0,'browser_used':False,'created_unix':time.time()})
command='python3 finalize_composite.py --case short_0358 --migration audit/hardware_recovery/prefix_evidence/MIGRATION_MANIFEST.json --deployment audit/hardware_recovery/prefix_evidence/MIGRATION_DEPLOYMENT.json --partial-release audit/hardware_recovery/prefix_evidence/PREFIX_PARTIAL_RELEASE.json --prefix-evidence-dir audit/hardware_recovery/prefix_evidence --segment-gate actual/short_0358/recovery/SCHEDULE_RUNTIME_GATE.json --segment-complete actual/short_0358/recovery/COMPLETE.json --segment-release actual/short_0358/recovery/ROOT_EXIT_RECEIPT.json'
write(ROOT/'audit/hardware_recovery/HANDOFF.json',{'status':'CPU_READY_ACTUAL_RECOVERY_RESULTS_PENDING','changed_files':[bound(ROOT/f) for f in files if not f.startswith('test')],'binding_update':bound(ROOT/'audit/hardware_recovery/BINDING_UPDATE.json'),'verification':bound(ROOT/'audit/hardware_recovery/VERIFICATION.json'),'drink_prefix':bound(ROOT/'audit/hardware_recovery/PREFIX_VALIDATED.json'),'retained_reviews':'All existing REVIEW.json files unchanged. No synthetic target receipts written to actual/.','future_drink_finalization_command':command,'future_required_records':['Two actual split/global_weak gates and videos','Actual recovery segment SCHEDULE_RUNTIME_GATE.json','Actual recovery segment COMPLETE.json and normal ROOT_EXIT_RECEIPT.json'],'Sam_3_plus_1':'Existing planned-stop strict CUDA release validation retained; only latest global binding updated.','MF':{'cabin_seal':bound(package/'SEAL.json'),'admin_diff':bound(package/'ADMIN_DIFF.json'),'CPU_preparation':bound(package/'audit/CPU_PREPARATION.json'),'upload_after_root_review':str(package/'audit/UPLOAD_AFTER_REVIEW.sh'),'GPU_uuid':'GPU-REDACTED','trackers':4,'new_source_trackers':0,'permitted_services':[],'launch_condition':'Root authorizes only after all video services end and fresh resource admission passes. No consumer GPU launch.','global_unknown':'Non-target unavailable GPUs remain release_confirmed=false and fresh_own_cuda_absent=null; exact task PID/CUDA checks remain strict.','drink_Sam':'Not finalized; require actual segment receipts.'},'created_unix':time.time()})
h=read(ROOT/'HANDOFF.json');h['segmented_release_cpu_handoff']=bound(ROOT/'audit/hardware_recovery/HANDOFF.json');write(ROOT/'HANDOFF.json',h)
mf=read(ROOT/'mf_preparation/HANDOFF.json');mf['cabin_final_review_ready']={'seal':bound(package/'SEAL.json'),'CPU_preparation':bound(package/'audit/CPU_PREPARATION.json'),'GPU_launch_authorized':False,'condition':'Only after all videos end; root admission and launch'};mf['hardware_recovery_handoff']=bound(ROOT/'audit/hardware_recovery/HANDOFF.json');write(ROOT/'mf_preparation/HANDOFF.json',mf)
print('HANDOFF',bound(ROOT/'audit/hardware_recovery/HANDOFF.json')['sha256'])
print('VERIFICATION',bound(ROOT/'audit/hardware_recovery/VERIFICATION.json')['sha256'])
