# H3 部分时间 RoPE 频带补偿

状态：独立实现与 CPU 验证完成，GPU 推理与效果验证待执行。全部实现和证据在本目录；未安装到当前服务，未更改 64 条实验、已排图或冻结 H3Study core。

## 机制与参数

对已执行原生 RoPE 的输出视频查询 `Q`，只旋转 mask 指定的时间通道对。第 `i` 对的附加相位为：

`theta_i = mask_i * delta_frames * (5/3) * diffusion.rope.inv_freq[i]`

原联合注意力输入 `Q/K/V` 保持原值；额外分支仅使用所选输出视频行和完整参考视频 `K/V`。输出采用旧 PhaseRoPE 的组质量保持公式：

`O_new = O_native + alpha * m_ref * (A(Q_rotated, K_ref, V_ref) - A(Q, K_ref, V_ref))`

`m_ref = exp(LSE_ref(Q) - LSE_joint(Q))` 取自旋转前的同一层输入。此式保持本层参考视频组总概率质量，将改变限制为该组内条件分布，并将结果混合到指定输出行。它不会屏蔽参考帧，参考身份图片不进入额外分支。

| 参数 | 精确定义 |
| --- | --- |
| `enabled` | 默认 false；控制补偿开关。节点仍经过与 H3Study 相同的 Flash 全注意力审计路径。 |
| `frequency_mask` | JSON 数组，16 个 0/1，按真实 `rope.inv_freq` 顺序。只写所选 `(i,i+48)` 对。 |
| `delta_frames` | 物理视频帧单位的额外 Q 时间偏移。正值增加 Q 坐标；动作提前/滞后须由视频测量确定。 |
| `alpha` | `[0,1]`，混合参考分支的输出修正，不缩放旋转角。 |
| `schedule` | 与冻结 H3Study 相同的零起始 step 集合；新增 `all`。`global_weak` 只指定 20 步，弱化强度由 alpha 明确给定。 |
| `start_frame/end_frame` | 物理帧闭区间，经现有 H3 positional-bin 映射选择输出查询；不是精确 VAE 感受野。 |
| `block_start/block_end` | DiT 块半开区间，范围 `[0,50)`。 |

给定 layout，完全抵消参考/输出原点差所需偏移为：

`delta_frames = (key_first_time_coordinate - query_first_time_coordinate) / (5/3)`

这个值使对应视频位置的所选时间频带相位对齐；可再叠加显式帧偏移。默认 delta 为零，不自动猜补偿量。全 mask 恢复旧的全时间频带 PhaseRoPE；零 mask、零 delta、零 alpha 和禁用开关都跳过额外分支。

## 真实源码与 checkpoint 证据

2026-10-22 只读获取 H3_SERVER_A 当前冻结 `comfy/ldm/minimax/model.py` 与 Kitchen eager RoPE；另核对 H3_SERVER_B 的 model.py，完整文件 SHA256 与 host9 相同。原文件、路径及 SHA256 在 `sources/`。适配器用规范化 AST 摘要核对位置生成和 Attention.forward，源码改变时拒绝启用，避免静默套用其他布局。

1. `MiniMaxH3Model.rope_freqs` 先将三轴位置乘以实际 16 项 `inv_freq`，再构造 `[t16,h16,w16,t16,h16,w16]`，共 96 维。
2. `rope_rotation_table` 使用前 48 个角生成二维旋转矩阵。
3. `Attention.forward` 在 `optimized_attention` 之前对 Q/K 做 RMSNorm 和 `rms_rope_split_half_`；额外分支收到的 Q/K 已经完成原生旋转。
4. Kitchen `_rms_rope1` 只旋转前 96 维，`apply_rope_split_half1` 将首尾 48 维配对。时间对因此是 `(i,i+48), i=0..15`，空间通道 `16:48`、`64:96`，无 RoPE 尾部 `96:128`。
5. 时间坐标是 `[1,4,4,4,4]` 周期跨度的前缀和，再乘 `5/3`，不是固定四帧一个 token。

另从当前 `minimax_h3_ref2va_pruned_int8_convrot.safetensors` 只读取 95,416 字节 header 和 64 字节 `rope.inv_freq`；记录在 `sources/checkpoint_inv_freq.json`，没有加载权重或初始化 CUDA。该实测 buffer 从 `1.0` 递减到 `0.00017782794`，所以本 checkpoint 的索引 `0..7` 是较高频、`8..15` 是较低频。程序不重建或改写 buffer，运行审计会保存真实值、hash 与所选频带的物理帧周期。

## 运行方式与边界

CPU 小张量测试只需要已有 PyTorch，无 ComfyUI 导入和新增依赖：

```bash
cd /Users/researcher/DevProjects/video-motion-alignment/execution-20261022/innovation/partial_rope
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv/bin/python \
  -m unittest discover -s tests -v
```

未来独立 Comfy 实验可将 `H3PartialRoPE/` 作为独立 custom node 包安装，并用 `H3PartialRoPE` 替代图中的 H3StudySchedule 方法节点。连接原 model 和 positive conditioning；使用唯一 run_id 与绝对 audit_dir。不要叠加 H3StudySchedule、旧 PhaseRoPE、Sage attention 或其他 DiT/attention patch。本次没有执行安装或图修改。

适配范围：已审计 host9/host41 H3 源码、50 个 DiT 块、56 heads × 128 dim、单批次、单参考视频、可选一个身份图片、目标与参考视频几何一致、20 次单分支 denoiser forward（预期 Euler20，无 CFG 交错）、显式 21 项递减 sigma 序列、原生 `attention_pytorch` 入口、CUDA fp16/bf16 Flash+LSE。其他源码版本先重审 contract；短测试使用注入的 CPU dense oracle，生产路径没有 dense fallback。

验证包括：delta0、mask0、alpha0、disabled 的恒等性；正负旋转与逆变换；范数；空间/尾部/未选时间对逐位不变；全频带与历史源码数值一致；真实 checkpoint 频率；真实源码/kernel 的角度平移等价；显式概率矩阵的参考组质量保持；Q/K/V 不变；仅所选输出行变化；20 步共 1000 块的适配器状态及审计生命周期。结果见 `reports/verification.json`。

尚待 GPU 验证：现有 Torch/Flash ABI 与 dtype 误差、实际源配置的分支调用/内存与耗时、真实完整图运行，以及对参考动作时间、背景泄漏、身份和编辑一致性的影响。CPU 测试证明实现的代数与接口约束；方法效果须由后续同源、同 seed、同配置实验回答。相关方法对照见 `sources/related_work.md`。
