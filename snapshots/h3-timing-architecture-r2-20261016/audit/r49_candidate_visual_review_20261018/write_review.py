from pathlib import Path
import json,hashlib
r=Path(__file__).parent
source=json.loads((r/'INTEGRITY_AND_FRAMES.json').read_text())
rotate=[
 {'source_frames24':[12,18],'seconds':[.5,.75],'event':'双手胸前，从一侧转体经过朝前位置','native':'同时间也经过朝前，双手和肘部动作阶段接近'},
 {'source_frames24':[33,42],'seconds':[1.375,1.75],'event':'向画面左侧转到一端，随后准备回转','native':'同区间达到相同一侧，未观察到明显独立停顿或持续晚到'},
 {'source_frames24':[54,63],'seconds':[2.25,2.625],'event':'从左侧回到正面附近，再向另一侧转','native':'同区间回中，肘/胸的细节形状存在差异；未建立精确帧级lag'},
 {'source_frames24':[75,87],'seconds':[3.125,3.625],'event':'向画面右侧转到另一端','native':'同区间也转到这一侧，腿保持分开、双手始终胸前'},
 {'source_frames24':[126,132],'seconds':[5.25,5.5],'event':'再次转到画面左侧一端，随后回转','native':'相同阶段出现；全片动作顺序保持'},
]
crouch=[
 {'source_frames24':[12,18],'seconds':[.5,.75],'event':'第一次屈膝下蹲开始，同时抬手','native':'仍直立，主要出现单臂向外抬起，动作内容不同'},
 {'source_frames24':[33,51],'seconds':[1.375,2.125],'event':'第一次深蹲低位保持','native':'仍站立，单臂伸出后收回；第一轮下蹲未在该阶段发生'},
 {'source_frames24':[72,87],'seconds':[3.,3.625],'event':'已起身到站立状态，双手胸前','native':'站立且双手胸前，但此前动作历史不同'},
 {'source_frames24':[108,126],'seconds':[4.5,5.25],'event':'第二轮下蹲低位','native':'4.5–4.875s目标男人也下蹲；4.875–5.0s间人物衣着和场景突变，5.0s起源灰衣人物/码头样式重新出现'},
 {'source_frames24':[132,144],'seconds':[5.5,6.0],'event':'从第二次下蹲起身，末尾接近站直','native':'继续保持低位，且已是源人物样式；不把这段误差归为纯时延'},
]
review={
 'kind':'exploratory agent visual review of existing completed outputs',
 'source_resolution_seconds':.125,'reviewed_frames24':list(range(0,147,3)),
 'scope':'all49 source instants covering complete6.125s valid prefix; generated two intermediate frames per source step not individually annotated; final11 padding frames excluded',
 'human_event_ground_truth':False,'GPU_calls':0,
 'rotate':{'requested_pair_exists':True,'actual_target':'game_girl_1.webp','task':'target appearance sustained and broad repeated torso rotation preserved','timing':'no clear sustained timing displacement at reviewed grid; acceptable normal-synchrony control','events':rotate,'can_reuse_as_R85_P1_baseline':False,'reason':'R49 uses original generic P0; R85 fresh P1 Native and forced require their own actual paired conditions/noise'},
 'crouch':{'requested_pair_exists':False,'requested_target':'movie_man_5.jpg','actual_target':'movie_man_4.jpg','task':'target identity initially present but not sustained; first squat absent and late source identity/scene returns','timing':'gross motion/identity failure, pure lag attribution unsupported','events':crouch,'can_reuse_as_R85_baseline':False,'reason':'different target and prompt; no completed R49 movie_man_5 output exists'},
 'integrity_evidence':str(r/'INTEGRITY_AND_FRAMES.json'),
 'noise_verification_scope':'Stored actual AV tensor hashes plus original PASS runtime gate. Large noise/PT blobs were not downloaded/rehashed in this review.',
}
(r/'REVIEW.json').write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n')
report='''R49 rotate / crouch 旧成片审查

实际配对与可复用性
- rotate → game_girl_1.webp：存在完整Native，目标盔甲人物与重复转体动作基本完成，适合保留为正常同步对照。49个源时刻内未见清楚、持续的整体延后。
- crouch → movie_man_5.jpg：R49没有该配对成片。实际是 movie_man_4.jpg。旧片起初换成海边男人，第一轮下蹲缺失；约5s又恢复源灰衣人物/码头，动作和身份任务均不稳定。
- R85新movie5目标需要自己的Native。rotate虽是同目标，R49使用通用P0，R85预定P1；新Native/forced仍需新成对验证。旧片可作为历史与正常对照参考，不能直接替换新P1普通编辑。

实际运行与输入完整性
两条来自.9（H3_SERVER_A），GPU UUID ea95cb74-d802-152e-e921-61e0d65470a3，实际服务PID45686/start_ticks2625167040，port8511。原RUN_GATE、RUNTIME_GATE、CPU_COMPLETE均PASS。
每条本地13项相关图、输入、provenance、history、条件/noise收据、输出等与归档SHA匹配，合计26/26。原门确认实际20forward、0router写入、实际条件存储/有限性/布局及noise。两条seed2026101701；实际video noise SHA f7a7edfeb5783649641d64e37bc3ca6d7fcfed8a477352f73b2151e7daece880，audio noise SHA 9b0b35c3eed0bcb48d650bd7109aa4502df60ce17f471fd5508a970028e915ff。当前审查复核的是已有实际收据和门；大PT保留远端，没有重新拉取或重算。
完整原成片158帧，1152×768@24fps；有效147帧=6.125秒，末11帧尾部padding。官方原视频49帧@8fps，每帧在准备输入中重复3次。四份source/Native视频均核158帧、PTS=i/24。

视觉判读方法
使用全49个源物理时刻0,0.125,…6.000秒，并对齐Native相同帧3i。每例7页双列图，左source、右Native。查看完整有效跨度和各转向/下蹲转换附近。未逐一标注每两个源时刻之间的额外生成帧；源事件边界只具有约125ms分辨率。以下为查看旧结果后的探索性人工语义判读，未拟合引导窗口，不是预注册event真值。

rotate五个可复核事件（原24fps帧号）
1. f12–18 / 0.500–0.750s：从一侧转体经过正面；Native同区间经过正面。
2. f33–42 / 1.375–1.750s：向画面左侧转到一端；Native同区间达同一侧。
3. f54–63 / 2.250–2.625s：从左侧回到正面后继续转；Native阶段接近。
4. f75–87 / 3.125–3.625s：向画面右侧转到另一端；Native阶段接近。
5. f126–132 / 5.250–5.500s：再次到左侧一端后回转；Native保持相同顺序。
盔甲、发型和目标女性外观持续出现；双手胸前/分腿/左右转体保持。部分肘/手位置和形状有差异，目前没有据此确认小动作缺失或精确lag。完整正常例仍应保留。

crouch五个可复核事件（实际movie_man_4）
1. f12–18 / 0.500–0.750s：源开始屈膝、抬手；Native直立并抬单臂。
2. f33–51 / 1.375–2.125s：源第一次深蹲低位；Native站立单臂伸出/收回，第一轮未发生。
3. f72–87 / 3.000–3.625s：源已站起，双手胸前；Native也站立，之前动作内容不同。
4. f108–126 / 4.500–5.250s：源第二次低位；Native目标男人在4.5–4.875s下蹲，4.875–5.0s间身份/衣着/场景突变为源人物样式。
5. f132–144 / 5.500–6.000s：源第二次起身；Native保持低位且身份已漂移。
这支持动作内容与身份保持失败；不能把首次蹲下晚出现解释成整段统一延后，也不能代表新movie_man_5会失败。

优先级建议
rotate先用于确认新P1配对能持续完成换人及正常同步时是否受固定引导损害；其旧片不提供“明显时序故障”的依据。crouch/movie5是值得先看Native任务完成的目标泛化测试，旧movie4只能提示要核全片身份与两轮完整下蹲。

文件
R49归档根：/Users/researcher/DevProjects/h3-timing-flexiact-native-r49-20261017/analysis/postrun/captured/batch/
原图/准备视频：inputs/source_{rotate,crouch}_{portrait.webp或portrait.jpg,video.mp4}。
实际输出：output/r49_source_rotate_seed2026101701_native_00001_.mp4（SHA80b8b754…34aed5）；output/r49_source_crouch_seed2026101701_native_00001_.mp4（SHAd2037ca2…55d1c0）。
本目录INTEGRITY_AND_FRAMES.json列确切绝对路径、逐文件SHA、原noise与运行证据；REVIEW.json列所有事件区间与结论；{rotate,crouch}_all49_page01…07.jpg是完整49点对照。
'''
(r/'REPORT.txt').write_text(report)
manifest={'scope':'new read-only review artifacts; all original R49 files unchanged','files':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(r.iterdir()) if p.is_file() and p.name!='MANIFEST.json']}
(r/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('REPORT',hashlib.sha256((r/'REPORT.txt').read_bytes()).hexdigest());print('REVIEW',hashlib.sha256((r/'REVIEW.json').read_bytes()).hexdigest())
