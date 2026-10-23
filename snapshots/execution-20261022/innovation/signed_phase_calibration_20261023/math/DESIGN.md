# 有符号检索相位：CPU 方程、反例与推进判断

**本轮结论：只值得做被动信号校准，尚不值得提交新的动态 α 控制实验。** 26 项 CPU 检查验证了导数公式、局部链与失败反例。外观变化可以与真实时间移位产生完全相同的观测；位置组可以掩盖小位移；当前 Attention 的输出修正也不会改变已经计算的 Q/K。数学求解器正确，尚未提供可辨识的动作误差。

范围限于本目录。没有修改方法、采集 hook、运行队列；没有 GPU 任务、VAE 解码或新模型。已与 `adaptive_strength_20261023/review_0807/DECISION_AND_CALIBRATION.md` 和 `H3_SOURCE_MAP_AND_CAPTURE.md` 对齐。

## 1. 要观测的量与符号

以固定空间 probes 的同一 head 为单位，在视频时间 bin j 上构造

\[
 z_j(q)=\log\frac1{P_j}\sum_r\exp(q^T k_{j,r}/\sqrt d),\quad
 p_j=\operatorname{softmax}_j z_j,\quad
 \mu=\sum_jp_j\tau_j,\quad e=\tau_t-\mu.
\]

τ 是相对序列起点的名义物理帧中心，不用 packed origin。正 e 表示 query 的内容检索偏向更早的参考位置，是**候选的延后读数**。API `phase()` 为方便求导返回相反号 `retrieval_error=μ−τ_t`；设计的 e 和 s 同时取负，最小二乘结果不变。这一约定在测试中明确保留。

这里的 sparse、去本层显式 RoPE 的 p 是独立诊断分布；它不是原完整参考 attention 的精确时间概率。P_j 不等时，logmeanexp 与原有求和概率也不同。首轮必须固定同一空间采样、保留各 head 的完整 p、峰位置和多峰情况；不要先平均 head/probe 的有符号误差。两个相反偏移能平均为 0。

Q/K 经本层逆 RoPE 后仍含此前层混入的位置、主体、镜头和 VAE 组内位置特征。源码支持“去掉本层显式旋转”，不支持把所得向量称为纯动作。可以同时报告参考 query→参考 keys 的自比偏差，用于暴露本身的定位偏好；减去自比偏差仅在偏置跨源/生成保持不变时有效。

## 2. 当前层的两个简单导数都不能给动作收益

现有实现先由 Q/K/V 求完整 O、参考 R、同时间 S_t，然后加

\[
 D=m(S_t-R),\qquad O'=O+\alpha D.
\]

Q/K 已经计算完。保持本次输入不变，原 p(Q,K) 对当前 α 的导数**严格为 0**。不能因 Q 和 D 的最后一维相同，就令 Q'=Q+αD；它们处在不同线性映射、归一化和残差位置。

若改用当前算子直接定义的参考时间分布

\[
 p_\alpha=(1-\alpha)p+\alpha\delta_t,
\]

则 e_α=(1−α)e，导数为 −e。在 [0,.5] 上最小化 e_α² 必然取 .5（e≠0）。该结果与 V、输出投影、后续网络和动作是否正确都无关，是更新定义的代数性质。本轮测试将它作为负面设计，没有当作成功校准。

## 3. 有意义的方向导数必须经过真实局部链

已核查的 H3 `DiTBlock` 路径是：

\[
 z(a)=x+g_A\odot W_o(O+aD),\qquad
 F(a)=z(a)+g_M\odot\mathrm{MLP}(\mathrm{ModNorm}_2(z(a))),
\]
\[
 q_{\ell+1}(a)=\mathrm{QNorm}\bigl(W_{Q,\ell+1}
    \mathrm{ModNorm}_{1,\ell+1}(F(a))\bigr).
\]

实际 `ModNorm` 包含 RMSNorm 权重和按模态/时间行选取的 AdaLN scale、shift；MLP 为 SwiGLU。reference 与 canvas 的 timestep/gate 可能不同，masked 布局还允许逐 token 行选择。下一层读出应使用**下一层** reference K，不能拿当前 K 或上个去噪步 K 冒充同一状态。

当前层的 full attention 已同时算出 reference 和 canvas 输出。只改变 canvas 输出，之后到下一层 Q/K 之前的运算均逐 token，所以这个局部检验中 next-reference K 可固定。再经过下一次 joint attention，reference 会受到生成分支影响；该局部导数不等于整网或最终视频的导数。

在固定 reference K 下，令 q'=dq/da，则

