# R66 FlexiAct 扩充：CPU 准备完成

8 对、16 次推理。每对按 Native → forced 执行。6 对是官方素材构造的新交叉配对，覆盖 3 个新动作源；2 对沿用官方 CSV 的配对，覆盖已观察过结果的 fitness / one_leg 两个动作源。统计分母为 8 个配对、5 个动作源，两个任务组分别汇报。这批属于开发性诊断，素材清单在查看本批生成结果前冻结。

## 固定队列

|顺序|pair key|组别|
|---|---|---|
|1|human2animal_1__movie_man_11|新交叉配对；新动作源1＋真人目标图|
|2|human2animal_1__game_man_4|新交叉配对；新动作源1＋动画目标图|
|3|fitness__game_man_4|官方 CSV；原动作＋新目标图|
|4|one_leg__movie_man_11|官方 CSV；原动作＋新目标图|
|5|human2animal_3__movie_man_11|新交叉配对；新动作源3＋真人目标图|
|6|human2animal_3__game_man_4|新交叉配对；新动作源3＋动画目标图|
|7|human2animal_2__movie_man_11|新交叉配对；低运动量对照＋真人目标图|
|8|human2animal_2__game_man_4|新交叉配对；低运动量对照＋动画目标图|

每个 pair 的条件节点、条件快照、初始噪声文件与 run_id 均包含 action＋target，避免不同目标图共用一个动作键。兼容代码中的 `source_id` / `--source` 实际指 pair key；明确的动作源字段是 `motion_source_id`，原官方或自建配对路径为 `original_pair_id`。核验命令优先用 `--pair`。

## 推理与形状

保持 R65 的模型、dtype、kernel、Euler20、CFG1、sigma、种子2026101701与原完整提示词。6 个数值核心文件与 R65 逐字节相等。forced 使用 mass_preserve、alpha1、全部50层、零基去噪步骤6…14。物理支持为0…146帧，对应47个潜在时间bin中的0…43，所有空间query。最后一个受引导bin覆盖145…148帧，其中147、148为边界padding；44…46是纯padding bin，维持原生注意力。Native 实际路由次数为0，forced为450，均20次预测与Euler更新。Native 的原继承step参数为0…19，forced为6…14；物理支持参数相同。

所有源保留49帧、8fps官方原片。每帧重复3次得到147帧有效输入，再加11帧尾padding，最终1152×768×158@24。AV形状分别 `[1,24,47,48,72]`、`[1,32,2,263]`。评分取0,3,…144共49帧、8fps；展示取前147帧、24fps、6.125秒。两图的 H3 `ref_image_size=match` 预期：

|目标图|原图|H3图像编码尺寸|clean image latent|图像patch数|
|---|---|---|---|---|
|movie_man_11|2500×1830|1088×800|[1,24,1,50,68]|850|
|game_man_4|975×600|960×608|[1,24,1,38,60]|570|

这些是由固定源码公式计算的预期值；实际 Qwen 长度、两种参考latent、packed layout、输出与前6步相等性在成片后由 `analysis/postrun/verify_pair.py` 检查。没有借用旧目标图的 packed sequence 长度。

## Root 执行入口

本地：`/Users/researcher/DevProjects/h3-timing-flexiact-expanded-r66-20261018`

远端：`/data3/researcher/h3_runs/timing_flexiact_expanded_r66_20261018`

.41 GPU2：`GPU-REDACTED`，端口8536，normal / reserve8。当前 `ready_for_launch=false`，没有部署、服务、GPU运行或伪造实际容量证明。R65 保持 GPU1/8535。其他用户的进程只受实际显存余量约束；我方所有任务所用 GPU 并集上限2张，peer需登记 exact UID/start/cmd identity。`existing_comfy_port=null`；peer正在运行任务可并存，由 permitted_compute_processes 校验身份。

沿 R65 的首对试运行流程：

1. 同步本包并核 PREPARATION_MANIFEST 文件 SHA；root 检查现场资源，在 admission.json 登记当前 peer 的精确身份。
2. 在远端运行 `python3 scripts/preflight.py`；`python3 scripts/execution_gate.py seal`。
3. `python3 scripts/execution_gate.py approve-first-pair --root-admitted`。首对试运行门为至少20GiB fresh free；该值是继承的容量试运行下限，实际峰值待首对测量。
4. `python3 scripts/launch_remote.py --service-only`。服务到达 pre-CUDA ready 后，root把该精确身份登记到 peer admission，原样原子复制 ready JSON 到 go JSON。
5. HTTP8536就绪后 `python3 scripts/start_controller.py --pid PID --start-ticks TICKS`。
6. 首对完成，队列停在 `awaiting_first_pair_review`，保留模型最多1800秒。执行：

```sh
CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python analysis/postrun/verify_pair.py --pair human2animal_1__movie_man_11
```

核验保存到 `analysis/postrun/human2animal_1__movie_man_11/PAIR_RUNTIME_GATE.json`。它检查8种条件tensor、实际初始AV噪声、前6个AV x0逐位相等、20次模型预测、全部21组AV张量、两种参考的实际形状、packed layout、路由计数、158帧24fps输出及冻结源。质量评估另做；结果没有预填成功。

7. root结合容量和成片评估，执行 `python3 scripts/execution_gate.py approve-rest --root-admitted` 后继续剩余14次。其余 pair 用各自 `--pair KEY` 核验。中途失败保留证据，已有 job 记录不自动重投。服务生命周期最多12小时，单job最多4小时。
8. 全队列完成后root置 queue.json 的 finalize=true 释放进程；等待状态1800秒到期亦精确回收本服务。

`audit/prepare_package.py`、`audit/extend_verifier.py`是一次性建包记录，不是部署/运行命令。`deploy_manifest.json`由root在正式现场封存；本包没有创建授权文件。

## 验证与边界

35项 CPU 测试全部通过，覆盖成对输入、缓存隔离、变量图像形状、实际噪声/条件/x0受损拒绝、数学dense oracle、纯padding保持、首对审批范围、已登记peer并行、其他用户跨3张卡、我方超过2张卡与身份替换拒绝。41个Python文件通过AST语法检查。10段实际源/准备视频通过ffprobe；18个输入文件共43,592,326字节并逐项SHA校验。

证据：`audit/CPU_PREPARATION_VALIDATION.json`、`audit/CPU_TESTS.log`、`audit/R65_TO_R66.patch`、`configs/source_selection/*`。原R65以及其他活跃目录保持原样。

source3主要评估腿部动作，手部/头部局部出框；source2是低运动量连续动作对照。source3的手臂observer缺测不能解释为运动无误差。后续官方MF与同帧人工动作/目标外观检查分开报告。
