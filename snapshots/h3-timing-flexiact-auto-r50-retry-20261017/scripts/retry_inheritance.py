"""Verify exact original science and explicit administrative relocation of this retry."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)
def specification(root=ROOT):
    root=Path(root);spec=read(root/'configs/retry/inheritance.json');manifest_path=root/'configs/retry/base_deploy_manifest.json'
    require(sha(manifest_path)==spec['base_deploy_manifest_sha256'],'retry base manifest differs')
    # CPU staging directories on the server use the same preserved producer.
    base=Path(spec['base_local_root'])
    if not base.exists():base=Path(spec['base_remote_root'])
    require(sha(base/'deploy_manifest.json')==spec['base_deploy_manifest_sha256'],'original producer seal differs')
    return spec,base,read(manifest_path)
def inherited_file(root,rel,expected):
    root=Path(root);spec,base,manifest=specification(root)
    require(sha(base/rel)==expected==manifest['files'][rel]['sha256'],'original inherited file differs: '+rel)
    if rel in spec['graph_path_changes_only']:
        require((root/rel).read_text().replace(spec['retry_remote_root'],spec['base_remote_root'])==(base/rel).read_text(),'graph change exceeds audit path relocation: '+rel)
    else:require(sha(root/rel)==expected,'scientific bytes changed: '+rel)
def check(root=ROOT,inputs=True):
    root=Path(root);spec,base,manifest=specification(root);bookkeeping=set(spec['bookkeeping_files']);resource=set(spec['resource_files']);relocated=set(spec['relocated_files']);protocols=set(spec['protocol_resource_only_files']);counts={'exact':0,'resource':0,'relocated':0,'bookkeeping':0,'protocol_resources':0}
    for rel,row in manifest['files'].items():
        require(sha(base/rel)==row['sha256'],'frozen base producer changed: '+rel)
        if rel in bookkeeping:counts['bookkeeping']+=1;continue
        if rel in resource:
            text=(root/rel).read_text()
            if rel=='extensions/H3AutomaticWindowRouter/transport.py':
                text=text.replace("PROTOCOL_SHA='"+spec['current_protocol_sha256']+"'", "PROTOCOL_SHA='"+spec['protocol_sha256']+"'")
            require(hashlib.sha256(text.encode()).hexdigest()==spec['resource_candidate_after_sha256'][rel],'resource patch differs from reviewed candidate: '+rel);counts['resource']+=1
        elif rel in protocols:
            old,current=read(base/rel),read(root/rel)
            require({k:v for k,v in old.items() if k!='resources'}=={k:v for k,v in current.items() if k!='resources'},'scientific protocol changed: '+rel)
            require(current['resources']==spec['resources_expected'],'unreviewed resource protocol changed: '+rel)
            require(sha(root/rel)==spec['current_protocol_sha256'],'current protocol seal differs: '+rel);counts['protocol_resources']+=1
        elif rel in relocated:
            require((root/rel).read_text().replace(spec['retry_remote_root'],spec['base_remote_root'])==(base/rel).read_text(),'relocation changed more than paths: '+rel);counts['relocated']+=1
        else:require(sha(root/rel)==row['sha256'],'unapproved original file change: '+rel);counts['exact']+=1
    require(sha(base/'configs/protocol.json')==spec['protocol_sha256'],'original scientific protocol changed')
    if inputs:
        for name,digest in read(root/'configs/input_hashes.json').items():require(sha(root/'inputs'/name)==digest,'retry input changed: '+name)
    return {'status':'pass','base_manifest_sha256':spec['base_deploy_manifest_sha256'],'protocol_byte_exact':False,'protocol_scientific_fields_exact':True,'resources_only_change':True,'counts':counts,'scientific_policy':'same delayed-only policy, same five cases and original seeds','new_runtime_GPU_gates':'root must execute dedicated decoder and resource admission'}
if __name__=='__main__':print(json.dumps(check(),indent=2))
