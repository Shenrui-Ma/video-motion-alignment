# H3 本地证据与复用路径映射（2026-10-16）

本次仅只读本地文件，没有连接服务器、启动推理或修改既有封存实验。JSON 附件列出准确的输入、输出、配置和噪声路径。

## 最快可复用入口

最新完整 .9 配对系统：`/Users/researcher/DevProjects/h3-sam-real-dance-batch-20261015/`。
- `scripts/service.py`：核心路径、启动参数、GPU admission、按 UID/PID/start_ticks/命令身份检查后清理。
- `scripts/job.py`：一次性提交、轮询、原始 history 归档。
- `scripts/run_queue.py`、`lease_watchdog.py`、`supervise_service.py`：串行队列、lease 超时清理、监督。
- `scripts/collect_run.py`：归档拉取；`probe_live.py`：一次读状态。
- `scripts/compatibility_bootstrap.py`：Torch2.5 schema、PyAV16、Triton INT8 row guard。
- `scripts/launch_remote.py`：含硬编码上轮 Musk07 完成要求，不要原样启动；需换新 RUN、端口、task ID、audit 根、输入、队列、admission、前序检查。
- `extensions/H3EventEmphasis/core.py`、`__init__.py`：最直接可扩展的隔离 DiT patch。
- `extensions/H3PairAudit/__init__.py`：每轮实际条件/布局/clean ref latent 哈希；允许共享 node5 缓存但每轮重新做快照。
- `extensions/H3EventAudit/__init__.py`：源帧、语义抽帧、clean VAE latent、初始噪声审计。audit_root 是任务根限制，移到新实验必须同步改。
- `tests/test_pair_audit.py`；较早 `h3-event-emphasis-pilot-20261013/tests/test_event_emphasis.py` 提供小张量等价验证。

连接脚本使用 `ssh -o BatchMode=yes researcher@192.0.2.1`；无密码出现在本报告。远程最近任务 `/data5/researcher/h3_runs/sam_real_dance_batch_20261015`，共享 Core `/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI`，Python `/home/researcher/miniconda3/envs/comfyui/bin/python`，依赖 `/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps`，模型 `/data5/researcher/ComfyUI/models`。最近用 GPU2 UUID `GPU-REDACTED`。历史清理已证实；**今日空闲状态本次未查，不能直接假设 GPU2 还空着**。

## 已经运行的真实配置与效率

所有四组真人：seed2026101311，1312×736、141帧、24FPS，20步Euler，video/audio shift12/3，无Turbo LoRA、无Sage，native PyTorch SDPA。H3 INT8 ConvRot pruned、Qwen NVFP4/AWQ、video VAE fp16、audio VAE fp32。具体模型名在 JSON。

Sam .9 四条实际 history 耗时：1576.019、1552.825、1523.406、1551.001秒（约25–26分钟/条）。配对共用条件编码；正常组0次attention override，x3组1000次=50层×20步。baseline与x3的少量耗时差不能当稳定加速结论。

.9 的 Triton INT8 分块只防 signed-32 row offset overflow，保留独立行计算及顺序，不是时间重采样。服务须使用任务级 bootstrap，不改共享环境；.41 Musk05用Torch2.11/cu130 CUDA INT8，而Musk07和两组Sam用.9 Torch2.5/cu121 Triton，因此跨机器不能单独归因身份。

## 先前 x3 到底是什么

源：`h3-four-pair-evidence-review-20261015/control_audit.txt` 和 `h3-sam-real-dance-batch-20261015/extensions/H3EventEmphasis/core.py`。

`duplicate_event_attention` 先调用 native 全 attention。对选定 target video Q，再把选定 reference video K/V 各附加两份，使用native attention重算，回填这些Q行。K已通过QK RMSNorm和RoPE。数学上是选定 Q→K logits 加 ln3；当参考组选前概率质量是P时，选后P'=3P/(1+2P)，是相对odds三倍，不是最终概率三倍。

全50个DiT层、20步、56头均执行。没有改token refiner、权重、prompt、RoPE坐标或K/V幅度。每个选中Q看整个选中K组，**没有逐时间片一一对应限制**。空间上全画面，包括背景/外观；不能说纯动作特征增强。

|案例|人工源帧窗（含端点）|latent区间（左闭右开）|位置bin覆盖|选中Q/K各自数量|
|---|---|---|---|---|
|真人05|50–65|[14,20)|47–67|5658|
|真人07|54–69|[16,22)|52–72|5658|
|动漫06原始factor2和factor3|39–44|[12,14)|39–46|1886|

