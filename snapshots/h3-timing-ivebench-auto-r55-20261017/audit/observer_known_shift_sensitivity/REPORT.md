# 已知物理时移下的 observer 检测能力

原 R55 在固定五条源姿态中的两条可检测全部预设非零时移；另外三条在躯干置信入口返回 UNKNOWN。对这些样例，持续 OFF 不能支持“生成动作同步”的判断。

本诊断只构造源姿态的物理时移，未生成视频、未调用姿态模型，未改变线上 producer。原 R55 与 R56 附录分别记录。

## 固定输入与协议

- 全部五条原 source90 姿态，统计有效帧数依次为 87、86、74、78、89。
- 固定 d = −8、−4、0、4、8 帧，24 fps。正 d 表示目标延后；4/8 帧对应 166.7/333.3 ms。
- 目标物理帧 t 取源内容 t−d。物理帧号/秒数维持 t，越界与原 padding 置信置零；各 `.pose.json` 的 ledger 保留有效掩码与源内容索引。
- 调用已复制并 SHA 绑定的原 scan、Geometry、signed selector；confidence 0.3/0.5、窗口 16/32 帧、stride 4、lag 搜索 ±24 帧、gain >0.5 均沿原实现。
- 相同观测依次提交 index 0、1，仅检查持续两次后能否触发 ON。在线去噪会改变姿态，故该重复不证明真实在线启动效果。

## 原 R55：完整 5 × 5 结果

每格为 **可靠 lag / 合格候选行数 / 第二次相同观测是否 ON**。可靠 lag 要求两个 confidence 均有结果且一致；本次所有可报告 lag 均精确等于已知时移。候选行按 window×arm 统计，重叠较多，仅描述控制器内部状态。

| 原源样例 | d=−8 | d=−4 | d=0 | d=4 | d=8 |
|---|---|---|---|---|---|
| short_0210 | -8 / 81 / ON | -4 / 96 / ON | 0 / 0 / OFF | 4 / 96 / ON | 8 / 84 / ON |
| short_0230 | -8 / 46 / ON | -4 / 61 / ON | 0 / 0 / OFF | 4 / 67 / ON | 8 / 56 / ON |
| short_0263 | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF |
| short_0352 | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF |
| short_0370 | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF | UNKNOWN（躯干入口） / 0 / OFF |

- 非零时移：2/5 个源样例的四个方向/幅度均可识别，共 8/20 格可触发；其余 12/20 格为 UNKNOWN。
- 零时移：2/5 可报告 lag=0；3/5 为 UNKNOWN；5/5 均未触发。
- short_0263 在 confidence 0.5 缺少可靠躯干锚点；short_0352 与 short_0370 在 0.3 和 0.5 都缺少。任一置信入口失败会使整次 scan 提前返回。

## R56 上肢特征入口：独立附录

附录仅在离线 scanner 中替换为已冻结的 `arm_features.py`。原上肢方向计算逐式保留；窗口、置信、可靠性、gain、selector 和持续性门均沿原版本。该 helper 没有接入当前 R55。

| 原源样例 | d=−8 | d=−4 | d=0 | d=4 | d=8 |
|---|---|---|---|---|---|
| short_0210 | -8 / 81 / ON | -4 / 96 / ON | 0 / 0 / OFF | 4 / 96 / ON | 8 / 84 / ON |
| short_0230 | -8 / 46 / ON | -4 / 61 / ON | 0 / 0 / OFF | 4 / 67 / ON | 8 / 56 / ON |
| short_0263 | -8 / 48 / ON | -4 / 58 / ON | 0 / 0 / OFF | 4 / 55 / ON | 8 / 45 / ON |
| short_0352 | UNKNOWN（上肢覆盖） / 0 / OFF | UNKNOWN（上肢覆盖） / 0 / OFF | UNKNOWN（上肢覆盖） / 0 / OFF | UNKNOWN（上肢覆盖） / 0 / OFF | UNKNOWN（上肢覆盖） / 0 / OFF |
| short_0370 | -8 / 26 / ON | -4 / 30 / ON | 0 / 0 / OFF | 4 / 33 / ON | 8 / 29 / ON |

- R56 对 4/5 个源样例的全部非零时移可识别，共 16/20 格可触发；short_0352 的四格为 UNKNOWN。
- R56 零时移有 4/5 个可靠 lag=0，1/5 UNKNOWN；5/5 均未触发。
- short_0352 在 d=0 的 90 个 window×arm 行均因覆盖不足返回 UNKNOWN；这保留了原 0.8 coverage 与至少 8 个有效帧门。
- 原本可观测的 short_0210、short_0230 在两个版本的可靠 lag 和合格候选计数一致。

## 对当前实验结论的影响

当前 R55 的 OFF 至少包含两种事实：可观测且未达到干预条件；源/目标姿态无法可靠测量。报告应同时给 observer status、UNKNOWN 原因和干预次数。三条源入口失败的样例，无法通过原控制器评价自动时序干预的有效性。

本诊断支持排查躯干入口对上肢观测的适用性影响。它尚未测量编辑造成的动作类型改变、遮挡、身份变化或小幅局部时移，且没有产生新视频质量证据。固定五个源样例是分析单位；25 个格、重叠窗口和左右臂不构成独立视频样本。

## 实现出处与验证

- `source_snapshot/scripts/timing_metrics.py:47–56`：计算 shoulder/hip torso scale，在缺少可靠锚点时抛错。上肢方向随后于 59–67 行单独由局部骨向量归一化。
- `source_snapshot/scripts/scan_current_pose.py:24–32`：任一输入/置信的 torso scale 异常导致整次 `unknown_visibility`；33–46 行扫描原窗口与双置信一致性。
- `source_snapshot/scripts/pairwise_gain.py:19–29`：原共同支持和残差质量门。
- `source_snapshot/scripts/automatic_window_policy.py` 与 `delayed_window_policy.py`：原 signed 候选与前后两次持久性判断。
- 定向 CPU 测试 6 项通过。`verify_results.py` 验证两版本全部 50 格：源/目标/结果 SHA、所有内容索引及置信、90 帧几何、保存摘要与 selector 再计算一致。
- 原 R55 scan 用时 10.586 秒；R56 附录 21.585 秒。GPU 调用 0；新 pose 调用 0。

## 文件

- `PROTOCOL.json`：运行前冻结的输入、变换、阈值和源代码 SHA。
- `r55_original/SUMMARY.json`：原 R55 的完整 25 格摘要。
- `r56_arm_only/SUMMARY.json`：独立 R56 附录的 25 格摘要。
- 两目录中的 `.pose.json`：合成姿态和物理索引 ledger；`.scan.json.gz`：完整原 scanner 曲线与 selector 输出。
- `VERIFIED.json`、`CPU_TESTS.log`、`VERIFY.log`：验证记录。
