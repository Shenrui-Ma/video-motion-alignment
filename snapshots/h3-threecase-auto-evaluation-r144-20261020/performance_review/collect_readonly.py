"""Read existing .41 code, CPU-visible package metadata, and saved step timings."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REMOTE = r'''
import json,hashlib,sys,subprocess,importlib.metadata as md
from pathlib import Path
import onnxruntime as ort
import torch
root=Path('/data4/researcher/h3_runs/threecase_auto_r144_20261020/cases/short_0358_cached_gpu2')
report={'python':sys.executable,'onnxruntime':{'version':ort.__version__,'file':ort.__file__,'available_providers':ort.get_available_providers()},'torch':{'version':torch.__version__,'file':torch.__file__,'build_cuda':torch.version.cuda},'distributions':{},'sources':{},'steps':[]}
for dist in md.distributions():
 name=dist.metadata.get('Name','')
 if name in ('onnxruntime','onnxruntime-gpu','torch','opencv-python','numpy') or name.startswith('nvidia-'):
  report['distributions'][name]=dist.version
aux=Path('/data3/researcher/ComfyUI/custom_nodes/comfyui_controlnet_aux/src/custom_controlnet_aux/dwpose')
for p in [aux/'dw_torchscript/jit_pose.py',aux/'dw_onnx/cv_ox_det.py']:
 data=p.read_bytes();report['sources'][str(p)]={'sha256':hashlib.sha256(data).hexdigest(),'content':data.decode()}
for request in sorted((root/'audit/observations').glob('*/request.json')):
 r=json.loads(request.read_text())
 if r.get('physical_index',99)>4:continue
 d=request.parent;row={'directory':str(d),'physical_index':r['physical_index'],'request_id':r['request_id']}
 for name in ('response.json','pose_complete.json','native.json','observer.json','pose/native.pose.json'):
  p=d/name
  if not p.is_file():continue
  data=p.read_bytes();obj=json.loads(data)
  if name=='pose/native.pose.json':obj={k:obj.get(k) for k in ('video','provenance','extraction','statistics')}
  elif name=='observer.json':obj={k:obj.get(k) for k in ('scan_seconds','complete_scan','physical_index','source_pose_sha256','edited_pose_sha256')}
  elif name=='response.json':
   obj={**{k:obj.get(k) for k in ('status','wall_seconds','decoder_stage_seconds','outer_admission_wait_seconds','physical_index')},'pose_process_wall_seconds':obj.get('pose_process',{}).get('wall_seconds')}
  elif name=='native.json':
   obj={k:v for k,v in obj.items() if not isinstance(v,(dict,list))}
  row[name]={'file':str(p),'sha256':hashlib.sha256(data).hexdigest(),'data':obj}
 report['steps'].append(row)
cuda_lib=Path(ort.__file__).parent/'capi/libonnxruntime_providers_cuda.so'
report['ort_cuda_shared_library']={'file':str(cuda_lib),'exists':cuda_lib.is_file()}
if cuda_lib.is_file():
 result=subprocess.run(['ldd',str(cuda_lib)],capture_output=True,text=True,timeout=10)
 report['ort_cuda_shared_library'].update(ldd_returncode=result.returncode,ldd=result.stdout+result.stderr)
report['torch_cuda_initialized']=torch.cuda.is_initialized()
print(json.dumps(report,ensure_ascii=False))
'''


def main():
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
         "H3_SERVER_B",
         "CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 "
         "PYTHONPATH=/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps "
         "/data3/researcher/ComfyUI/.venv/bin/python -"],
        input=REMOTE, capture_output=True, text=True, check=True, timeout=45,
    )
    record = json.loads(result.stdout)
    (ROOT / "HOST41_READONLY.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    for path, source in record["sources"].items():
        (ROOT / Path(path).name).write_text(source["content"])
    print(json.dumps({
        "providers": record["onnxruntime"]["available_providers"],
        "torch": record["torch"]["version"], "cuda_initialized": record["torch_cuda_initialized"],
        "steps": len(record["steps"]),
        "missing_cuda_libraries": [
            line.strip() for line in record["ort_cuda_shared_library"].get("ldd", "").splitlines()
            if "not found" in line],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
