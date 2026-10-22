# 与已有 RoPE 方法的关系（2026-10-22 核对）

本目录属于已有 reference-only PhaseRoPE 的部分频带消融实现；目前没有新颖性结论。以下是官方论文或作者代码中直接相关的机制，范围是简短核对而非完整文献检索。

| 方法与一手来源 | 已有机制 | 与本实现的关系 |
| --- | --- | --- |
| [RIFLEx 论文](https://arxiv.org/abs/2502.15894)、[作者官方代码](https://github.com/thu-ml/DiT-Extrapolation) | 识别并降低一个 intrinsic RoPE frequency，使长度外推时不易周期重复；官方代码对所选 `freqs[k-1]` 重新赋值。 | 已有“仅干预选定 RoPE 频率”的直接先例。本实现保留 checkpoint 频率，在额外参考分支上对部分 Q 时间对增加常数相位，研究问题是参考条件路由。 |
| [VideoRoPE](https://arxiv.org/abs/2502.05173) | 将低频分配给时间轴，采用三维布局和可调时间间距，面向视频理解/检索等。 | 说明时间频率选择有明确先例；它修改位置编码设计，本实现保持 H3 固有三轴布局。 |
| [RoPECraft 论文](https://arxiv.org/html/2505.13344v2) | 用参考光流位移扭曲 RoPE，再通过轨迹/速度对齐优化，并使用 Fourier phase regularization。 | 已有通过 RoPE 控制视频运动的直接先例。本实现没有光流扭曲或优化，只有固定 mask 与显式 delta 的条件注意力修正。 |
| [FFP-300K / AST-RoPE](https://arxiv.org/abs/2601.01720) | 通过自适应时空位置重映射区分外观与动作参考，并结合训练与自蒸馏。 | 已有通过参考流位置编码处理外观/动作张力的相关方案。本实现是 H3 推理时选频补偿的实验模块。 |

H3 接口另核对了 [ComfyUI 官方 model.py](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/ldm/minimax/model.py)。实际实现以本目录保存的正在运行版本源码及其 SHA256 为准，不依赖后续 master 版本的布局。

历史全带基线为 `legacy_phase_core.py`，来源路径与 SHA256 见 `provenance.json`。全 mask 的旋转与注意力公式直接对照该文件执行 CPU 测试。创新研究的下一步是判断部分频带相位补偿是否比全频带补偿、零补偿和参考增强对照更稳定，而非仅凭工程差异作新颖性判断。
