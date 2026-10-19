R104：六项旧 FlexiAct 任务的提示修复设计

本轮完成原素材、旧实际 prompt、官方 metadata 和六段候选 prompt 的准备。没有新增推理结果。六项任务覆盖五条动作视频和四张目标图；下蹲源被两个不同目标人物复用。

建议后续普通编辑顺序
1. fitness / game_man_4：主要修复白背景。旧版已生成动漫男性和主要服装，但背景变为山地。完整动作是双臂侧举、过头、手靠拢、合掌下降；片尾只降到脸前。目标图与 R98 已成功使用的图像相同。
2. human2animal_1 / movie_man_11：目标是浅金短发的西装男性，场景为草坪旁铺装路面及树/灯柱。源动作是低位屈肘、胸近地、伸肘抬胸、拱背低头。这与 R98 成功案例共用动作源，便于检查同一来源分工能否迁移到另一个人物。
3. crouch / movie_man_5：短侧分棕发男性、炭灰西装、浅蓝衬衣、窄领带，白色背景。源为两轮下蹲与起立。此前 R85 已有六段 P1，本次具体化目标身份、白背景及动作角色；不能把以后变化解释为首次采用官方格式。
4. human2animal_2 / movie_man_11：盘腿坐直、双手前移、躯干前屈、低位保持。旧版变成俯卧/跪姿。身份与盘腿底座可验收，但动作慢、后半长保持，时序信息量有限。
5. crouch / movie_man_4：目标是裸上身、短深发、深蓝泳裤的海边男性。目标图只有头部到大腿附近，脚下支撑不可见；保留海水/天际线，膝以下和支撑几何需要模型推断，不能给不存在的鞋型或地面真值。
6. human2animal_3 / game_man_4：先低位前倾，再屈腿抬升、趋向倒置。手和头靠画面下缘，承重细节无法可靠看清；片尾膝仍弯曲。先验收动作顺序和身体结构，不能只凭局部检测点说时差改善。

参考分工
每份候选沿 R98 的写法：Subject 1 明确来自 Picture 1 的人物外观，Subject 2 明确目标图环境，Subject 3 单独定义 Video 1 中的可见动作，Video 1 负责连续结构和物理时间。Picture 1 的站姿不作为首帧。六段均按官方英文顺序写，保留 [reference generation]、关系标记和 [Shot 1]；动作阶段描述来自原片，没有把人工帧区间加入 prompt。

环境要求的证据边界
官方 README 将任务定义为从参考视频转移动作、使目标图运动，并允许布局/视角变化。val_image.csv 给出目标图及动作 caption，没有逐字规定“白背景必须完整保留”。本项目六项旧实际 prompt 已明确要求保留目标图场景，本轮沿用这个既有任务约定。白背景或室外路面来自实图检查和旧任务文本，不能说是官方 CSV 的明文要求。
三项 human2animal→人类目标是既有自建交叉配对：原官方验证目标为动物。它们属于官方素材扩展，结果需与三项原 CSV 人类配对分别登记。

发现的 metadata 冲突
两项 crouch 官方 target caption 错写拉索器械运动，实际原片和 source caption 都是下蹲。fitness caption 写双手降到胸前，49帧片段实际只到脸前。human2animal_1 caption 写多机位与桌椅，实片是固定近景；human2animal_3 caption 提到后续 push-up，当前片段未出现。原文已完整保留在 metadata；候选 prompt 按实际可见动作描述。

验收与后续边界
首次只生成每项新的普通编辑，先分别验收人物身份、目标环境、动作顺序和结构，再判断时序。全部147有效帧与49个原动作时刻应保留；背景失败即单列任务失败，即使动作大致同步。只有基础任务通过后才由 root 决定匹配引导。
保持原图原视频字节、seed2026101701，以及现有1152×768、24fps、158总帧设置：49原帧@8fps各重复3次得到147有效帧，尾部11帧为padding。输出0,3,…144对应原49时刻。8fps提供约125ms原始时间粒度。当前未生成运行图；正式运行配置需在后续独立生产包中绑定。
旧结果仅为失败背景。若新旧主机/runtime不同，修复结果不能单独归因于 prompt；本次也没有新的机制或新颖性主张。movie_man_5 原图水印和侧边文字保持原文件，作为额外输出现象登记。

可核验文件
EVIDENCE.json：六项实际 graph/原 prompt/原始与处理后视频/目标图/SHA、官方 CSV 行、官方 LFS 来源和任务范围。
prompts/*_previous.txt：旧实际字符串，按原字节保存；crouch/movie5 为已有 P1，其余为原三句 prompt。
prompts/*_P1.txt：六份新候选。
SOURCE_TARGET_REVIEW.json、review/*_all49.jpg：已查看的五条完整49帧及四张原图记录、动作阶段与可见性限制。
ACCEPTANCE.json：每项身份/场景/动作验收条件。
PROPOSED_ORDER.json：建议顺序和原因；尚未提交队列。
PREPARATION_VERIFIED.json、audit/ACTUAL_PTS.json：实际输入 SHA、原始和处理后 PTS、六段结构核验。

复核命令
PYTHONDONTWRITEBYTECODE=1 /Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python verify_design.py

官方资料
H3 指南：https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md
FlexiAct README：https://github.com/shiyi-zh0408/FlexiAct/blob/main/README.md
数据 revision：69d7747f93e1b913a3dca306bf8e91ee74fea7d4；所有精确资产 URL 和 SHA 在 EVIDENCE.json。
