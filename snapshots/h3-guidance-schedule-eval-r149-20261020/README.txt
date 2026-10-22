R149 评测准备（新目录；旧报告、旧实验和库存均不修改）

三组：机舱 short_0252 / Sam 05_real_megumi_v / 饮酒 short_0358。
前三列精确复用历史参考、普通编辑、原第 7–15 步时序引导。
第四列切换 early / late / split / global_weak；总计十二个新结果。
前三方案分别启用 1–9、12–20、1–4＋16–20，各九步；保留原物理帧窗与 α=1。
global_weak 启用全部二十步、全有效视频，引导强度为原来的1/4（α=0.25）。
它混合原 all-reference 输出与同时间 bin 读数，参考总概率质量保持。
phase displacement 均为零。步号展示为 1-based；合同和日志使用 0-based。

冻结证据：
EVALUATION_MANIFEST.json：旧视频、图、提示词、实际噪声、MF 分数、源轨迹及 SHA。
EVALUATION_PLAN.json / EVALUATION_FREEZE.json：沿用既有事件和姿态窗口。
机舱三事件 source42–45/48–51/69–75；Sam 主窗50–65，回收窗69–81/80–92/99–111。
饮酒三事件沿 R123/R148：放低酒瓶14–18、瓶口到嘴37–40、瓶口离嘴80–84。
第三组新增记录在 audit/amendments/add_short_0358/；before/ 保存原两组冻结文件。
两组原数据与事件逐项相等，展示标题的任务类型单独在 build_html.py 映射。
Sam 旧 lag 是 arm_direction 诊断，不能替代成人工事件时刻。
每条完整有效帧都审阅；追加全片观察单独记录，不更换主评价窗口。
MF_PLAN.json：十二个新 target tracker；三份精确 source track cache 复用。
全部旧大型资产仅路径引用，不复制。只用 CPU 不加载模型。

执行目录：
cd /Users/researcher/DevProjects/h3-guidance-schedule-eval-r149-20261020
PY=/Users/researcher/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3

1. producer 最终 seal 后，逐 case 绑定（只读 producer，不启动）：
python3 bind_producer.py --case short_0252 \
  --producer /Users/researcher/DevProjects/h3-guidance-schedule-r149-20261020/cases/short_0252 \
  --seal-sha256 ACTUAL_SEAL_SHA
另一 case 同理。仅最终封存包可 READY，未绑定时 intake 明确拒绝。

2. 每条实际 run 的 *_GATE.json 和小视频已收取后，直接生成同帧四列预览：
"$PY" ingest.py --case short_0252 --schedule early \
  --video /ABS/ACTUAL_OUTPUT.mp4 --gate /ABS/r149_short_0252_seed2026101703_early_GATE.json
逐条 gate 核 actual graph/history/owner/conditions/noise 的 producer 检查结果；
consumer 再核 role/run/seal/alpha/实际步集合/phase0/调用数/有效帧域/输出SHA与实测geometry。
只有逐条门时状态是 PER_JOB_VERIFIED_BATCH_RELEASE_PENDING，不宣称整组释放。
产物：review/<case>/<arm>/comparison.mp4、全部有效同帧 JPEG、PRESENTATION.json、REVIEW_TEMPLATE.json。
四列视频2560×424，黑底中文底caption，无额外顶栏，原速24fps。

3. 完整有效帧审阅写入同目录 REVIEW.json：
从 REVIEW_TEMPLATE.json 起草，actual_video 保留，review_completed=true。
task_verdict/summary_zh 如实保留失败、部分编辑、负时序效果；
仅填该 arm 的事件或离线姿态窗值，源/native/fixed 旧区间不改。
python3 summarize_review.py --case short_0252 --schedule early
区间统计穷举整数帧，配对误差共享 source 时刻；相邻阶段时长另列。

4. 四条结束且真实 COMPLETE/ROOT_EXIT 到齐后：
python3 finalize_batch.py --case short_0252 --gate /ABS/SCHEDULE_RUNTIME_GATE.json \
  --complete /ABS/COMPLETE.json --release /ABS/ROOT_EXIT_RECEIPT.json
只追加实际 BATCH_RELEASE.json；不重新渲染媒体。

Sam 迁移的独立 3+1 释放路径：
  原 .9 early/late/split 保留原各臂绑定；global_weak 仅在根代理确认迁移后绑定新包：
  python3 bind_producer.py --case 05_real_megumi_v --schedule global_weak \
    --producer /ABS/APPROVED_NEW_PRODUCER --seal-sha256 ACTUAL_SHA --archive-old

  三条原结果必须有真实 PARTIAL_RELEASE.json；该记录仍列 remaining=[global_weak]。
  新 .41 单臂必须有 segment gate、segment COMPLETE 和精确 ROOT_EXIT。
  收取双方 MIGRATION_MANIFEST/MIGRATION_DEPLOYMENT，以及 partial receipt 所引用的四个小原文件
  （cleanup.json、FAILURE.json、CAPACITY_MONITOR_EXIT.json、BOUNDARY_REQUEST.json）。
  全四个 per-job gate 和视频仍按各自 runtime/<case>/<arm>.json 单独 ingest。
  最后使用：
  python3 finalize_composite.py --case 05_real_megumi_v \
    --migration /ABS/MIGRATION_MANIFEST.json --deployment /ABS/MIGRATION_DEPLOYMENT.json \
    --partial-release /ABS/PARTIAL_RELEASE.json --prefix-evidence-dir /ABS/PREFIX_RECEIPTS \
    --segment-gate /ABS/NEW/SCHEDULE_RUNTIME_GATE.json \
    --segment-complete /ABS/NEW/COMPLETE.json --segment-release /ABS/NEW/ROOT_EXIT_RECEIPT.json

  此命令写独立 r149-evaluation-composite-release-v1，明确 same_persistent_service=false，
  original_four_arm_COMPLETE=false；不生成或改写旧 producer 的 COMPLETE。
  缺任一角色、错误文件 SHA、不同 owner/实际 seal、缺少精确释放均拒绝。
  原 finalize_batch.py 的四臂同服务路径不变。MF 仍等四个新结果齐全后一次准备，
  同时封存两段真实证据；不重复旧 source/native/fixed tracking。
本轮每 case 同一 service 四 job；预览和整组完成严格分开。

5. 生成离线 MF 输入（CPU，仅已释放的结果）：
python3 prepare_mf.py --case short_0252 --schedule early
复用 R148 同一 lossless score_view：crop、帧域、fps、像素MD5规则不变。
输出 mf_inputs/<case>/<arm>/INPUTS.json + score.mp4，原 source track/report SHA 再验证。
GPU tracker 命令由 root 在资源释放后授权；此目录没有 GPU 启动/下载入口。
失败编辑同样评分，MF 与人工事件结论分别报告。

6. 展示页：
python3 build_html.py                    # 可随逐条结果更新，缺结果明确 pending
python3 build_html.py --embed --final    # 十二条真实结果、完整review、MF、release齐后才通过
单文件产物 R149_引导步区间对照_单文件.html，视频与固定代表截图内嵌。
下载目录最终发布由 root 完成；准备阶段仅写本目录。
不调用任何 headless Chrome、check_html.cjs、HTTP替代浏览器。
QA 限 HTML 源结构、JS语法和实际媒体解码/hash/收据绑定；未声称浏览器视觉验收。

CPU 验证：
python3 -m unittest -v test_evaluation.py
python3 freeze_evaluation.py             # 再运行只核对冻结文件，不改事件
