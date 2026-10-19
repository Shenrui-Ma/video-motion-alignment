"""Explicit one-run recovery; read/verify old outputs, never rerun pose or sampling."""
import time
import remote_consume as m

def main():
 lock=m.locked();started=time.time();p=m.HERE/'RECOVERY_BINDING.json';spec=m.read(p);run=spec['run_id'];root,b,owner=m.bind(spec['lane'],m.HERE/'BINDING.json');arc=m.HERE/'captured'/run
 m.require(spec['authorization']=='root exact-owner finalize after immutable archive; reuse completed pose/scan','recovery authorization scope')
 m.require(run in b['runs'] and spec['binding_sha256']==m.sha(m.HERE/'BINDING.json'),'recovery live binding')
 for rel,entry in m.read(m.safe(root,b['manifest_file']))['files'].items():m.require(m.sha(m.safe(root,rel))==entry['sha256'],'recovery deployed mutation '+rel)
 m.require(not (arc/'CPU_COMPLETE.json').exists(),'recovery already complete; normal receiver must reuse')
 m.require(m.sha(arc/'RUN_GATE.json')==spec['gate_sha256'] and m.sha(arc/'FILE_INVENTORY.json')==spec['inventory_sha256'],'recovery original audit binding')
 accepted=m.verify_source_archive(root,arc,owner,run);m.require(accepted is not None and accepted['root_release_request_sha256']==spec['root_release_request_sha256'],'exact authorized release record')
 for rel,d in m.HASHES.items():m.require(m.sha(m.OLD/rel)==d,'frozen evaluation changed '+rel)
 gate=m.read(arc/'RUN_GATE.json');case=gate['case'];src=b['source_poses'][case['source_id']];source=m.safe(m.HERE,src['file']);m.require(m.sha(source)==src['sha256'],'recovery source pose binding')
 video,pp,praw,scan=m.validate_existing_analysis(arc,run,case,source,spec['derived_files'])
 m.verify_source_archive(root,arc,owner,run)
 done={'passed':True,'run_id':run,'arc':str(arc),'video':str(video),'video_sha256':m.sha(video),'pose':str(pp),'pose_sha256':m.sha(pp),'source_pose_sha256':m.sha(source),'elapsed_seconds':gate['integrity_seconds']+praw['statistics']['elapsed_s']+scan['elapsed_seconds'],'elapsed_seconds_kind':'sum recorded original integrity + pose + scan durations, not original wall','pose_seconds':praw['statistics']['elapsed_s'],'all_UNKNOWN_retained':True,'scan_summary':scan['summary'],'scan_result_sha256':m.sha(arc/'scan/RESULTS.json'),'no_GPU':True,'model_device':praw['provenance']['device'],'providers':praw['provenance']['providers'],'recovered_after_exact_root_finalize':True,'recovery_binding_sha256':m.sha(p),'recovery_verification_seconds':time.time()-started,'no_pose_or_scan_recalculation':True}
 m.save(arc/'CPU_COMPLETE.json',done);print(m.json.dumps(done))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY');raise SystemExit(75)