\[
 z'_j=\sum_r p(r\mid j,q)\,k_{j,r}^Tq'/\sqrt d,\qquad
 s=de/da=-\operatorname{Cov}_{p}(\tau,z').
\]

每 bin 的 logit 导数必须是其内部 softmax 加权和，直接平均空间 keys 的导数通常不对。`grouped_lse_derivative()` 与逐 token oracle 已互相核验。

CPU `continuous_local_chain()` 含输出投影、两次 gated residual、RMS/AdaLN、SwiGLU、next Q 投影/QNorm；解析 JVP 与独立中心差分一致。它使用小型 float64 连续矩阵，是结构 oracle，不是量化 H3 模型仿真。实际 INT8 激活量化可能出现局部平坦、阈值跳变、shape 相关数值变化，不能将此 JVP 直接视为真实 H3 导数。后续应以真实调用的预定非零扰动检查 s 的符号和局部曲率。

若将来在当前层应用 α 前计算该链，next-reference K 尚未正常产生。省计算的路径是：固定参考 probes 也走其真实 gate/MLP/next K，只构成一个稀疏 observer；如果坚持完整 reference keys 的精确 LSE，就需提前重算整段 reference FFN/next K，成本明显更大。当前阶段仅被动采集，不做任何局部重算。

## 4. 最小二乘能解决什么

在已校准的观测集合上，于 ā=.25 附近线性化：

\[
 e_i(a)\simeq e_i(\bar a)+(a-\bar a)s_i,
 \quad a^*=\operatorname{clip}_{[0,.5]}
 \left(\bar a-\frac{\sum_iw_ie_is_i}{\sum_iw_is_i^2}\right).
\]

分母为正时是严格凸一维二次目标，唯一 box 解；端点梯度满足 KKT。分母为 0 时没有方向信息，保留 .25。可以进一步限制在一个预登记的小信赖区间，但本轮不为真实模型选阈值或步长。`box_linearized_ls()` 使用 ā=0 的等价简化 oracle，检验了闭式解对稠密一维搜索及端点 KKT。

应聚合 Σw e s 和 Σw s²，而不是先平均 e、s 再求解。误差为 −4/+4、敏感度为 +2/−2 的两个位置，均值都为0，但两处都支持同方向修正。

仅有真实一阶导数也不保证大步改善。测试构造可微非线性观察器，线性最小二乘的候选反而增加实际误差。若 logits 对 a 确为仿射，则

\[
 e''=-\mathbb E[(\tau-\mu)(z'-\mathbb E z')^2],
 \quad |e''|\le \operatorname{range}(\tau)\operatorname{range}(z')^2.
\]

这可给出局部线性余项上界；H3 的 norm/FFN/量化会让 logits 非仿射，因此该界不能直接沿用。无可靠误差观测时，换信赖域求解器不会修复可辨识性。

## 5. CPU 反例与可辨识条件

| 条件 | 本轮构造与结果 |
|---|---|
| 已知正负移位 | 非周期 Gaussian 内容序列在公共内区准确恢复 ±3/±7 的检索符号。证明方程可工作，不涉及真实动作语义。 |
| 保持组内位置、只移动内容 | 固定 t mod 5 的角色偏好；±5/±10 可恢复，但真实1bin内容位移可被强角色项压成近0。不能以全向量移位通过代替该检查。 |
| 零延迟外观变化 | 构造外观项改变 query 的时间相关方向，得到与真实5bin延迟完全相同的 Q/K、p，甚至相同 V/D；两种真实相位无法由这些观测区分。 |
| 静态姿态 | 相同 keys/values 使时间无信息。分布重心可远离当前 t，只反映参考范围。静态动作不能由该观察器强行分配相位。 |
| 周期或重复动作 | 两个等强 ±10 峰的均值正好0，而同时间位置概率几乎0。均值0并非唯一对应。 |
| 镜头而非主体运动 | 只编码镜头位置的 keys/query 产生明确时间偏移，静止主体动作并无延迟。 |
| 不同 RoPE origin | 常量内容仅经位置旋转即可形成带符号偏移；减去坐标 origin 不会改变受旋转影响的 logits。去本层旋转后该例变为无信息，而非可靠动作定位。 |
| 稀疏空间遗漏 | 已取 probes 均静态/无偏移，未取位置可以分别拥有相反的强时间证据；采样外的动作相位不可确定。 |
| 平方量丢符号 | D 与 −D 的切向平方能量一致；相同局部观测允许后续 Jacobian 正负翻转，s 及真实修正收益可相反。 |
| 数值量化 | 极小差分落在同一量化台阶时为0，有限剂量跨阈值后非0；无需诉诸随机误差即可失败。 |

足够条件至少包括：参考在候选局部区间具有唯一可辨识时间内容；编辑后的 query 对动作相位保持可校准对应；外观/镜头/位置组不与动作相位混淆；采样覆盖有关主体；真实局部链能提供稳定的 signed sensitivity。当前没有同时满足这些条件的真实证据。

故下一项是观测校准，不是新控制器。需要在固定 native/weak 事件上看到前者有真实延后读数、后者回到参考附近，同时报告所有事件、未知/多峰及零移外观反例。不能从本批结果挑 head、层或 probes。

## 6. 代码与已验证范围

- `oracle.py`：概率、精确协方差导数、分组 LSE、连续局部链、仅 oracle 的一维 LS。
- `test_oracle.py`：26 项本机 CPU 测试；根线程另独立执行同26项通过。
- `TEST_RESULTS.json` / `NUMERICAL_EXAMPLES.json`：运行证据、负面例的数值。
- `CACHE_AND_CAPTURE.md`：实际缓存核查、固定只读采集计划及不修改输出的验收要求。

没有新颖性主张。这里与旧 latent/KL 控制器的区别是先验证独立的 signed 观察与真实局部链；在验证完成前不分配 α。
