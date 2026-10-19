from pathlib import Path
import sys,json,time,hashlib,subprocess
r=Path("/data5/researcher/h3_runs/timing_source28289_native_r42_20261017")
sys.path.insert(0,str(r/"scripts"));import service
old=Path("/data5/researcher/h3_runs/timing_manual_source51310_r41_20261017")
cleanup=json.loads((old/"processes/cleanup.json").read_text())
assert cleanup.get("process_absent") is True and cleanup["service_record"]["pid"]==11676
assert not Path("/proc/11676").exists()
peer=Path("/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017")
po=json.loads((peer/"processes/service.json").read_text())
assert po["pid"]==16635
identity=service.external_identity(16635)
assert identity=={"uid":1016,"start_ticks":"2623514879","cmdline_sha256":"850af6280946af017471126c5ab5116c554b5d34d3e934bb7e4f1f4a896b13b6"}
a={"ready_for_launch":True,"scope":"own_user_video_jobs","existing_comfy_port":None,"permitted_compute_processes":[{"pid":16635,"identity":identity}]}
processes=service.compute_processes();service.check_admission(a,processes,{"queue_running":[],"queue_pending":[]})
service.write_json(r/"audit/root_live_admission.json",{"unix":time.time(),"old_cleanup":cleanup,"processes":processes,"admission":a})
service.write_json(r/"configs/admission.json",a)
subprocess.run(["python3","scripts/preflight.py","--live"],cwd=r,check=True)
subprocess.run(["python3","-u","scripts/launch_remote.py","--service-only"],cwd=r,check=True)
