"""Read-only admission: verify exact release and the disposition of all R96 outputs."""
from pathlib import Path
from r103_contract import ROOT,read,sha,require

def after_release_review(root, old, audit, policy, owner):
    binding=policy.get('after_release_review')
    require(isinstance(binding,dict),'R96 completion absent and no reviewed recovery is registered')
    rel=Path(binding['file'])
    require(not rel.is_absolute() and '..' not in rel.parts,'unsafe recovery receipt path')
    path=root/rel
    require(sha(path)==binding['sha256'],'R96 recovery receipt changed')
    value=read(path)
    require(value.get('schema')=='r96-after-release-review-v1' and value.get('root_reviewed') is True,'R96 recovery was not reviewed')
    require(value['owner']==owner and value['producer_seal_sha256']==policy['producer_seal_sha256'],'R96 recovery generation differs')
    require(value['exit_sha256']==sha(audit/'ROOT_EXIT_RECEIPT.json'),'R96 recovery release binding differs')
    pending=read(audit/'RELEASED_PENDING_REVIEW.json');ledger=read(old/'audit/SCREEN_LEDGER.json')
    require(value['pending_receipt_sha256']==sha(audit/'RELEASED_PENDING_REVIEW.json') and value['ledger_sha256']==sha(old/'audit/SCREEN_LEDGER.json'),'R96 original pending evidence changed')
    require(pending.get('passed') is True and pending.get('GPU_released') is True and pending.get('all_sources_reviewed') is False,'R96 pending release state differs')
    require(value['previous_terminal_sources']==pending['terminal_sources']==ledger['rows'],'R96 prior terminal rows differ')
    reviews=value['post_release_reviews']
    require([r['source_id'] for r in reviews]==pending['remaining_sources'],'R96 pending sources not fully reviewed')
    require([r['source_id'] for r in ledger['rows']]+[r['source_id'] for r in reviews]==policy['required_terminal_sources'],'R96 source scope differs')
    for row in reviews:
        source=row['source_id'];gatefile=old/'analysis/postrun'/source/'NATIVE_RUNTIME_GATE.json';gate=read(gatefile)
        require(row['native_gate_sha256']==sha(gatefile) and gate.get('passed') is True and gate['source_id']==source,'R96 reviewed Native gate differs')
        require(gate['service_owner']=={'pid':owner['pid'],'identity':owner['identity']},'R96 reviewed Native owner differs')
        run=gate['runs']['native'];video=run['video']
        require(run['NFE']==20 and run['routed_blocks']==0 and sha(Path(video['file']))==video['sha256'],'R96 reviewed Native output differs')
        reviewpath=root/row['review_file'];require(sha(reviewpath)==row['review_sha256'],'R96 visual review changed')
        review=read(reviewpath);require(review['source_id']==source and review['reviewed_frame_count']==run['valid_frames'],'R96 visual review coverage differs')
        require(row['disposition']=='reviewed_transfer_to_followup' and row['followup_root'] and row['guided_result_pending'] is True,'R96 pending follow-up was silently closed')
        require(not (old/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json').exists(),'R96 transfer unexpectedly has a completed pair')
    return {'completion_mode':'released_reviewed_followup_pending','review_sha256':sha(path),'pending_followups':[{'source_id':r['source_id'],'root':r['followup_root']} for r in reviews]}

def check(root=ROOT,current_identity=None,compute_processes=None):
    import service
    root=Path(root);current_identity=current_identity or service.current_identity
    compute_processes=compute_processes or service.compute_processes
    p=read(root/'configs/predecessor.json');old=Path(p['remote_root']);owner=p['owner']
    require(sha(old/'deploy_manifest.json')==p['producer_seal_sha256'],'R96 predecessor seal differs')
    require(read(old/'processes/service.json')==owner,'R96 predecessor generation differs')
    audit=old/'audit'/p['attempt'];exit=read(audit/'ROOT_EXIT_RECEIPT.json')
    require(exit.get('passed') is True and exit.get('owner')==owner and exit.get('process_absent') is True and exit.get('CUDA_allocation_absent') is True,'R96 exact exit receipt incomplete')
    require(current_identity(owner['pid']) is None,'R96 registered PID still present')
    require(not any(r['pid']==owner['pid'] for r in compute_processes()),'R96 CUDA allocation still present')
    if (audit/'COMPLETE.json').exists():
        complete=read(audit/'COMPLETE.json')
        require(complete.get('passed') is True and complete.get('all_sources_reviewed') is True and complete.get('GPU_released') is True and complete.get('remaining_sources')==[],'R96 full review/release incomplete')
        require([r['source_id'] for r in complete['terminal_sources']]==p['required_terminal_sources'],'R96 terminal source set differs')
        result={'completion_mode':'completed','complete_sha256':sha(audit/'COMPLETE.json')}
    else:
        result=after_release_review(root,old,audit,p,owner)
    return {'passed':True,'owner_pid':owner['pid'],'owner_identity':owner['identity'],'exit_sha256':sha(audit/'ROOT_EXIT_RECEIPT.json'),**result}