映射按(1,4,4,4,4)循环，不能frame/4；每latent时间片943个空间token。位置bin不是精确VAE感受野。**此前聊天的33–77不是正式加权窗口**；正式文件中的检查展示窗是30–77，真正干预39–44。旧注册计划和报告均证实。原始动画seed2026101312的factor2、factor3均未修复早期手—眼动作，不能把后面的长V手势当成恢复。

## 时间链已经排除与尚未排除

`h3-motion-timing-audit-20261013/REPORT.txt` 汇总：20个源和输出全逐帧PTS检查为首PTS0、24FPS均匀网格，误差<2微秒；没有输出慢一档帧率或0.6秒起始偏移。Prepared真实float32存储与源逐帧RGB核查：06/07/04全部同索引最佳；05的138/141同索引、其余最多差1帧，无15–16帧系统移位。代码链未发现显式重排或prepend。

`h3-short-event-switching-20261013/REPORT.txt` 另说明三个case的实际输入、prepared、VAE回解已检查，目标手—脸关系可回解。回解视频可直接复用：该目录`outputs/{05_real_megumi_v,06_anime_eye_insert,07_real_ary_v}_reference_vae_reconstruction_00001_.mp4`。这只排除目标关系完全消失，不代表细指/边界毫无损失。

141帧对应42latent；video patch=1×2×2；reference和target局部时间增量相同，但packed RoPE有固定段起点差。该差不是物理视频延迟。语义分支2FPS取0,12,...132；dense VAE仍用全部帧。当前任务从全噪声sigma1做Ref2VA条件重生成，没有源latent inversion或逐帧保持硬约束。

尚未有官方pipeline/full-precision/no-edit对照，无法定位共同实现/量化/模型机制唯一原因。

## 已有动作结果和量化缺口

- `h3-motion-timing-audit-20261013/landmark_audit.{txt,json}` 与 `landmarks/landmark_table.csv`：26项目视动作边界；16条结果反证“所有视频统一变慢”，部分中段延后15–17帧、末段又追上。
- `h3-musk-real-dance-pair-20261014/REPORT.txt`：Musk05普通约晚9帧，x3约提前3帧，后续低位交叉/头顶展开更接近源。
- `h3-four-pair-evidence-review-20261015/musk07/motion_review.txt`：普通目标晚约15帧，x3接近源。
- `.../sam05/review.txt`：普通约晚11–14帧，x3早约1–3帧；后续阶段接近。
- `.../sam07/REPORT.txt`：普通约晚15–16帧，x3接近源，但后段仍有误差。

这些都是非盲AI目视抽帧检查（边界约±1–3帧），不是经验证pose/flow指标、不是统计显著性或人类盲评。**没有发现可直接复用的自动动作延迟量化脚本**；`pixel_time_audit.py`只比较未编辑源与prepared，不宜用于跨身份生成视频对齐。各review.py/make_sheets.py仅渲染证据。四组实际为2相关编舞×2身份×1seed，不能当4独立动作类型。

## 建议最小公平对照（供主线程决定）

1. 优先Sam07或Sam05（.9环境、一组噪声与条件已归档），同一新服务复跑baseline、旧x3、候选机制。历史baseline只作复现参考；新方法若换环境不能独自对比历史baseline。
2. 两个case至少各1个固定seed；若算力允许，再加第二seed，并保留本来近源的正例。先注册候选、评价窗、失败判据，不按生成结果改窗口。
3. 候选必须对比旧x3以及其消融（例如去掉时间对应结构但保持相同强度/算量），否则无法证明架构部分必要。可加相同长度wrong-window以区别特定时序指向与笼统重参考。
4. 新patch继续用相同model.clone/model_patch_replace接口，不修改共享模型或Core；记录实际call/layer/step/selected-token数、条件和噪声哈希。
5. 每组至少量出目标onset/peak/offset误差、前后邻接动作次序、完整片段漏/新增次数；身份与背景/画质单列。不以单帧相似或DTW对齐后误差代替原始时间误差。先定义与同一源的时间映射，不能后处理重定时再声称修复。
6. 首次新机制可以2步技术检查；技术输出不参与画质结论。正式至少保留20步Euler一套以匹配旧证据，若改8步或Sage则整套对照都重跑，并单列加速因素。

完整准确资产列表见同目录`local_evidence_map.json`。未修改任何旧项目。
