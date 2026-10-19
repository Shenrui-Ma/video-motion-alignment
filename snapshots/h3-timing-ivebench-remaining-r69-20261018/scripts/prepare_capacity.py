"""Create a fresh isolated capacity graph using the exact selected runtime profile."""
import argparse,copy,json,shutil
from pathlib import Path
from r69_contract import ROOT,read,sha,require,registry

def prepare(root=ROOT):
 root=Path(root);runtime=read(root/'configs/runtime.json');require(root.resolve()==Path(runtime['remote_root']),'exact remote root required')
 out=root/'audit/capacity_probe'/runtime['profile'];require(not out.exists(),'capacity attempt exists; retain its evidence')
 for name in ('scripts','custom_nodes','input','output','temp','user','logs','audit','configs'):(out/name).mkdir(parents=True)
 jobs,order=registry(root);case=jobs[order[0]]['case'];run='r69_capacity_'+case['source_id'];source=root/'inputs'/case['video']
 require(sha(source)==case['video_sha256'],'input changed');shutil.copyfile(source,out/'input'/case['video'])
 for name in ('compatibility_bootstrap.py','backend_dispatch_audit.py','int8_row_chunking.py','process_identity.py','probe_guards.py','capacity_entry.py'):shutil.copyfile(root/'scripts'/name,out/'scripts'/name)
 for name in ('H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout','H3CapacityProbe'):(out/'custom_nodes'/name).symlink_to(root/'extensions'/name,target_is_directory=True)
 (out/'custom_nodes/ComfyUI-KJNodes').symlink_to(runtime['kj_nodes'],target_is_directory=True)
 cfg={'schema':'r69-capacity-config-v1','producer_root':str(root),'run_root':str(out),'runtime':runtime,'port':8530,'run_id':run,'source_id':case['source_id'],'parent_capture':str(root/'configs/R54_evidence'/case['source_id']/'captures.json'),'bound_files':{}}
 g=copy.deepcopy(read(root/'configs/graphs'/(order[0]+'.json')))
 for n,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit')]:g[n]['inputs'][key]=str(out/suffix)
 for n in ('6','50','51'):g[n]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']=run
 g['52']={'class_type':'H3CapacityProbe','inputs':{'model':['50',0],'config_file':str(out/'configs/probe.json')}}
 (out/'configs/graph.json').write_text(json.dumps(g,indent=2)+'\n')
 shim="""import json,hashlib\nfrom pathlib import Path\nROOT=Path(__file__).resolve().parents[1]\ndef sha(p):\n h=hashlib.sha256()\n with Path(p).open('rb') as f:\n  for c in iter(lambda:f.read(1048576),b''):h.update(c)\n return h.hexdigest()\ndef audit_dir(value):\n if Path(value)!=ROOT/'audit':raise ValueError('probe audit path differs')\n return Path(value)\ndef validate_job(run):\n cfg=json.loads((ROOT/'configs/probe.json').read_text())\n if run!=cfg['run_id']:raise ValueError('probe run differs')\n return {'case':{'source_id':cfg['source_id']}}\ndef validate_router(mode,alpha,radius,offset,start,end,bs,be,ss,se,run,audit):\n validate_job(run)\n if (mode,alpha,radius,offset,start,end,bs,be,ss,se)!=('native',1.,0,0,0,89,0,50,0,20):raise ValueError('probe router differs')\n if Path(audit)!=ROOT/'audit/router':raise ValueError('probe router root differs')\n"""
 (out/'scripts/r69_contract.py').write_text(shim)
 paths=[root/'configs/runtime.json',source,Path(cfg['parent_capture']),out/'configs/graph.json']
 paths+=list((out/'scripts').glob('*.py'))+list((root/'extensions').rglob('*.py'))
 for name,digest in read(root/'configs/parent_core_hashes.json').items():
  p=Path(runtime['core'])/name;require(sha(p)==digest,'actual Comfy core changed');paths.append(p)
 for p in paths:cfg['bound_files'][str(p)]=sha(p)
 (out/'configs/probe.json').write_text(json.dumps(cfg,indent=2)+'\n')
 return out
if __name__=='__main__':
 argparse.ArgumentParser(description=__doc__).parse_args();print(prepare())
