"""R138 exact-generation intake; retain full scans remotely, collect small evidence."""
import argparse,ast,shlex,subprocess
from common import *
from remote import read_paths,fetch
from render_native import media_info,check_time,choose_font
import render_pair,full_frame_review

# Reuse only the frozen media functions; producer/collection boundary stays here.
_helper=read(ROOT/'configs/SHARED_HELPERS.json')['consume_online.py']
require(sha(_helper['file'])==_helper['sha256'],'shared media implementation changed')
_tree=ast.parse(Path(_helper['file']).read_text())
exec(compile(ast.Module(body=[n for n in _tree.body if isinstance(n,ast.FunctionDef) and n.name in ('render_four','render')],type_ignores=[]),_helper['file'],'exec'),globals())
_render=render

def compact_remote(c):
    remote=Path(c['compact_remote_root']);script=remote/'compact_audit.py';out=remote/'ACTUAL_AUDIT_COMPACT.json'
    subprocess.run(['ssh',c['host'],'mkdir','-p',str(remote)],check=True,timeout=45)
    subprocess.run(['scp',str(ROOT/'scripts/compact_audit.py'),c['host']+':'+str(script)],check=True,timeout=45)
    args=['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1',c['remote_python'],str(script),'--input',str(Path(c['producer_remote'])/f'audit/counterfactual/{RUN}.json'),'--output',str(out)]
    subprocess.run(['ssh',c['host'],shlex.join(args)],check=True,timeout=180)
    return out

def collect(attempt):
    c=validate_static();require(attempt==c['expected_attempt'],'unregistered recovery attempt');root=Path(c['producer_remote']);dest=ROOT/'incoming/actual'
    if dest.exists():return verify_collection()
    paths={'STARTED.json':root/f'audit/{attempt}/STARTED.json','COMPLETE_REVIEW_HOLD.json':root/f'audit/{attempt}/COMPLETE_REVIEW_HOLD.json','ROOT_EXIT_RECEIPT.json':root/f'audit/{attempt}/ROOT_EXIT_RECEIPT.json','ONLINE_RUNTIME_GATE.json':root/'analysis/postrun/ONLINE_RUNTIME_GATE.json','graph.json':root/f'configs/graphs/{RUN}.json','history.json':root/f'logs/{RUN}_history.json','job.json':root/f'logs/{RUN}_job.json','x0_manifest.json':root/f'audit/x0/{RUN}/manifest.json'}
    data=read_paths([str(p) for p in paths.values()]);v={k:data[str(p)]['value'] for k,p in paths.items()};g=v['ONLINE_RUNTIME_GATE.json']
    require(g.get('passed') is True and v['ROOT_EXIT_RECEIPT.json'].get('passed') is True and v['COMPLETE_REVIEW_HOLD.json'].get('passed') is True,'actual success/release not complete')
    stage=ROOT/'audit/recovery_intake_staging'/str(time.time_ns());stage.mkdir(parents=True)
    compact=compact_remote(c);fetch(str(compact),stage/'counterfactual.json');a=read(stage/'counterfactual.json')
    counts=verify_gate(g,v['STARTED.json'],v['COMPLETE_REVIEW_HOLD.json'],v['ROOT_EXIT_RECEIPT.json'],a)
    require(v['COMPLETE_REVIEW_HOLD.json']['gate_sha256']==data[str(paths['ONLINE_RUNTIME_GATE.json'])]['sha256'],'completion gate SHA differs')
    digests={'counterfactual.json':sha(stage/'counterfactual.json')};remote_map={str(compact):'counterfactual.json'}
    def get(path,name,digest=None):
        path=safe_path(path);require(path.suffix=='.json','tensor/unregistered metadata transfer denied');target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);fetch(str(path),target)
        if digest:require(sha(target)==digest,'changed actual evidence '+name)
        digests[name]=sha(target);remote_map[str(path)]=name;return read(target)
    for name,path in paths.items():get(path,name,data[str(path)]['sha256'])
    for m in a['counterfactual']['measurements']:
        i=m['physical_index'];folder=f'observations/{i:02d}';req=get(m['request_file'],folder+'/request.json',m['request_sha256']);res=get(m['response_file'],folder+'/response.json',m['response_sha256'])
        expected_root=Path(c['old_producer_remote'] if i<9 else c['producer_remote'])
        require(Path(m['request_file']).is_relative_to(expected_root/'audit/observations') and Path(m['response_file']).is_relative_to(expected_root/'audit/observations'),'observer crossed execution generations')
        require(req['physical_index']==i and req['run_id']==(c['old_run'] if i<9 else RUN),'observer request generation differs')
        for kind in ('decode','pose'):get(res[kind]['file'],folder+'/'+kind+'.json',res[kind]['sha256'])
        observer=res['observer'];require(a['compact_receipt']['verified_remote_json_sha256'][observer['file']]==observer['sha256']==m['observer']['full_remote_record']['sha256'],'full observer remote integrity missing')
        p=stage/folder/'observer.compact.json';save(p,m['observer']);digests[str(p.relative_to(stage))]=sha(p)
        filtered=Path(res['pose']['file']);selection=get(filtered.parent/'adult_selection.json',folder+'/adult_selection.json');get(filtered.parent/'native.pose.json',folder+'/raw.pose.json',selection['raw_pose_sha256']);require(selection['filtered_pose_sha256']==res['pose']['sha256'],'raw/filtered pose differs')
        get(filtered.parent.parent/'pose_complete.json',folder+'/pose_complete.json')
        expected=next(x for x in g['raw_filtered_pose_binding'] if x['index']==i)
        require(expected['raw_sha256']==selection['raw_pose_sha256'] and expected['filtered_sha256']==selection['filtered_pose_sha256'] and expected['rejected_frames']==selection['rejected_frames'],'gate adult selection differs')
    fetch(g['video']['file'],stage/'visible_only.mp4');require(sha(stage/'visible_only.mp4')==g['video']['sha256'],'actual final output changed');digests['visible_only.mp4']=g['video']['sha256'];check_time(media_info(stage/'visible_only.mp4','/opt/homebrew/bin/ffprobe'),107,1312,736)
    save(stage/'COLLECTION.json',{'schema':'r138-recovered-online-intake-v1','attempt':attempt,'files':digests,'remote_json_to_local':remote_map,'producer_seal_sha256':c['producer_seal_sha256'],'actual_counts':counts,'original_audit':a['compact_receipt'],'roles':['source','native','fixed','visible_only'],'historical_inputs':bound(ROOT/'configs/HISTORICAL_INPUTS.json'),'valid_frames':98,'total_frames':107,'fps':24,'crop_xywh':[16,8,1280,720],'tensor_payloads_transferred':False,'GPU_started':False})
    dest.parent.mkdir(exist_ok=True);stage.rename(dest);return verify_collection()

def render():
    result=_render();collection=read(ROOT/'incoming/actual/COLLECTION.json')
    for entry in result['presentations']:
        p=Path(entry['file']);d=read(p);d.update(schema='r138-recovered-online-presentation-v1',execution_lineage={'old_completed_indices':list(range(9)),'new_completed_indices':list(range(9,20)),'same_trajectory':True,'logical_updates':20,'actual_cost':collection['actual_counts'],'failed_attempts':config()['failed_attempts']},method='R133 frozen visible-only controller continued from bitwise-verified state9; interruption after logical index8; manual source adult ROI xcenter0.40–0.75')
        save(p,d);entry.update(bound(p))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',default=config()['expected_attempt']);a=p.parse_args();collect(a.attempt);print(json.dumps(render(),ensure_ascii=False))
