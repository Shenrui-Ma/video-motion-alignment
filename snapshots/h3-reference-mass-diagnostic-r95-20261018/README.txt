R95：参考视频组增权的 CPU 诊断内核

范围
本包提供两种已知机制控制，检验参考组总注意力占比与组内同时间读取的不同作用。
它尚未接入 Comfy 节点或运行队列，尚无真实 CUDA / H3 成片结果。
原 R85 core.py、layout.py 按字节保存在 r95_kernel/snapshot，原目录未修改。

定义和两种模式
对一个被选中的输出视频 query，令 R 为参考视频的完整 key 区间；图像、文本、音频
以及输出视频自身的 key 均属于其余集合。O 是原完整 attention 输出，m=Z_R/Z_all，
O_ref 是仅在 R 内归一化的 attention 输出。O_same 是仅在该 query 对应时间 bin 的
参考 keys 内归一化的输出。空间 token 仍全部保留，时间分组沿原 R85 layout。

reference_group_gain：B = [O + (r−1)m O_ref] / D
samebin_group_gain：  C = B + m_r (O_same − O_ref)
D = 1 + (r−1)m；m_r = r m / D。
第二式等价于 C = [O − m O_ref + r m O_same] / D。
最终写入 O + alpha(T−O)，T 取 B 或 C；alpha∈[0,1]，r 为有限正数，默认 1。
因此 alpha 是输出混合系数，r 控制参考视频组 gain，两者独立。

logits 的对应关系
B 等价于给选中 query 到 R 的 logits 统一加 log(r)。
C 对同时间集合 S 保留 logits，并加 log(r)+log(Z_R)−log(Z_S)，其余 R keys 屏蔽。
这样组内重新归一化先保留原参考组 partition，再改变该组总质量。
直接屏蔽其他 R keys 后只加 log(r)，会改变不同的组总质量；测试保留了这一反例。
alpha<1 表示两个 attention 分布的输出混合，不等价于单次 log(r) 偏置。

精确继承
r=1，reference_group_gain 直接调用原 Native；samebin_group_gain 直接调用原
mass_preserve。alpha=0 直接调用原 Native。测试在 FP64/FP32/FP16/BF16 上逐位比较。
非法 r 即使在 alpha=0 时也拒绝。只改指定 query 区间，其他模态及未选视频 query
输出逐位保持；输入 Q/K/V 和 plan 不修改。
写回沿 R85 的 full[:, :, qa:qb].copy_(changed)，先计算旧输出的审计统计，再原位
替换选定区间，避免复制整个 packed attention 输出。实际峰值显存仍需 GPU 测量。

稳定实现和代价
r>1 用 logaddexp 计算归一化系数，不直接构造可能溢出的 r 张量。
B 写成 O 与 O_ref 的凸组合；C 再加入 m_r(O_same−O_ref)。这里不存在除以 (1−m)。
0<r<1 时，m 接近 1 会使已分别舍入的 O 和 m O_ref 相消。实现直接计算其余 key
集合的 attention，再与参考组混合；该分支多一次 attention 调用和相应 K/V 拼接。
这是预先登记的数值策略，r=3 不进入此分支。
默认 radius=0/time_offset=0；邻近窗口操作原样复用 R85，只为接口兼容。

调用量：reference_group_gain 在 full attention 外计算一次参考组 attention；
samebin_group_gain 再计算原有分组同时间 attention。audit.additional_attention_calls
专指 r<1 的额外 complement 调用，不表示相比 Native 的总额外调用量。

半精度边界
组合公式使用 FP32（FP64 输入用 FP64），最后写回原 dtype。attention 后端输出自身
仍已舍入，LSE 沿原 Flash 接口为 FP32。r>=1 时展开 C 的 O、O_ref、O_same 系数
绝对值均≤1，避免由 1/(1−m) 放大的误差；输出接近零时相对误差仍可能较大。
实际 CUDA Flash 与这里 dense CPU 后端的误差和内存尚待目标机器验证。

