# 书本编辑：引导阶段对照 CPU 准备

状态：设计及 CPU 检查冻结，未上传、未启动 GPU。主代理将优先生成书本、饮酒眼镜、手帕三组自动触发成片，本包暂停继续集成。当前没有服务启动脚本，`configs/admission.json` 为 `ready_for_launch=false`。

已登记两个新条件，均为 R122 long_0039 简短编辑加通用保留句，seed 2026101701、alpha 1、全片、全部 50 层、20 次 Euler 更新：

| 条件 | zero-based 预测索引 | 图中半开范围 | 引导预测次数 | 路由块调用 |
|---|---|---|---|---|
| 早期 | 0..8 | [0,9) | 9 | 450 |
| 后期 | 11..19 | [11,20) | 9 | 450 |
| 复用中期 | 6..14 | [6,15) | 9 | 450 |
| 复用 Native | 无 | 原成片 | 0 | 0 |

两份新图只调整引导阶段、运行标识和任务路径。R122 权重、提示词、输入、几何、采样器、sigma、算子保持原绑定。比较目标是蓝色书本的编辑效果与动作保留，包括拿起、翻阅及人与物体的关系；这是既有方法的阶段诊断。

原 R122 的 .9 环境、视频、真实 AV 噪声及完成记录已只读定位。目标拟为 `H3_SERVER_A:/home/researcher/h3_runs/book_guidance_stage_r143_20261020`；GPU3 UUID `GPU-REDACTED`，拟用端口 8626，端口尚未实测预留。运行环境路径在 `configs/runtime.json`；当前未部署目录。

原视频 SHA 为 `ed29fd0615aaeee1f24f103b37bea5f18dc7daebce0159b8ff460492ca6c934c`。原噪声文件为 `/home/researcher/h3_runs/timing_ive_generic_retention_r122_20261020/audit/r122_long_0039_seed2026101701_noise.pt`，SHA 为 `149c638af54913020b9c3f49c5625aba8a44efa3e326738834f6be9e87a1f943`。后续运行须复制并逐字节核对该文件，不能只按 seed 重新生成。Native 和中期视频的具体路径及 SHA 已登记在 `configs/jobs.json`。

.41 已有同 SHA 的 MP4，但 PyAV 解码的 float32 RGB 与 R122 不同。差异出现在 YUV→RGB，早于 VAE；完整 CPU 审计结论保存在 `design/HOST41_RGB_DIFFERENCE.txt`。主代理已选择 .9 同环境方案，不增加 Native，也不做跨环境生成。

当前可执行的 CPU 命令：

```bash
cd /Users/researcher/DevProjects/h3-book-guidance-stage-r143-20261020
PYTHONDONTWRITEBYTECODE=1 python3 scripts/cpu_contract.py
PYTHONDONTWRITEBYTECODE=1 /Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv/bin/python -m unittest discover -s tests -v
```

后续由主代理恢复时的必要接入工作：

1. 从已有 `/Users/researcher/DevProjects/h3-timing-ive-glasses-schedule-r97-20261018` 复用单机顺序 runner；从 R122 复用四个扩展及六份数值文件。数值文件 SHA 已存于 `configs/parent_bindings.json`。改动仅涉及实验登记与验证。
2. 加入采样前硬检查：原 MP4 SHA；同环境 PyAV `gbrpf32le` 全 107 帧 RGB SHA；六个实际干净条件及布局与 R122 完全相等；实际 AV 噪声缓存及两个流 SHA 完全相等。预期值在 `parent_bindings.json` 与 `design/R122_ACTUAL`。条件不符时退出，交由主代理判断，不补跑 Native。
3. 主代理选定实际前置并记录其退出回执。R142 成功不是唯一前置。本轮已知 R142 attempt1 预检退出且 service=null，attempt2 在 dispatch 前资源门拦截，尚未创建。后续应以实际当前状态为准，比较 UID/start_ticks 世代而非要求数字 PID 不存在；不修改或终止其他任务。
4. 部署后在启动前核对 core/权重 SHA、空闲显存至少 40 GiB、GPU 健康、端口与身份；只在独立目录创建服务。顺序执行早期、后期，全部完成或失败后释放准确所属世代；无自动重试、无额外条件。
5. 后验记录两组 20 NFE、20 Euler、各 450 路由块、全部 20 个 AV x0 及最终快照。后期在首次引导前的 0..10 AV 预测应与原 Native 逐元素相等；早期从 0 开始，无可要求的 Native 前缀。OFF 的算子等价不意味着先前引导已经改变的轨迹会恢复成 Native。

缺口：runner、实际父实验读取门槛、前置绑定、部署 manifest、真实 GPU / Flash 行为和成片检查尚未集成或执行。此目录是可复核 CPU 准备包，不能作为 GPU 已就绪的交付。
