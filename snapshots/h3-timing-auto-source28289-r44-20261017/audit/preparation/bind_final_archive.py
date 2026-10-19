"""Bind R42's completed archive without reading its outcome to set any policy."""
import hashlib,json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[2]
P=R.parent/'h3-timing-source28289-native-r42-20261017/analysis/postrun'
A=P/'captured/batch'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def put(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
expected={'CPU_COMPLETE.json':'b7b918a2eedae1fef46f0090ff9c31a306603a654622ead543c0aa15c43c3a7b','DERIVED_FILES.json':'149990fa551baee9091cd9b3ce71a3fbc0a3ee6468038ae9fb63956a76cf0b2f'}
for name,digest in expected.items():assert sha(A/name)==digest
assert read(A/'CPU_COMPLETE.json')['passed'] is True
assert read(A/'CPU_COMPLETE.json')['runs']==['r42_source_28289_seed2026101701_native']
# Verify the source pose is a certified derived artifact; result scores are not read.
derived=read(A/'DERIVED_FILES.json');rel='source_pose/source_28289_video/source_28289_video.pose.json'
assert derived[rel]==sha(A/rel)==sha(R/'configs/source.pose.json')
rows={}
for name in expected:
 dst=R/'configs'/('parent_final_'+name.lower());shutil.copyfile(A/name,dst)
 rows[str(dst.relative_to(R))]={'source':str(A/name),'sha256':sha(dst)}
c=read(R/'configs/PARENT_CLOSURE.json');c['final_archive_ready']=True;c['final_archive_note']='Root completed final archive and nonPT download; source pose certified by actual DERIVED_FILES. No target pose/score is used online.';c['final_archive_evidence']=rows
put(R/'configs/PARENT_CLOSURE.json',c)
b=read(R/'configs/observer_bindings.json')
for rel,item in rows.items():b['local_files'][rel]=item['sha256']
put(R/'configs/observer_bindings.json',b)
# The closure contains observer SHA and never recursively binds itself.
c['actual_file_sha256']['configs/observer_bindings.json']=sha(R/'configs/observer_bindings.json');put(R/'configs/PARENT_CLOSURE.json',c)
put(R/'audit/preparation/FINAL_PARENT_CLOSURE.json',{'passed':True,'source_pose_sha256':sha(R/'configs/source.pose.json'),'parent_final_evidence':rows,'parent_inventory_count':len(read(R/'configs/parent_file_inventory.json')),'no_target_pose_or_result_score_read':True,'GPU':False})
print(json.dumps({'passed':True,'final_archive_ready':True,'source_pose_sha256':sha(R/'configs/source.pose.json')}))
