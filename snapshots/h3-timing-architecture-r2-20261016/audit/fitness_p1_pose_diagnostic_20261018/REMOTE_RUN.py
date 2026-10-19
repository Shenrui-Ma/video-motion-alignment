import pathlib,json,hashlib,subprocess,time,os
r=pathlib.Path('/data5/researcher/h3_runs/timing_flexiact_fitness_cpu_diagnostic_20261018'); expected={'source_fitness_video.mp4': '168eca8e9b2ebcfcb4b61ece44730a99889726ee0106078bbd063330eb72a686', 'r72_p1_fitness.mp4': '71733e24078401854bb39056ec37a2d520082c5e2a47f7c1451e6375bab751f1'}
for n,h in expected.items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h
p=r/'CPU_RECEIPT.json';assert not p.exists(),'existing CPU receipt; inspect instead of rerun'
cmd=['/home/researcher/miniconda3/envs/comfyui/bin/python','-u','/data5/researcher/h3_runs/timing_oxygen_online_r86_20261018/scripts/pose_probe.py','--threads','2','--frame-end','146','--stride','3','--output-dir',str(r/'poses'),'--video',str(r/'source_fitness_video.mp4'),'--video',str(r/'r72_p1_fitness.mp4')]
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'); t=time.time()
with (r/'run.log').open('w') as f: a=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600)
v={'exit_code':a.returncode,'wall_s':time.time()-t,'inputs_sha256':expected,'command':cmd,'scope':'posthoc historical R72P1 diagnostic at original8fps sample times; CPU only; not new synthesis','created_unix':time.time()};p.write_text(json.dumps(v,indent=2)+'\n'); print(json.dumps(v));raise SystemExit(a.returncode)
