"""Read-only fail-closed admission for this finite, user-authorized six-arm run."""
import json,os,socket,subprocess,time,hashlib,shutil
from pathlib import Path

def preflight(root):
 root=Path(root).resolve();c=json.loads((root/'CONFIG.json').read_text())
 assert str(root)==c['root'] and str(root.parent)==c['allowed_root']
 from progress_binding import validate_progress_bindings
 progress_binding=validate_progress_bindings(root)
 assert os.getuid()==c['uid'], 'UID mismatch'
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 assert boot==c['boot_id'], 'Boot changed: require fresh inspection'
 inp=root/'input/short_0177_video.mp4'
 assert inp.is_file() and not inp.is_symlink(), 'Require lane-local real input'
 assert hashlib.sha256(inp.read_bytes()).hexdigest()==c['input_sha256'], 'Input SHA changed'
 check=subprocess.check_output(['/data3/research-user/ComfyUI/.venv/bin/python',str(root/'scripts/cpu_input_check.py'),str(root)],text=True,timeout=30,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 input_check=json.loads(check);assert input_check['passed']
 (root/'INPUT_VALIDATED.json').write_text(json.dumps(input_check,indent=2))
 mem={row.split(':')[0]:int(row.split(':')[1].split()[0]) for row in Path('/proc/meminfo').read_text().splitlines()}
 available=mem['MemAvailable']/1024**2
 assert available>=c['min_mem_available_gib'], f'Host available memory {available:.1f} GiB below admission floor'
 cg=Path('/sys/fs/cgroup/user.slice')
 assert '/user.slice/' in Path('/proc/self/cgroup').read_text(), 'Unexpected cgroup membership'
 cs={k:int(v) for k,v in (line.split() for line in (cg/'memory.stat').read_text().splitlines())}
 current=int((cg/'memory.current').read_text());limit=int((cg/'memory.max').read_text())
 headroom=(limit-current+min(current,cs['inactive_file']))/1024**3
 assert headroom>=c['min_cgroup_headroom_gib'], f'Shared cgroup working-set headroom {headroom:.1f} GiB below admission floor'
 disk=shutil.disk_usage(root).free/1024**3
 assert disk>=c['min_disk_free_gib'], 'Insufficient output disk space'
 load=os.getloadavg()[0];cpus=os.cpu_count()
 assert load<cpus*c['max_load_cpu_fraction'], 'Host CPU admission load exceeded'
 query=['nvidia-smi','--id='+c['gpu_uuid'],'--query-gpu=uuid,pci.bus_id,temperature.gpu,power.limit,utilization.gpu,memory.free','--format=csv,noheader,nounits']
 values=[v.strip() for v in subprocess.check_output(query,text=True,timeout=20).strip().split(',')]
 assert values[0]==c['gpu_uuid'], 'GPU UUID mismatch'
 temp,cap,util,free=map(float,values[2:])
 assert cap==450 and temp<c['max_temperature_c'] and free>=c['min_gpu_free_mib'] and util<=5, 'GPU health/free/idle gate failed: '+str(values)
 apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=20)
 assert not any(row.split(',')[0].strip()==c['gpu_uuid'] for row in apps.splitlines()), 'Selected GPU occupied'
 with socket.socket() as sock:
  sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);sock.bind(('127.0.0.1',c['port']))
 result={'checked_unix':time.time(),'boot_id':boot,'uid':os.getuid(),'gpu':values,'available_mem_gib':available,'cgroup_headroom_gib':headroom,'cgroup_memory_max_bytes':limit,'cgroup_memory_current_bytes':current,'progress_binding':progress_binding,'free_disk_gib':disk,'load1':load,'cpus':cpus,'passed':True}
 p=root/'ADMISSION.json';p.write_text(json.dumps(result,indent=2))
 return result
if __name__=='__main__':
 import sys
 print(json.dumps(preflight(Path(sys.argv[1]))))
