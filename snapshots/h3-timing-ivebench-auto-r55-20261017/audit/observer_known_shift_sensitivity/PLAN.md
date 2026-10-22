# 原 R55 observer 的已知时移 CPU 诊断

目的：检验固定五条 IVEBench 源姿态中的运动，在施加已知物理时移后，原 R55 检测器是否能给出可靠 lag、候选和持续两次观测后的 ON。这里的目标姿态为合成诊断输入；结果不代表生成视频质量或在线去噪效果。

1. 固定原 R55 protocol 的全部五条 source90 pose、原脚本及依赖 SHA；不改变 producer。
2. 固定 d = -8,-4,0,4,8 帧（24 fps）。目标物理帧 t 对应源内容 t-d。有效域为原案例的 valid prefix；越界及原 terminal padding 的全部关节置信为 0，并保存原物理时间与内容索引 ledger。无环绕、插值、时间压缩或端点复制。
3. 用原 scanner、原几何窗口、confidence 0.3/0.5、lag [-24,24]、原全部可靠性门和 gain >0.5，调用 signed selector。相同观测连续提交 index 0、1 仅检验 persistence 能否达到 ON。
4. 保存全部 25 格的完整 scan、selector 输出及摘要。逐案例报告，不将重叠窗口与左右臂视作独立样本。UNKNOWN 保留具体原因，OFF 不解释为同步。
5. 定向测试物理索引、置信继承、越界、d=0、SHA 和 selector persistence。零 GPU、零新姿态提取、零依赖安装。
6. 可独立附录 R56 已冻结 arm-only helper，保持相同阈值/selector，仅定位 torso 入口门的影响；不得混写成原 R55。

已有检查检索：R55 audit/scripts/tests/configs 与 R56 全目录中有数学合成 self_test、源姿态支持和最终 Native 扫描，以及 CoTracker MF 敏感性诊断；没有此固定五条 source90 的 25 格 scan+signed selector 诊断。
