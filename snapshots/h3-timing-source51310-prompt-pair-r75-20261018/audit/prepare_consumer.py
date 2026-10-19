from pathlib import Path
R=Path(__file__).resolve().parents[1]
P=R.parent/'h3-timing-flexiact-prompt-pair-r72-20261018/audit/consumer'
D=R/'audit/consumer';D.mkdir(exist_ok=True)
for name in ('common.py','collect.py','watch_remote.py','sync_publish.py','presentation.py','test_consumer.py'):
 s=(P/name).read_text().replace('r72','r75').replace('R72','R75')
 if name=='common.py':
  s=s.replace("PAIRS = ('fitness__game_man_5', 'one_leg__movie_man_9')","PAIRS = ('source_51310',)")
  s=s.replace('147, 158, 24, 1152, 768','141, 141, 24, 1312, 736')
  s=s.replace("HOST = 'H3_SERVER_B'","HOST = 'H3_SERVER_A'")
  s=s.replace('/data3/researcher/h3_runs/timing_flexiact_prompt_pair_r75_20261018','/data5/researcher/h3_runs/timing_source51310_prompt_pair_r75_20261018')
  s=s.replace('/data3/researcher/ComfyUI/.venv/bin/python','/home/researcher/miniconda3/envs/comfyui/bin/python')
  s=s.replace('/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps','/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps')
  s=s.replace('/data3/researcher/h3_runs/timing_architecture_r2_20261016','/data5/researcher/h3_runs/timing_architecture_r2_20261016')
  s=s.replace('list(range(0, 147, 3))','list(range(141))').replace("row['evaluation_fps'] == 8","row['evaluation_fps'] == 24")
  s=s.replace("'independent_prompt_conditioning'):","'independent_prompt_conditioning', 'original_AV_noise_exact', 'original_raw_input_video_exact'):")
 if name=='collect.py':s=s.replace('design/PAIR_DEFINITIONS.json','design/CONTROL_DESIGN.json')
 if name=='sync_publish.py':
  s=s.replace("['rsync', '-a',", "['rsync', '-a', '-e', 'ssh -o ConnectTimeout=15 -J H3_SERVER_B',")
  s=s.replace("['scp', '-q', '-o', 'ConnectTimeout=10',", "['scp', '-q', '-o', 'ConnectTimeout=15', '-o', 'ProxyJump=H3_SERVER_B',")
 if name=='presentation.py':
  s=s.replace("TITLES = {'fitness__game_man_5': '举臂健身 · 红金装甲人物', 'one_leg__movie_man_9': '单腿平衡 · 深色西装人物'}", "TITLES = {'source_51310': '夜间球场舞蹈 · Sam Altman'}")
  s=s.replace('H3_FlexiAct_两组P0_P1提示适配对照_20261018.html','H3_Source51310_Sam_P0_P1提示协议对照_20261018.html')
  s=s.replace('source_p0_p1_full147.mp4','source_p0_p1_full141.mp4').replace('576, 384, 432','656, 368, 416')
  s=s.replace('人物外观与环境来自这张图。三栏最左侧视频提供动作及其时间顺序。','目标人物身份来自这张图；灰色长袖、深色长裤按任务指定。动作、镜头和背景来自左侧参考视频。')
  s=s.replace("'H3_FlexiAct_' + pair + '_P0_P1完整147帧_20261018.mp4'","'H3_Sam_' + pair + '_P0_P1完整141帧_20261018.mp4'")
  s=s.replace('H3 FlexiAct 提示适配对照','H3 Sam 提示协议对照').replace('H3 · FlexiAct 角色替换提示适配','H3 · Sam 角色替换提示协议对照')
  s=s.replace('两组预先固定的官方源视频与目标人物配对。每组依次展示动作参考视频、P0 原始指令编辑、P1 按 H3 协议整理的指令编辑。保留 147 个有效帧，共 6.125 秒；三列使用相同的原始时间。','同一 source51310 舞蹈片段替换为 Sam Altman。三列依次为动作参考、P0 原始指令编辑、P1 按 H3 协议整理的指令编辑。全部 141 帧，共 5.875 秒，三列使用相同的原始时间。')
  s=s.replace('P1 明确图像、视频各自的角色，并写出原片动作和保留要求。P0、P1 均为普通 H3 生成，使用同一原始参考输入与初始噪声。此对照检验整套提示适配的影响。','P1 同时改变分节格式、任务标签和显式媒体引用。P0、P1 均为普通 H3 编辑，使用同一原始参考输入和已核验的历史初始噪声；该结果检验整套提示协议，不能独立归因于某一个格式元素。样例来自此前的开发筛选。')
  s=s.replace("'fixed_pair_denominator': 2","'fixed_pair_denominator': 1")
 if name=='test_consumer.py':
  s=s.replace("'independent_prompt_conditioning')","'independent_prompt_conditioning', 'original_AV_noise_exact', 'original_raw_input_video_exact')")
  s=s.replace("'valid_frames': 147","'valid_frames': 141").replace('[0, 0, 1152, 768]','[0, 0, 1312, 736]').replace('list(range(0, 147, 3))','list(range(141))').replace("'evaluation_fps': 8","'evaluation_fps': 24").replace("'width': 1152, 'height': 768, 'nb_read_frames': '158'","'width': 1312, 'height': 736, 'nb_read_frames': '141'")
  s=s.replace("('source_id', PAIRS[1])","('source_id', 'other')").replace("run_id(PAIRS[1], 'p0')","'r75_other_seed2026101701_p0'")
  s=s.replace('[0, 29, 58, 88, 117, 146]','[0, 28, 56, 84, 112, 140]').replace('trim=end_frame=147','trim=end_frame=141')
 (D/name).write_text(s)
print(D)
