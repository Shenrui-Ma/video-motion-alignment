# Reference phase → temporal RoPE：近邻核对与可否决条件

2026-10-18。仅研究审查；现行实验保持原参数。范围为指定六项工作的论文，以及 ReTime 和 H3MotionLab 的固定版本代码。尚不能据此声称新颖性或有效性。

## 最接近的已有机制

**ReTime 已把内容测得的时间进度变成 temporal RoPE 重参数化。** 它先用视频的 Semantic Progress Function 求逆时间映射，在 Q/K 的 temporal RoPE 中使用新坐标，并按频段、去噪时间调节强度。论文还含重新生成、重新测量进度、再更新坐标的迭代。代码 `retime.py:281–340` 每步根据 sigma 调整预先得到的映射；该函数内没有从当前 x0 与外部参考动作估计身体部位相位。候选与它的可检验区别是“同一次去噪中的参考动作对应反馈，作用于 reference stream”。仅换成姿态特征、换模型或换名称，贡献仍很接近。[论文 §4.1](https://arxiv.org/html/2604.22554v1#S4.SS1)；[固定代码](https://github.com/SagiPolaczek/semantic-progress-function/blob/bf5a388378d5153a9b25ae4a64c2de377e62f48f/spf/retime.py)。

**H3MotionLab 的 H3DyRoPE 已实现 H3 的分层、随 sigma 变化的时间坐标修改。** `dyrope_video_rows` 定位 packed sequence 最后的目标视频；`dyrope_retimed_position_ids` 只改这些行的 t 列；`_install_dyrope_rope_patch` 按 physical/compact spans 生成坐标；`_dyrope_block_patch` 更换指定 DiT blocks 的旋转表。它支持单调 spans 混合和 sigma fade。该版本以 hold map/geometry 为输入，所读部分没有 source 与当前 x0 的可见部位相位匹配。H3 上改变 RoPE、指定层和去噪区间已有直接软件先例。[代码 1940–2121](https://github.com/matlowai/ComfyUI-MAINodes/blob/f4868b4a08e8a504ce86db54a17961d399ffa2bc/motion.py#L1940)。

**DIAL Phase I** 由前一步 ISGM 决定空间位置，并向 video-query/reference-key logits 加 `log(γ)·ISGM`。其空间局部性和逐步更新已有实质重合。论文的最终 80% 采样步指跳过前 20%，并非到 80% 才启动。候选的时间对应与坐标重参数化和其 additive bias 有区别；“根据局部信号增强参考”本身已被覆盖。[§3.3、式 6–7、Algorithm 1](https://arxiv.org/html/2609.11507v1#S3.SS3)。

**TempoControl** 把 video-to-text attention 的时间曲线对齐用户 temporal mask，用相关性、强度、空间熵目标优化 latent，包含相关性 early stopping。已覆盖测量控制误差、在推理中更新和提前停；所读方法没有 reference-video RoPE 相位改写。[§4](https://arxiv.org/html/2510.02226v3#S4)。

**MotionEcho** 用滑动平均运动损失启动教师纠正，教师损失达到阈值时截断，再混合 clean endpoint。DiT 版本还使用参考 K/V 注入。动态启动/停止、按动作误差控制已存在；所读方法没有这里的 reference temporal-coordinate feedback。[§3.3–3.5](https://arxiv.org/html/2506.19348v2#S3.SS3)。

**FlowMotion** 对 source/target predicted-clean latent 及帧间差分做对齐，以历史平均速度约束更新方向。已覆盖无需额外教师的在线源动作纠偏；其目标直接改变 latent/生成轨迹，所读方法未估计局部单调时间对应再改 reference RoPE。[§3.2–3.4](https://arxiv.org/html/2603.06289v2#S3.SS2)。

## 候选必须先说明的控制量

以下是本次推导，尚未验证为控制方法。仅写 temporal 子空间，忽略共同的空间/模态项：

`ℓ(t,u) = q_tᵀ R(r_ref(u) − r_out(t)) k_u / √d`。

改 reference 坐标 `r_ref(u) → r_ref′(u)` 会改变跨 stream 的相对旋转。直接改 reference K 会影响所有读取这些 keys 的 queries；同时改 reference Q 还会改变参考 token 对其他 token 的读取。完整模型中“只改坐标”仍会通过后续层改变外观与 latent，不能据此保证只改动作。

设当前生成 `g(t)=s(t−d)`，d>0 表示延后。**观测对应是 u=t−d，而编辑任务期望对应是 u=t。** 如果只是让当前相似姿态的 Q/K 更容易匹配，可能加强已有延后。因此必须写清“测得对应→希望纠正的对应→坐标位移”的符号和逆映射，先验证控制响应方向。RoPE 的振荡和内容内积意味着坐标移动 4 帧并不保证动作移动 4 帧。

若同一组 target 与 reference 坐标共同平移，彼此的相对 temporal rotation 抵消；非线性共同 warp 则另会改变内部距离。单个 key 的全局位置不能同时实现左臂和右臂各自不同的 query-dependent 对应。后者需要在 attention 交互范围上另做限定，且须核算额外开销。**姿态可见性门控与 query 空间 mask 是两个独立部件。**

H3 的物理帧、非均匀 token spans 和多参考 stream offset 必须分别处理，不能照搬 Wan 的 4× VAE 坐标。这里保持 tensor 的时间排列，仅改相对位置；之前的候选 C 是重采样 x0 tensor 后改 Euler endpoint。两者作用位置不同，但都属于已有时间重参数化家族。当前 R70 的 VAE 检验有助于 C 的可行性判断，不能替这个 RoPE 候选提供成功证据。

## 最小可否决实验建议

1. **先检验对应，再接模型。** 复用冻结 source pose、已知 ±4/±8 帧移位、零移位、遮挡和 R60/R61 跨动作反例。记录每个真实物理时刻的 source/target index、可见性和匹配残差。零移位须保持 identity，遮挡须 UNKNOWN；事件类型改变时不把偶然相似的上臂方向当可靠相位。原跨案例反例必须保留，不为通过它调阈值。若已有观测器在这些条件下失败，不能直接包装为自动控制。
2. **由 root 决定的短 GPU 控制响应试验，尚未执行。** 固定一个确有同类动作时间差的已存 noisy state、sigma、条件、后续噪声和一份人工诊断对应，先比较 identity、reference 时间坐标 +Δ、−Δ 三个极小分支。全部记录同帧事件时间、姿态形状与编辑内容。identity 必须复现；正确符号与相反符号应产生可区分的定向响应。若只改变外观/幅度，或两种符号同样恶化，则停止把该偏移当时序执行器。这里的人工对应仅验证执行器，不报告自动化成功。
3. 若执行器通过，再比较同一对应作用于 target stream（ReTime/H3DyRoPE 接近的对照）与 reference stream；然后把人工对应换成已冻结估计器。分别回答“作用 stream 的差别”和“在线估计能否复现”，保留失败及 UNKNOWN 分母。当前 Native/固定 ON 队列继续原方案。

建议把候选表述为“参考与生成的时间对应是否可通过 reference stream 的相对位置控制”，并把它与 ReTime 的完整机制直接对比。当前证据支持进一步做可否决检查；尚无证据证明它具有独立创新或能改善 H3 的动作时间。

固定版本、源码 SHA 与行号见 `EVIDENCE.json`。本文件未新增模型、阈值或推理实现。
