from pathlib import Path
import json,hashlib,os,subprocess,time
core=Path('/data3/researcher/h3_runs/silverwolf_486_ref2va4_clean/ComfyUI')
expected={'comfy/ldm/minimax/model.py': '0d5edcf32b4b98d704eaa51de60ed71f507d0c7d9845947f566647dc76fb8dfe', 'comfy/ldm/modules/attention.py': '9cafaafaf93ff53e8cbefb5e4a204014019985df2da8c1996bf40f1235fc2960', 'comfy/model_base.py': '6280712f8315f00f19a1ada53e48bf243c818b017fa751b3412092fa0f381e68', 'comfy/model_patcher.py': '26da6710a7d84e8e98ea3e0f0bc07b88cfef3f99a7f7d59daa71e650512c6ed4', 'comfy_extras/nodes_minimax_h3.py': '62ec72d4f3b879640dbd41b959a6c1112a82b77478509323094f49dae17fffdb', 'comfy/model_sampling.py': '8afdc665272589a567792bb652389df7d4a83f69574c2b7e5b3d533d55592990', 'comfy/samplers.py': 'f2c264ca9d394612f828e3ffe167c856a278a10e1711b269f0ba65dccb66393f', 'comfy/ldm/minimax/vae.py': '40c4bf2db63279e0d13eb8de2c8a4602207a90cf9350f94afbee7aeed8b757ea', 'comfy/text_encoders/qwen3vl.py': '1004f4184c8ca5da74e4147a706bc4f1c9bd1a19ae63db74f3cab88ded0f0255'}
rows={}
for name,digest in expected.items():
 p=core/name;b=p.read_bytes();actual=hashlib.sha256(b).hexdigest();rows[name]={'sha256':actual,'matches_host9':actual==digest}
models=Path('/data3/researcher/ComfyUI-H3/models')
modelrows={}
for sub in ['diffusion_models','text_encoders','vae']:
 for p in (models/sub).glob('*minimax*h3*'):
  if p.is_file():
   stat=p.stat();modelrows[str(p.relative_to(models))]={'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns,'realpath':str(p.resolve())}
raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True)
compute=[]
for line in raw.splitlines():
 gpu,pid,mem=[x.strip() for x in line.split(',')];compute.append({'gpu_uuid':gpu,'pid':int(pid),'memory_mib':mem,'uid':(Path('/proc')/pid).stat().st_uid})
print(json.dumps({'utc_unix':time.time(),'uid':os.getuid(),'core':str(core),'core_files':rows,'model_stat':modelrows,'compute':compute,'available_cpu':os.cpu_count()},indent=2))
