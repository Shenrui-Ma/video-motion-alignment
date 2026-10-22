Sam .9 分支已完成 CPU 验证并交由 root 启动，运行包冻结。

- 远端：`/home/researcher/h3_runs/guidance_schedule_r149_host9_20261020/cases/05_real_megumi_v`
- Seal：`8d384204d378c5ea6c626a69fc9e851a7d0d21e06e7c52a15b359a2d9bcd77c4`
- 11 本地 + 11 目标 CPU 测试；实际 Comfy namespace、五缓存重建、四臂 fresh ModelPatcher 状态检查通过，CPU 证明无 CUDA 初始化。
- 所有数值扩展与原 .41 包逐字一致，九个 Comfy 关键源码 SHA 相同；直接复用 .9 原条件和噪声。
- GPU1 最低空闲20GiB，reserve8，沿已有 normal model manager 根据实际空闲显存部分 CPU 卸载。Host9 为 cgroup v1：主机 RAM 入口64GiB、运行40GiB；真实有限祖先采用 raw 余量入口46/运行20GiB，内存事件变化和监测失败精确停止本任务。
- Torch2.5.1+cu121 / Triton3.1.0 与 .41 环境差异已记录，没有增加跨环境一致性 GPU 实验。
- 逐臂/总完成/精确释放沿原 R149 协议；评测代理已收到新根与 seal。
- cabin 的 .9 备用分支仅 CPU 完成后保留；当前 root 使用 .41 原冻结 cabin。

2026-10-20 行政监控修复：.9 内核3.10无 pidfd，首次启动在 CUDA 前结束。新 seal `5fa5b4714f0c4790d2176e8505605cc9db5c35d3133585593da19f5229cf3274`；监控改向真实 supervisor 提交精确世代停止请求，父进程以 waitid(WNOWAIT) 保留子进程 PID 后发送信号。16 项目标 CPU 测试＋实际 system Python 的5项受控子进程测试通过；旧失败和封存保留。Root 使用新 review/attempt 重试。
