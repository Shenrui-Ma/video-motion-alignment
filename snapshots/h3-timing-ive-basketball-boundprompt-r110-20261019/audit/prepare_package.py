from pathlib import Path
import json,hashlib,shutil,time,subprocess
D=Path('/Users/researcher/DevProjects');OLD=D/'h3-timing-ive-basketball-shortprompt-r109-20261019';R=D/'h3-timing-ive-basketball-boundprompt-r110-20261019';C=D/'h3-ive-basketball-shortprompt-metrics-r109-20261019'
PROMPT='Edit <Video 1> by changing only the basketball into a neon-lit basketball. Keep the original player, dribbling actions, camera framing, scene, and timing.'
OP='Replace the basketball with a neon-lit basketball.'
REMOTE='/data5/researcher/h3_runs/timing_ive_basketball_boundprompt_r110_20261019'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert not R.exists();R.mkdir()
numerical=read(OLD/'configs/runtime_kernel_hashes.json')
for rel,row in read(OLD/'deploy_manifest.json')['files'].items():
    src=OLD/rel;assert sha(src)==row['sha256'],rel
    dst=R/rel.replace('r109','r110');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    if rel not in numerical and not rel.startswith(('source_snapshot/','design/R100_ACTUAL/','configs/parent_graphs/')):
        text=dst.read_text().replace('r109','r110').replace('R109','R110').replace('timing_ive_basketball_shortprompt_r110','timing_ive_basketball_boundprompt_r110').replace(OP,PROMPT).replace('plain-exact-v1','bound-short-v1')
        dst.write_text(text)
for rel in ['inputs','input','output','temp','user','logs','processes','custom_nodes','audit/router','audit/x0']:(R/rel).mkdir(parents=True,exist_ok=True)
for p in (OLD/'inputs').iterdir():shutil.copy2(p,R/'inputs'/p.name)
for rel in numerical:assert sha(R/rel)==sha(OLD/rel)
runtime=read(R/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8574,expected_gpu_index=3,gpu_index=3,profile='host9_gpu3_r110_boundprompt_reserve8',profile_scope='R110 changes only the prompt/admin paths relative to actual R109 on the same GPU3; explicit Video1 binding and preservation wording.')
put(R/'configs/runtime.json',runtime)
P=R/'configs/prompts/short_0114_plain.txt';P.write_text(PROMPT)
s=read(R/'configs/scientific_contract.json');case=s['cases'][0];case['prompt']=PROMPT;case['prompt_sha256']=sha(P);s['scope_note']='Ordinary-only reference-bound short prompt versus actual R109 short prompt and R100 six-section prompt. All numerical runtime, initial AV noise, source and geometry are identical. Task/composition success evaluated before any timing claim.';put(R/'configs/scientific_contract.json',s)
a=read(R/'configs/parent_bindings.json');a['p1_file_sha256']=sha(P)
actual=R/'design/R109_ACTUAL';actual.mkdir()
for name,src in {'history.json':C/'incoming/history.json','gate.json':C/'incoming/gate.json','job.json':C/'incoming/job.json','COMPLETE.json':C/'incoming/COMPLETE.json','ROOT_EXIT_RECEIPT.json':C/'incoming/ROOT_EXIT_RECEIPT.json','STARTED.json':C/'incoming/STARTED.json','runtime.json':OLD/'configs/runtime.json','graph.json':OLD/'configs/graphs/r109_short_0114_seed2026101701_native.json','review.json':C/'audit/full105_review/REVIEW.json'}.items():shutil.copy2(src,actual/name)
a['r109_comparator']={'root':read(OLD/'configs/runtime.json')['remote_root'],'run_id':'r109_short_0114_seed2026101701_native','video_sha256':read(C/'incoming/gate.json')['video']['sha256'],'gate_sha256':sha(actual/'gate.json'),'records':{p.name:sha(p) for p in actual.iterdir()},'conditioning_relative':'audit/r109_short_0114_seed2026101701_native_conditioning.json','noise_relative':'audit/r109_short_0114_seed2026101701_native_noise.json'}
put(R/'configs/parent_bindings.json',a)
put(R/'configs/predecessor.json',{'root':read(OLD/'configs/runtime.json')['remote_root'],'service_pid':14789,'service_start_ticks':'2641156049','gpu_uuid':runtime['gpu_uuid'],'last_run':'r109_short_0114_seed2026101701_native'})
put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
# Prompt literal is byte-exact in graph and tests. Numerical code remains byte-equal.
graph=R/'configs/graphs/r110_short_0114_seed2026101701_native.json';g=read(graph);g['5']['inputs']['prompt']=PROMPT;put(graph,g)
assert set(g)==set(read(actual/'graph.json'))
(R/'ROOT_HANDOFF.txt').write_text('R110：明确绑定原视频的简短提示词普通编辑。\n完整prompt：'+PROMPT+'\n单因素相对R109：prompt与行政ID/path，其余数值、GPU3、原始AVnoise、20Euler、CFG1、107采样/105有效帧均相同。\n前驱R109 PID14789/start2641156049，完成后精确释放已验证。端口8574。\n先54项CPU继承测试和新增R109绑定测试，部署后fresh40GiB与真实peer准入。\n运行audit/root_run_native.py --execute --attempt root_boundprompt_attempt1 --peer-root <真实GPU0根>。\n生成完成后自动释放；核实际条件、原始noise、20NFE/0route及R109比较；消费并检查全105有效帧、人物/球/构图/镜头连续性。\n')
put(R/'audit/PREPARATION_ORIGIN.json',{'parent_seal_sha256':sha(OLD/'deploy_manifest.json'),'parent_actual_gate_sha256':sha(C/'incoming/gate.json'),'parent_review_sha256':sha(C/'audit/full105_review/REVIEW.json'),'source_prompt':OP,'new_prompt':PROMPT,'new_prompt_sha256':sha(P),'sameGPU3':True,'numerical_files_equal':list(numerical),'created_unix':time.time(),'gpu_started':False})
print(R)
