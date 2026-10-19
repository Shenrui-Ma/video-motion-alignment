from pathlib import Path
import hashlib,json,shutil,time
D=Path('/Users/researcher/DevProjects');P=D/'h3-timing-flexiact-p1-control-r90-20261018';T=D/'h3-flexiact-character-repair-metrics-r98-20261019';R=D/'h3-flexiact-p1-control-metrics-r90-20261019'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text());write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert not R.exists()
for directory in ['scripts','tests','configs/historical','audit']:(R/directory).mkdir(parents=True,exist_ok=True)
for source in list((T/'scripts').glob('*.py'))+list((T/'tests').glob('*.py')):
 text=source.read_text().replace('r98','r90').replace('R98','R90').replace('r90-character-repair-native-runtime-gate-v1','r90-p1-native-runtime-gate-v1').replace('historical_R66_gate_sha256','parent_R85_P0_gate_sha256')
 (R/source.relative_to(T)).write_text(text)
old=D/'h3-flexiact-expanded-metrics-r85-20261018/incoming/one_leg__movie_man_9/native.mp4'
definition=read(P/'design/CASE_DEFINITION.json');bindings=read(P/'configs/parent_bindings.json')
rt=read(P/'configs/runtime.json');run='r90_one_leg__movie_man_9_seed2026101701_native'
copies={
 'configs/producer_seal.json':P/'deploy_manifest.json','configs/producer_runtime.json':P/'configs/runtime.json',
 'configs/producer_scientific_contract.json':P/'configs/scientific_contract.json','configs/producer_graph.json':P/'configs/graphs'/f'{run}.json',
 'configs/historical/PAIR_RUNTIME_GATE.json':P/'design/R85_ACTUAL/PAIR_RUNTIME_GATE.json',
 'configs/historical/native_graph.json':P/'configs/parent_graphs/r85_actual_native.json',
 'configs/historical/native_job.json':P/'design/R85_ACTUAL/r85_one_leg__movie_man_9_seed2026101701_native_job.json',
 'configs/historical/native_history.json':P/'design/R85_ACTUAL/r85_one_leg__movie_man_9_seed2026101701_native_history.json',
}
for dst,src in copies.items():shutil.copy2(src,R/dst)
assert sha(old)==read(R/'configs/historical/PAIR_RUNTIME_GATE.json')['runs']['native']['video']['sha256']
media={'source':P/'inputs/source_one_leg_video.mp4','old_native':old,'target':P/'inputs/target_movie_man_9.webp'}
c={
 'schema':'r90-prompt-control-media-consumer-v1','producer_remote':rt['remote_root'],
 'producer_seal_sha256':sha(P/'deploy_manifest.json'),'producer_contract_sha256':sha(P/'configs/scientific_contract.json'),
 'producer_runtime_sha256':sha(P/'configs/runtime.json'),'graph_sha256':sha(P/'configs/graphs'/f'{run}.json'),
 'source_id':'one_leg__movie_man_9','run_id':run,'prompt_version':'P1','prompt':definition['prompt'],
 'expected_attempt':'root_p1_native_attempt1','media':{k:{'file':str(v),'sha256':sha(v)} for k,v in media.items()},
 'width':1152,'height':768,'total_frames':158,'valid_frames':147,'fps':24,'original_indices':list(range(0,147,3)),
 'columns':['参考动作','旧普通编辑','新版普通编辑'],
 'cross_host_limit':'R85 P0 与 R90 P1 均在 .9 GPU3 上运行，复用原始 AV noise；输入图像、参考视频、VAE、模型和20步Euler保持一致。比较完整提示词设置的变化。',
 'default_output':'/Users/researcher/Downloads/H3_R90_单腿站立_P0与P1提示词对照_20261019.html',
}
write(R/'configs/contract.json',c)
required=('producer_seal','actual_runtime_device','actual_parent_evidence_unchanged','R85_parent_gate_same_semantics','same_host_numerical_runtime','actual_history','actual_service_generation','actual_P1_condition_snapshot','original_input_pixels','actual_prepared_RGB_and_clean_VAE','actual_reference_snapshot','Qwen_visual_sampling','target_shapes_and_dtype','actual20NFE20Euler0routes','actual_native_layout','actual_reference_geometry','sampled_finite','actual_noise_cache','raw_initial_AV_noise_matches_R85')
f=R/'scripts/common.py';s=f.read_text();start=s.index('REQUIRED_CHECKS=');end=s.index('\ndef require',start);s=s[:start]+'REQUIRED_CHECKS='+repr(required)+s[end:];f.write_text(s)
f=R/'scripts/collect.py';s=f.read_text().replace("'started':r/'audit'/attempt/'STARTED.json'","'complete':r/'audit'/attempt/'COMPLETE.json','started':r/'audit'/attempt/'STARTED.json'")
s=s.replace("('started','exit','gate')","('started','exit','gate','complete')")
s=s.replace("verify_gate(rows['gate']['value']);require", "require(rows['complete']['value'].get('passed') is True and rows['complete']['value'].get('GPU_released') is True and rows['complete']['value'].get('runtime_gate_sha256')==rows['gate']['sha256'],'actual COMPLETE gate binding differs')\n verify_gate(rows['gate']['value']);require")
s=s.replace("[('gate','NATIVE_RUNTIME_GATE.json')","[('complete','COMPLETE.json'),('gate','NATIVE_RUNTIME_GATE.json')")
f.write_text(s)
f=R/'scripts/render.py';s=f.read_text()
s=s.replace('俯卧支撑角色替换修复','单腿站立提示词对照').replace('俯卧支撑：替换为目标动漫角色','单腿站立：目标西装老人动作迁移')
s=s.replace('任务：使用目标图中的短黑发男性、绿披肩和棕外套，在白色背景中完成参考视频的低伏、撑起、伸背与拱背动作。','任务：由目标图提供西装老人及环境，迁移参考视频中抬双臂、单腿站立的完整动作及其时序。')
s=s.replace('深色裤子、浅色交叉绑带、深色靴子与腰侧装备','目标图中的老人、深色西装与环境')
s=s.replace("'host_change':'41 → 9'","'host':'9 GPU3 both'")
f.write_text(s)
# Freeze the production consumer and its fixture tests before the actual output is available.
files=[x for d in ['scripts','tests','configs'] for x in (R/d).rglob('*') if x.is_file()]
write(R/'CONSUMER_FREEZE.json',{'schema':'r90-consumer-freeze-v1','files':{str(x.relative_to(R)):sha(x) for x in files},'created_unix':time.time()})
write(R/'audit/PRE_OUTPUT_REVIEW_PLAN.json',{'case':'one_leg__movie_man_9','task':'Reference image supplies elderly suited man and background; source video supplies raised-arms and one-leg balancing motion.','review_frames':list(range(147)),'source_motion_precision_seconds':0.125,'acceptance':['target identity and suit','reference image scene','complete one-leg/arms motion','physical timing of visible transitions'],'compare':'R85 P0 ordinary vs R90 P1 ordinary','guidance_calls':[0,0]})
shutil.copy2(__file__,R/'audit/prepare_consumer.py')
print(json.dumps({'root':str(R),'freeze_sha256':sha(R/'CONSUMER_FREEZE.json'),'files':len(files)}))