48 个固定 CPU 数值场景的最大绝对误差：FP64 输入 1.2141e−7；FP32 1.7881e−7；
FP16 0.00048828125；BF16 0.00390625。这里比较同一 dtype 输入下的独立 dense logits
结果，原 Flash 接口 LSE32 精度也适用于 FP64 测试，所以不声称 FP64 精确运算。
全部结果有限，包含 m≈0/1 和有限极端 r=1e−300/1e300。
BF16 相消见证：m≈0.9997969、r=0.0001 时，直接旧公式误差 0.6157227，显式其余组
重算误差 0.0009766。该见证是可控张量实验，没有模型轨迹含义。
另一见证中 m 增大而最终 BF16 写回全为零改变量，说明 m_r 增大不能单独证明有效
改变了 attention 输出。原始数值见 audit/NUMERICAL_AUDIT.json。

接口
from r95_kernel import route_attention
logs = []
output = route_attention(q, k, v, heads, plan,
    mode='samebin_group_gain', reference_gain=3.0, alpha=1.0,
    radius=0, time_offset=0, attention=verified_attention_callback, audit=logs)

Q/K/V 是相同 shape 的 [1,H,N,D] packed self-attention 张量；输出为 [1,N,H*D]。
plan 沿原已核 layout，包含 query_interval_half_open、reference_video_segment、
latent_interval_half_open 和 frame_rows。后端返回 [B,H,Q,D] 输出与 FP32 [B,H,Q] LSE；
分组调用可令 B>1，后端须支持。默认后端仍为原 CUDA Flash，CPU 测试显式提供 dense。

audit 中 stats 是 detached tensor，保持设备位置，由调用方统一 flush/转 JSON；
内核不逐 block 执行 CPU 同步。采样上限 8 heads ×128 queries ×16 channels。
ref_mass_mean/max 是原 m；boosted_ref_mass_mean/max 是目标 m_r；effective_ref_mass_mean
是 alpha 混合后的 (1−alpha)m+alpha m_r。written_delta_rms/ratio 与零改变量比例测量
最终 dtype 写回的 attention 变化，位置在 out_proj/AdaLN gate 之前。
这些是特征幅度统计，不能充当动作误差或因果证据。精确 Native 回退路径不额外计算
参考组统计；其 stats=null。精确 mass_preserve 回退返回原核已有的有限统计。

采样时间的解释
实际 R85 图使用非均匀 Euler sigma。预测 indices 6…14 对应 .965517→.8，
sum|Δsigma|=.165517；最后 5 次 Euler 更新总 |Δsigma|=.8。
原证据按字节保存在 audit/R85_SIGMA_WINDOW_EVIDENCE.json，来源与 SHA 见 PROVENANCE。
把 6…14 延长到 6…19 同时改变持续时间与积分权重暴露；模型响应、后续传播和
attention 修正均非线性，Δsigma 之和不能直接当作成片修复强度。
比较 B/C 时应固定 schedule、alpha、层和输入；schedule 控制另作单因素记录。

科学边界
统一 log(r) 组偏置和同组重新归一化属于现有 attention 操作。该包用于拆分机制，
不声称新公式，也未复现完整 DIAL 的空间区域选择及论文全部设置。
继承的一手分析：R85 consumer audit/samebin_groupboost_review/REPORT.txt，以及
early_schedule_history_review/REPORT.txt。后续 H3 推理需要独立集成/容量检查，并由
root 在 R90/R94 的实际任务与时序结果明确后决定；本包没有改变任何运行中的实验。

复现 CPU 验证
CUDA_VISIBLE_DEVICES='' /Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python -m unittest discover -s tests -v
CUDA_VISIBLE_DEVICES='' /Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python tests/numerical_audit.py
工作目录为本包根目录。22 个测试全部通过；初轮测试后端的 LSE dtype 不符失败记录保留。
依赖沿用现有 Torch 2.14.0，无新增依赖、远程部署或 GPU 初始化。
