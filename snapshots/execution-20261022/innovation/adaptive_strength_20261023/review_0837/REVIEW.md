# 历史 AV 有限前向回放独立审查

审查范围：真实 Euler/音视频归一化、被动 Q/K 捕获、冻结事件索引与诊断分布。只读审查实现；本目录的独立 CPU 测试没有加载模型或占用 GPU。

## 已核对的机制

1. 历史保存的 x0 已经过 `process_latent_out`，视频不变、音频除以 4。重建 sampler carried state 时先把音频 x0 乘回 4，完整 packed AV 共用视频 sigma 的 FP32 Euler 更新顺序。不能另用音频 sigma 更新 raw carried audio。
2. 从真实 `.41` 与 `.9` H3 core 抽取的七个关键源码文件 SHA 一致。运行 Python 的 venv 所在目录不是实际 ComfyUI core；已持久保存实际源码 AST 和 SHA。
3. 四个历史轨迹各 20 步的 CPU 重建完成；最终视频与音频均与历史 sampler_final 逐元素相等。step 9/19 的中间状态仍须通过预先冻结的历史 x0 有限前向门槛。
4. 捕获位置是 qkv projection 的 forward hook，先复制 raw Q/K，随后在原 attention 完成原地 RMSNorm/RoPE 后复制同一缓冲区的实际 Q/K。hook 返回 None、保存 detached 独立 CPU 副本，既不改 attention 算子也不改输出。
5. 稀疏诊断 LSE 是固定空间 probes 的 token softmax 按时间求和；独立逐 head/query/probe 的 dense oracle 与当前计算一致。所有 heads/probes 保留；无效 query/key bins 双边零质量。
6. 六个历史事件的源/普通编辑/固定弱引导区间、视频 SHA、midpoint offset 均与历史协议逐项一致。晚动作使用其生成时刻的 query bins，而 reference event mass 使用源视频时间区间；完整 reference support 不由标签裁剪。

## 审查发现及修复核对

- **真实包装层回调阻断，已修复**：KSAMPLER 即使外部 callback=None，仍给 sampler_function 传内部 k_callback。原有限采样器会以 callback 非空拒绝。独立实际 KSAMPLER AST 测试复现；最终源码改为不调用该内部回调，真实包装层 CPU 测试通过。
- **失败回放的捕获误入分析，已修复**：失败 gate 仍可能留下 qk.pt。初版 evaluator 只验 schema。root 已增加成功 gate、完整 AV 无变化、历史门槛及 case/method/video/capture/input identity 绑定；最终节点与 evaluator 字段已经复核对齐。
- **历史审计文件保护**：原 ScheduleState 构造与 timing wrapper 会写历史路径。派生图必须迁移全部 run/audit/output 路径或删除纯 timing wrapper，并移除原 X0Readout。只修改运行时复制 state.path 不够。
- **生产形状/方法绑定，已修复**：最终包检查 56 heads × 128 dim、native/global_weak 对应 router 模式、冻结 valid_frames，代码与负例测试已核对。

## 数值口径

`FROZEN_REPLAY_GATES.json` 是 GPU 结果产生前冻结的标准：每流历史 NRMSE≤1e−4、P99/RMS≤1e−3、max/RMS≤1e−2；视频和音频均 FP32、shape/finite/身份完全匹配；同状态 hook off/on 完整 AV 逐元素相等。失败时单独定位原因，不自动放宽门槛。

FP32 eager RMS 是诊断定义；实际 fused BF16 输出另做误差统计。由量化后的 RoPE 输出求逆只能做数值诊断，不声称精确恢复。位置 bin 的 frame_spans 是名义物理时间映射，不是精确 VAE 感受野。

最终源码补核：实际 `comfy_kitchen/backends/triton/rms_rope.py` 的 `rms_rope_split_half_` 对 `rot_dim=96 != head_dim=128` 直接调用 eager 分支；当前 H3 的 partial RoPE 并不执行完整 triton fused kernel。实际顺序 oracle 因此应使用冻结 eager AST 的 BF16 RMSNorm 后再 RoPE，显式 FP32 RMS 诊断误差另列。上文 fused 指调用接口，不能据名称推定实际 kernel。

## 独立 CPU 测试

- `test_actual_ksampler_contract.py`：4 项通过；使用生产 KSAMPLER/KSamplerX0Inpaint AST，覆盖内部 callback、有限函数不调用 callback、完整 sigma 及末端 inverse 路径。
- `test_probability_independent.py`：3 项通过；远端 CPU、CUDA_VISIBLE_DEVICES 空；覆盖不同 H/T/P/D 轴的 dense softmax oracle、晚事件索引/符号、静态内容均匀分布。
- 最终 READY 的 22 个资产在本地与独立远端 CPU 副本逐字 SHA 一致；36 项包测试独立重跑全部通过（0.642 秒）。四份历史轨迹在增强 metadata/final tensor SHA 校验后重新 audit-only 通过。

发布状态：**APPROVED_LIMITED_FIRST_PROBE**，详见 `SIGNOFF.json`：只限 short_0358 native、step 9、layer 25、off/on 两次完整 AV 前向。READY `cfbd56b99eaec984fcd64aa0f2786ef3d7588e3fff75777117a874354d1b65aa`；派生图 `411e62520a7a45e5aec97d46886f566720ddcc1c2581924ca5a78c1d9a64160d`。

实际图保留模型、sigma shift 和完整 sigma grid；原 native 的 6..14 路由区间通过 fixed schedule 保持，缓存与原噪声均按 SHA 绑定；全部旧 writers/VAE/CLIP/完整采样节点已移除，新 writer 路径均在隔离目录。当前 checkpoint 又完成 20.97GB 全字节 CPU SHA 复核，与历史一致。

此签审允许执行上述有限核验，不放行额外样例、步数或控制器。CPU fixture 的小模型部分仍是模拟；实际 GPU 捕获能否用于动作相位解释，由冻结历史 AV 门槛和随后独立 fused 数值诊断决定。
