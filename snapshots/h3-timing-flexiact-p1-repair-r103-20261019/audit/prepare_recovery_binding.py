from pathlib import Path
import json,hashlib,shutil,time
R=Path(__file__).resolve().parents[1]
C=R.parent/'h3-ive-native-screen-metrics-r96-20261018/audit/recovery_full_review_long0174'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
a=read(R/'audit/R96_ACTUAL_RECOVERY.json');f=a['files'];policy=read(R/'configs/predecessor.json')
assert policy['owner']==f['processes/service.json']['value']
assert policy['producer_seal_sha256']==f['deploy_manifest.json']['sha256']
folder=R/'design/post_release';folder.mkdir(exist_ok=True)
for name in ['REVIEW.json','FRAME_LEDGER.json']:shutil.copy2(C/name,folder/name)
gate=f['analysis/postrun/long_0174/NATIVE_RUNTIME_GATE.json']['value']
assert gate['passed'] and gate['runs']['native']['valid_frames']==145
receipt={'schema':'r96-after-release-review-v1','root_reviewed':True,'created_unix':time.time(),'owner':policy['owner'],'producer_seal_sha256':policy['producer_seal_sha256'],'exit_sha256':f['audit/root_native_screen_attempt1/ROOT_EXIT_RECEIPT.json']['sha256'],'pending_receipt_sha256':f['audit/root_native_screen_attempt1/RELEASED_PENDING_REVIEW.json']['sha256'],'ledger_sha256':f['audit/SCREEN_LEDGER.json']['sha256'],'previous_terminal_sources':f['audit/SCREEN_LEDGER.json']['value']['rows'],'post_release_reviews':[{'source_id':'long_0174','native_gate_sha256':f['analysis/postrun/long_0174/NATIVE_RUNTIME_GATE.json']['sha256'],'review_file':'design/post_release/REVIEW.json','review_sha256':sha(folder/'REVIEW.json'),'frame_ledger_sha256':sha(folder/'FRAME_LEDGER.json'),'disposition':'reviewed_transfer_to_followup','followup_root':'/data4/researcher/h3_runs/timing_ive_long0174_guidance_r107_20261019','guided_result_pending':True}],'scope':'Lifecycle admission only. Original R96 pending receipt, four-row ledger, timeout state and missing COMPLETE remain unchanged. The fifth Native was reviewed after release; matching guidance is still pending in R107.'}
path=folder/'AFTER_RELEASE_REVIEW.json';assert not path.exists();write(path,receipt)
policy['after_release_review']={'file':str(path.relative_to(R)),'sha256':sha(path)}
write(R/'configs/predecessor.json',policy)
old=R/'deploy_manifest.json';shutil.copy2(old,R/'audit/deploy_manifest_before_recovery.json')
print(sha(path))
