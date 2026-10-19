# R66 评测消费包：CPU 准备完成

本包接收 R66 的 8 对真实 Native / fixed-ON 成片，保留完整158帧；按官方原片时标抽取0,3,…144，共49帧、8fps，计算 FlexiAct author-code Motion Fidelity。官方CSV的2对与新增交叉配对的6对分报；统计为5个不同动作源，其中3个新动作源。CoTracker 与 MF 函数、权重和49帧抽取代码继承R65原字节。

本地：`/Users/researcher/DevProjects/h3-flexiact-expanded-evaluation-r66-20261018`

.41：`/data3/researcher/h3_runs/flexiact_expanded_evaluation_r66_20261018`

.9：`/data5/researcher/h3_runs/flexiact_expanded_evaluation_r66_20261018`

root占用的 `inputs/`、`SOURCE_POSE_PROTOCOL.json`、`SOURCE_POSE_COMPLETE.json`、`source_pose/`保留原样。消费代码、配置与独立runtime放在其他目录；本次没有启动GPU、tracker、pose、服务或远程任务。

## 输入与缓存

生成结果按 action＋target 的8个 pair key保存，例如 `human2animal_1__movie_man_11`；reference CoTracker 按5个 motion_source_id保存，例如 `human2animal_1`。同一动作源换目标图共用 reference tracks。生成结果各自提取，互不混用。

`human/<action>/000`是继承tracker接口的 motion-source cache ID。真实任务ID另存为 `original_pair_id`，例如 `human/fitness/004` 或 `extension/human2animal_1/movie_man_11`。新增交叉配对不会被记成官方CSV条目。

新3个源需在.41提取fresh CoTracker。fitness、one_leg可复用R65本批在.41提取的source缓存；使用显式复用收据，保留R65原始 REPORT、tracks、输入manifest、wrapper和freeze文件字节。复用时核对原视频SHA、49个原时间点、运行host/GPU型号、Torch/CUDA版本、权重/代码哈希、grid55与无mask设置。R49历史缓存不能进入该路径。

## Root执行

所有GPU动作由root安排，两个服务占用限制仍为自有GPU并集最多2张。tracker继承R65的40GiB当前free门，允许已有CUDA上下文；运行前再次查显存。先把本包同步到.41，保留root已有pose目录。`CONSUMER_FREEZE.json`覆盖本消费包静态文件，不覆盖root pose资产。

### 每对成片接收与抽帧（CPU）

先完成producer的 `analysis/postrun/verify_pair.py --pair KEY`，取得实际条件、噪声、前6步AV x0、路由及输出核验收据。

```sh
CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python scripts/collect_pair.py --producer-root /data3/researcher/h3_runs/timing_flexiact_expanded_r66_20261018 --pair human2animal_1__movie_man_11
CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python scripts/prepare_pair.py --pair human2animal_1__movie_man_11
```

`collect_pair`只接收该实际pair的PASS收据与绑定视频/图/历史/日志；`prepare_pair`检查任务一致性，并验证49帧与原158帧对应画面的decoded MD5相等。

### 新源轨迹（命令规划本身为CPU）

```sh
python3 scripts/tracking_plan.py --key human2animal_1 --method reference --gpu-uuid GPU-REDACTED
```

打印root可执行命令。root实际启动后等待 `controls/reference_human2animal_1/ready.json`，核确切PID身份并登记peer，再原样复制ready到go。脚本用同一进程执行冻结的 `run_tracks.py`；退出后释放GPU。新源2/3同理，各只需一次。GPU UUID由root现场选择；source与generated必须同host、同GPU型号及数值环境。

### R65 source缓存复用（CPU）

```sh
CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python scripts/source_cache.py --r65-root /data3/researcher/h3_runs/flexiact_forced_metrics_r65_20261018 --action fitness
CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python scripts/source_cache.py --r65-root /data3/researcher/h3_runs/flexiact_forced_metrics_r65_20261018 --action one_leg
```

要求R65的fresh reference REPORT/track和R65_BINDING已完成，输出 `tracks/reference/<action>/R66_SOURCE_REUSE.json`。若复用来源缺失，等待R65完成或单独安排R66 fresh source；禁止用历史R49冒充fresh缓存。

### 生成结果轨迹与评分

```sh
python3 scripts/tracking_plan.py --key human2animal_1__movie_man_11 --method native --gpu-uuid GPU-REDACTED
python3 scripts/tracking_plan.py --key human2animal_1__movie_man_11 --method forced --gpu-uuid GPU-REDACTED
```

root分别执行打印命令与ready/go。随后CPU评分：

```sh
CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python scripts/score_one.py --pair human2animal_1__movie_man_11 --method native
CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python scripts/score_one.py --pair human2animal_1__movie_man_11 --method forced
python3 scripts/summarize.py --output reports/MF_SUMMARY_001.json
```

`score_one`调用原字节 `metric_adapter.score_tracks(edited, reference)`，沿官方方向与相似度计算。它使用显式cache bridge核验器，因此可读取原封不动的R65报告；不要直接调用原 `official_metric/score_pair.py` 绕过该桥接检查。

汇总保留全部8对，分别显示固定分母2和6、可计算的成对数及缺失数；均值只在同一组的双侧有限分数对上计算。官方函数产生非有限值时保留null。MF并不证明目标外观成功、动作类型正确或物理时差改善；这些字段保持待人工评估。source3手部不完整，宜按同帧腿部变化检查；source2保留为低运动量对照。

## 展示

`make_triptych.py --pair KEY`生成三列黑底、底部中文caption：参考视频、编辑后视频、编辑＋时序引导后视频。固定输出前48帧（2秒）和完整有效147帧（6.125秒）；各列同物理帧，不移动时标。可传 `--font` 指定中文字体。`make_showcase.py --video FILE ... --output FILE.html`把实际生成的横拼视频内嵌为单HTML。

## CPU验证与当前状态

24项测试通过：成片gate、pair/group与时间映射、8pair/5source缓存隔离、R65复用来源与环境拒绝、官方数值函数继承、未知值保留、GPU共享与≤2自有卡、root ready/go身份校验。测试曾把官方自比值误写成必为1；原公式会从相似度矩阵减去单位阵，现已按原公式的独立小矩阵结果检查，并保存失败记录。官方函数没有改变。

新R66 CoTracker、生成结果分数和展示成片当前均未执行。根目录已有CPU姿态由root独立产生，不由本MF工具启动。`audit/CPU_PREPARATION.json`记录代码继承与实际源timebase；`CONSUMER_PREPARATION_MANIFEST.json`列本交付文件，明确排除root拥有的pose/inputs资产。
