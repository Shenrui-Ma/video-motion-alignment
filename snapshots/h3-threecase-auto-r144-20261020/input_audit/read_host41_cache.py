from pathlib import Path
import os,json,hashlib,time
expected={'/data4/researcher/h3_runs/ive_context_mf_20261020/cases/long_0039/source_full.mp4': 'ed29fd0615aaeee1f24f103b37bea5f18dc7daebce0159b8ff460492ca6c934c', '/data4/researcher/h3_runs/ive_context_mf_20261020/cases/long_0039/native/full.mp4': '1511941d9f441a1e8cf844285a83f5444d944b5a556a29430627202dcc2c6c23', '/data4/researcher/h3_runs/ive_context_mf_20261020/cases/long_0039/forced/full.mp4': 'abe41ece0768cb8f2925e7341e97bbe06c9d5f5d8557c42825412679b80fb886', '/data4/researcher/h3_runs/ive_reference_phase_mf_20261020/cases/long_0039/source_full.mp4': 'ed29fd0615aaeee1f24f103b37bea5f18dc7daebce0159b8ff460492ca6c934c', '/data4/researcher/h3_runs/ive_bird_aligned_mf_20261020/cases/long_0039/source_full.mp4': 'ed29fd0615aaeee1f24f103b37bea5f18dc7daebce0159b8ff460492ca6c934c', '/data4/researcher/h3_runs/ive_context_mf_20261020/cases/short_0358/source_full.mp4': 'ed48b90939dd7387f5a4e56a371394e899b600baa230740544ec75ea9fd531fd', '/data4/researcher/h3_runs/ive_context_mf_20261020/cases/short_0358/full_native/full.mp4': '04510e08e359c2b22614bc12a0fdcbfffb35e9cbcef1d0a2f0a7dbc92c069c2e', '/data4/researcher/h3_runs/ive_context_mf_20261020/cases/short_0358/full_forced/full.mp4': '362e23ac4bc864a3a7e5ec454c1eceed5f7c6ffc572067943873636ab423f935', '/data4/researcher/h3_runs/ive_r121_official_prompt_mf_20261020/cases/short_0358/source_full.mp4': 'ed48b90939dd7387f5a4e56a371394e899b600baa230740544ec75ea9fd531fd', '/data4/researcher/h3_runs/ive_reference_phase_mf_20261020/cases/long_0059/source_full.mp4': 'd8d60f728e4d4e7a8d06566689a12f7816383765f610b467476a5fe955056c79', '/data4/researcher/h3_runs/ive_reference_phase_mf_20261020/cases/long_0059/native/full.mp4': '7850f1c84cfe24a597c59f7694d733e81c625a9016e858a1aaec6bab9227ea2c', '/data4/researcher/h3_runs/ive_reference_phase_mf_20261020/cases/long_0059/guided/full.mp4': 'b46c6bb18f28ffbdcd26f2bf72c2625d999ebeead7fc371c8761d4eb5a0c5daf'}
cache=[]; inode_sha={}
def sha(p):
 st=p.stat(); k=(st.st_dev,st.st_ino)
 if k not in inode_sha:
  h=hashlib.sha256()
  with p.open('rb') as f:
   for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
  inode_sha[k]=h.hexdigest()
 return inode_sha[k]
for f,h in expected.items():
 p=Path(f); row={'file':f,'exists':p.is_file(),'expected_sha256':h}
 if p.is_file():row.update(sha256=sha(p),bytes=p.stat().st_size,sha_matches=sha(p)==h)
 cache.append(row)
base=Path('/data4/researcher/h3_runs'); roots=[p for p in base.iterdir() if p.is_dir() and any(k in p.name for k in ['r122','r123','r126','r132','context_mf','pose','observer'])]
noise=[]; poses=[];small=[]
prune={'tensor_blobs','x0','models','weights','runtime_deps','node_modules','.git','__pycache__','runtime','custom_nodes','media','pages','output','prepared','observations','counterfactual'}
for root in roots:
 for directory,dirs,files in os.walk(root,followlinks=False):
  dirs[:]=[d for d in dirs if d not in prune]
  for name in files:
   p=Path(directory)/name
   if name.endswith('.pose.json'):
    poses.append({'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
   if name.endswith('_noise.pt') and any(k in name for k in ['long_0039','short_0358','long_0059']):noise.append({'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
   if name.endswith('_noise.json') and any(k in name for k in ['long_0039','short_0358','long_0059']):
    v=json.loads(p.read_text());small.append({'file':str(p),'sha256':sha(p),'record':v})
print(json.dumps({'host':'H3_SERVER_B','utc_unix':time.time(),'cache':cache,'search_roots':[str(p) for p in roots],'excluded_directories':sorted(prune),'noise':noise,'pose_files':poses,'noise_manifests':small,'read_only':True,'GPU_started':False}))
