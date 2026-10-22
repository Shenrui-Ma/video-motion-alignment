R64 IVEBench 四源消费包：CPU 准备完成

本地：/Users/researcher/DevProjects/h3-ivebench-heldout-metrics-r64-20261018
.41 目标：/data3/researcher/h3_runs/ivebench_heldout_metrics_r64_20261018
.41 Python：/data3/researcher/ComfyUI/.venv/bin/python
.41 producer：/data3/researcher/h3_runs/timing_ivebench_heldout_r64_20261018

继承与范围

R63 的68个 runtime 文件逐字节保留，官方 IVEBench commit2dcf8900ee65197f43854c76f61c66a32bb8dbfc；原 CoTracker3 offline grid10/window60/query0/backwardFalse，100点，原官方 MF 插值、可见性与匹配函数未改。包装器仅替换旧固定5源/90帧的输入验证和显存准入，兼容本批4源及动态帧长。源与两种编辑必须 fresh same-host、同Torch/CUDA/显卡型号。没有沿用旧源分数。

有效帧：0092=58/总73；0114=105/总107；0126=109/总124；0392=57/总73。四源都按原有效 i/24 秒、裁剪[16,8,1280,720]评估，尾部 padding 不计分。四任务是官方道具/环境编辑，人体运动保存用源视频事件表核查；与此前人物/服饰编辑组分别报告。当前包含官方MF和同帧人工评估媒体，不新增时延估计器。

完成证据

- CONSUMER_FREEZE.json：99个冻结文件，包括68个原runtime、适配脚本、四源选择与源crop/时间绑定。最终SHA见CONSUMER_PREPARATION_MANIFEST.json。
- audit/CPU_TESTS_FINAL.txt：26 tests PASS，检查动态形状、实际条件/noise/前6步要求、错误物理时间、padding、source变更、旧gate、同环境约束、foreign多卡与own两卡上限。
- audit/ACTUAL_SOURCE_CHECK_ONLY.json：4条真实源的原tracker check-only PASS，零forward、零CUDA、未导入Torch；实际源crop已经逐帧MD5校验。随后只修了.41现有checkpoint路径和跨host清单命名，两次变更归档在audit；数值与源视频不变。
- .41已有checkpoint实际SHA已核验：/data3/researcher/h3_runs/ivebench_official_metric_20261017/weights/baseline_offline.pth，da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df。
- 没有运行GPU/tracker，没有生成任何伪结果。目标预处理与渲染等真实pair gate后执行。

被动部署

audit/consumer_cpu_bundle.tar.gz包含代码/config/runtime/准备好的4源crop与原始manifest（不含大模型或已存在producer输入）。解包到独立consumer根，先mkdir -p inputs，运行：
  CUDA_VISIBLE_DEVICES='' python scripts/materialize_inputs.py --producer-root /data3/researcher/h3_runs/timing_ivebench_heldout_r64_20261018
该步骤逐SHA复用已在producer里的16个源文件，不接触producer。可运行26项CPU测试；tests无需本机路径。原prepared SOURCE_INPUTS.json带本机历史路径，source_row按原SHA重绑当前根，source_manifest使用按当前根命名的HOST副本。host副本不覆盖历史文件。

实际消费，每完成一对立即处理

1. root/producer先跑 analysis/postrun/verify_pair.py --source short_0092（另3源同理）。
2. consumer：python scripts/collect_pair.py --source short_0092 --producer-root <producer>。必须passed R64实际gate、same conditions/noise/prefix0..5、NFE20、Native0/ON450、逐源总帧数；复制真实视频、job/history/router/graph和gate到incoming。
3. CUDA_VISIBLE_DEVICES='' python scripts/prepare_pair.py --source short_0092。共享CPU锁，逐帧验证lossless有效crop；输出prepared/SOURCE/METRIC_INPUTS.json和READY.json。
4. root分别对 source/native/forced 启动 scripts/track_one.py。source可以在目标成片前跟踪。示例（只有root执行）：
  CUDA_VISIBLE_DEVICES=GPU-ROOT-CHOSEN PYTHONDONTWRITEBYTECODE=1 python -u scripts/track_one.py --source short_0092 --method source --gpu-uuid GPU-ROOT-CHOSEN --attempt 1 --control controls/0092_source_attempt1
   读ready.json准确PID/UID/start/cmd后，写内容完全相同的go.json；600s超时，CUDA前两次fresh资源查询，最多2张own卡，foreign共存按余量。每个source/target独立进程自然释放。Native/forced参数相同但独立control，绝不复用directory。
   默认至少24GiB free 是最大109有效帧的保守bootstrap门，尚无实际109帧峰值认证；原90帧峰值不当作本批实测。root可先跑109帧source记录actualpeak，再决定其余tracker排程。本包不会自动启动。
5. 两个实际target完成后，CUDA_VISIBLE_DEVICES='' python scripts/score_one.py --source short_0092 --method native（forced同理）。从真实同host/runtime源/target缓存调用原score函数，CPU输出results/source/method_source1_target1.json。
6. 原始分数必须与编辑成功、人体动作保存一起看。results/source/HUMAN_REVIEW.json可记录 source、source_selection_sha256、editing_success、motion_preservation；未检查状态为UNREVIEWED。不要把MF当毫秒时延或把所有帧看不清当无误差。

展示

下载该源incoming实际小文件和prepared三份score MP4/JSON到本地同根。python scripts/render_pair.py --source short_0092，会生成3840x808黑底中文caption三栏：完整有效片段、前48帧、6个均匀源时刻截图。绘制只加caption，三列物理时刻一致。根目录读取源checkpoints用于人工事件核查，不进入模型。Mac现成STHeiti Light字体，FFmpeg无drawtext也可运行。
python scripts/make_showcase.py --output <Downloads单文件HTML>。实际视频内嵌，4条始终保留；待完成与未评测显示对应状态，全部4条有效才报告均值。当前无真实生成结果，因此未发布新结果网页。

未测边界：真实目标视频进入consumer后的端到端、109帧tracker显存峰、实际展示渲染均待第一对成片。当前任务仅CPU准备，未改任何生产源或科学kernel。
