# 逐时间 bin 强度场：CPU 原型交接

严格凸、因果逐 bin 锚定控制器已经完成，19 项 CPU 测试通过。代码与设计已冻结，哈希见 READY.json。未部署、未推理视频。

- prototype.py：update_gain_field、box tridiagonal active-set 求解器及 probe 聚合。
- DESIGN.md：目标、归一化、边界、KKT、计算量与最小实验。
- LAYER_NEXT.md：独立的一步滞后层预算设计。
- test_result.json：19 项测试，包含独立穷举 active-set oracle。
- cpu_timing.json：1000 次 CPU 调用，T=29 平均 0.881 ms；T=41 平均 0.929 ms。不含 GPU 同步或 Attention。

首个有效步、无证据 bin 与选中窗口两端 alpha=.25；无证据处切断平滑边。其余 bin 在 [0,.5] 求解；mu=1 时实际理论正下界 1/28，因此称连续强度调节，不称二元起停。lambda=.625 固定。

后续独立节点实现位于 innovation/feature_gain_field，保持原 anchor 与在线队列不变。
