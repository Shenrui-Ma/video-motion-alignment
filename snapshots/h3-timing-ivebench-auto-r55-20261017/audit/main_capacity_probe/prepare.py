"""CPU-only preparation on the host containing the actual R54 evidence."""
import argparse,importlib.util,json,os,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('capacity_contract',HERE/'H3MainCapacityProbe/contract.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def main():
 p=argparse.ArgumentParser();p.add_argument('--parent-root',type=Path,required=True);p.add_argument('--producer-root',type=Path,required=True);p.add_argument('--run-root',type=Path,required=True);p.add_argument('--port',type=int,default=8527);a=p.parse_args()
 root=a.run_root.resolve();c.require(not root.exists(),'capacity directory must be fresh');c.require(root.is_relative_to(a.producer_root.resolve()/'audit/main_capacity_probe'),'run outside owned probe audit')
 protocol=c.read(a.producer_root/'configs/protocol.json');selected,inventory=c.select_largest(protocol['cases'],a.parent_root)
 case=next(v for v in protocol['cases'] if v['source_id']==selected['source_id']);old_graph=a.parent_root/'configs/graphs'/(case['parent_run']+'.json');parent=c.read(old_graph)
 c.require(c.sha(old_graph)==case['parent_graph_sha256'],'actual parent graph changed')
 manifest=a.parent_root/'audit/x0'/case['parent_run']/'manifest.json';cap=c.read(manifest);first=next(v for v in cap['captures'] if v['step_zero_based']==0);step0=manifest.parent/first['file']
 c.require(step0.is_file() and cap['status']=='complete','actual R54 first endpoint/complete manifest required')
 runtime=c.read(a.parent_root/'configs/runtime.json')
 for name in ('scripts','custom_nodes','input','output','temp','user','logs','audit','configs'):(root/name).mkdir(parents=True)
 shutil.copyfile(HERE/'capacity_entry.py',root/'scripts/capacity_entry.py')
 cfg={'schema':'h3-main-capacity-config-v1','run_root':str(root),'producer_root':str(a.producer_root),'source_id':case['source_id'],'parent_run':case['parent_run'],'seq_len':selected['seq_len'],'selected_by':'maximum actual packed seq_len; metadata only','all_case_seq_len':inventory,'parent_manifest':str(manifest),'parent_conditioning':selected['conditioning_file'],'parent_step0':str(step0),'parent_step0_sha256':c.sha(step0),'reserve_vram_GiB':8,'branch_count':2,'runtime':runtime,'port':a.port,'bound_files':{}}
 for path in (manifest,step0,old_graph,Path(selected['conditioning_file']),a.parent_root/'configs/runtime.json',a.producer_root/'configs/protocol.json',a.parent_root/'scripts/compatibility_bootstrap.py'):
  cfg['bound_files'][str(path)]=c.sha(path)
 cfg['bound_files'][str(root/'scripts/capacity_entry.py')]=c.sha(root/'scripts/capacity_entry.py')
 core_hashes=c.read(a.producer_root/'configs/parent_core_hashes.json')
 for relative,digest in core_hashes.items():
  path=Path(runtime['core'])/relative;c.require(c.sha(path)==digest,'actual Comfy core differs: '+relative);cfg['bound_files'][str(path)]=digest
 for relative,row in c.read(a.parent_root/'configs/runtime_kernel_hashes.json').items():
  if relative.startswith('scripts/'):
   path=a.parent_root/relative;c.require(c.sha(path)==row['current_sha256'],'actual compatibility kernel differs');cfg['bound_files'][str(path)]=row['current_sha256']
   dest=root/relative;shutil.copyfile(path,dest);cfg['bound_files'][str(dest)]=c.sha(dest)
 for ext in ('H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout','H3AutomaticWindowRouter'):
  source=a.producer_root/'extensions'/ext;c.require(source.is_dir(),'missing producer component '+ext)
  (root/'custom_nodes'/ext).symlink_to(source,target_is_directory=True)
  for path in source.rglob('*.py'):cfg['bound_files'][str(path)]=c.sha(path)
 (root/'custom_nodes/ComfyUI-KJNodes').symlink_to(runtime['kj_nodes'],target_is_directory=True)
 shutil.copytree(HERE/'H3MainCapacityProbe',root/'custom_nodes/H3MainCapacityProbe',ignore=shutil.ignore_patterns('__pycache__'))
 for path in (root/'custom_nodes/H3MainCapacityProbe').glob('*.py'):cfg['bound_files'][str(path)]=c.sha(path)
 video=a.parent_root/'input'/case['video'];c.require(c.sha(video)==case['video_sha256'],'source video changed');cfg['bound_files'][str(video)]=c.sha(video)
 # Comfy validates the real path inside its input directory; external symlinks
 # fail LoadVideo validation. A byte-identical ordinary file preserves input.
 staged_video=root/'input'/case['video'];shutil.copyfile(video,staged_video)
 c.require(not staged_video.is_symlink() and c.sha(staged_video)==case['video_sha256'],'staged source video differs');cfg['bound_files'][str(staged_video)]=c.sha(staged_video)
 # Audit nodes retain their tensor computation. This standalone contract binds
 # only this fresh capacity graph/run; it is separate from scientific R55 jobs.
 shim='''import json,hashlib\nfrom pathlib import Path\nROOT=Path(__file__).resolve().parents[1]\ndef audit_dir(value):\n p=Path(value).resolve()\n if p!=ROOT/'audit':raise ValueError('capacity audit root differs')\n return p\ndef validate_job(run_id):\n if run_id!='capacity_native_full_reserve8':raise ValueError('outside standalone capacity run')\n cfg=json.loads((ROOT/'configs/probe.json').read_text())\n if hashlib.sha256((ROOT/'configs/graph.json').read_bytes()).hexdigest()!=cfg['graph_sha256']:raise ValueError('capacity graph changed')\n return {'case':{'source_id':cfg['source_id']}}\n'''
 (root/'scripts/r55_contract.py').write_text(shim);cfg['bound_files'][str(root/'scripts/r55_contract.py')]=c.sha(root/'scripts/r55_contract.py')
 graph=c.probe_graph(parent,root,root/'configs/probe.json');shared='r55_'+case['source_id']+'_shared';graph['5']['inputs']['run_id']=shared;graph['51']['inputs']['source_run_id']=shared
 c.write_new(root/'configs/graph.json',graph);cfg['graph_sha256']=c.sha(root/'configs/graph.json');cfg['bound_files'][str(root/'configs/graph.json')]=cfg['graph_sha256'];c.write_new(root/'configs/probe.json',cfg)
 c.write_new(root/'configs/package.json',{'probe_sha256':c.sha(root/'configs/probe.json'),'graph_sha256':cfg['graph_sha256'],'scope':'two-forward capacity only; reserve8 Native equality required'})
 print(json.dumps({'prepared':str(root),'source_id':case['source_id'],'seq_len':selected['seq_len'],'profile_status':'UNMEASURED'}))
if __name__=='__main__':main()
