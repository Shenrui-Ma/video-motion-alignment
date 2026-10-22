from pathlib import Path
import html, json, re

ROOT = Path(__file__).resolve().parent

def figure(name, caption):
    svg = (ROOT/'figures'/name).read_text()
    for ident in re.findall(r'id="([^"]+)"', svg):
        namespaced = Path(name).stem + '_' + ident
        svg = svg.replace('id="'+ident+'"', 'id="'+namespaced+'"')
        svg = svg.replace('url(#'+ident+')', 'url(#'+namespaced+')')
    return '<figure><div class="diagram">'+svg+'</div><figcaption>'+caption+'</figcaption></figure>'

def cite(name, url):
    return f'<a href="{url}" target="_blank" rel="noreferrer">{name}</a>'

body = '''
<header><p class="eyebrow">研究方案 · 2026.10.20 · MiniMax H3</p>
<h1>动作时间对齐：下一步改进方案</h1>
<p class="lead">在已有效果的时序引导上，进一步改善动作对齐与编辑质量，并把引导选择变成轻量的模型内部计算。</p>
<p>本文件用于选择下一轮实验。下文四个候选尚未生成实验视频；本轮五组“时序引导＋相位对齐”结果单独展示。架构图中的矩阵与曲线均为机制示意。</p></header>
<nav><a href="#current">当前算子</a><a href="#feedback">参考特征保护</a><a href="#selection">选择修正位置</a><a href="#coverage">时间覆盖</a><a href="#rope">RoPE 频带</a><a href="#decision">建议顺序</a></nav>

<section id="current"><h2>1　当前方法与本轮验证</h2>
<p>H3 的主 DiT block 对文本、参考图、参考视频、输出音视频 token 做联合 Self-Attention。我们的修改位于 <code>optimized_attention</code> 返回的各 head 输出与 <code>out_proj</code> 之间，作用于<strong>输出视频 query 读取参考视频 keys/values</strong>这一部分。</p>
<div class="equation">A = softmax(QKᵀ / √d)<br>mᵢ = Σ<sub>j∈参考视频</sub> Aᵢⱼ<br>o′ᵢ = oᵢ + αmᵢ(μ<sub>same</sub> − μ<sub>ref</sub>)</div>
<p><var>mᵢ</var> 是当前 query/head 在原始 softmax 中分给参考视频全部 keys 的概率之和。<var>μ<sub>ref</sub></var> 是这些 keys 对应的归一化 Value 加权和；<var>μ<sub>same</sub></var> 只在对应物理时刻的参考视频 token 内重新计算 Attention。修改后经 <code>out_proj</code>、AdaLN 的 <code>gate_msa</code> 加入 residual stream，再执行后续 FFN 和 DiT 层。</p>
{{FIG1}}
<p>这轮新增版本在计算 <var>μ<sub>same</sub></var> 时，对输出 query 的副本补偿参考与输出的时间坐标原点差。设 Δ = 输出原点 − 参考原点：</p>
<div class="equation">q̃ = R<sub>time</sub>(−Δ)q<br>o′ᵢ = oᵢ + αmᵢ[Attn(q̃ᵢ, K<sub>ref,same</sub>, V<sub>ref,same</sub>) − μ<sub>ref</sub>]</div>
<p>原始联合 Attention 和用于求 <var>mᵢ</var>、<var>μ<sub>ref</sub></var> 的 Q/K 保留原相位。这一组合回答：在已有同时间引导上，参考分支的相位补偿是否带来额外收益。Δ 来自 token 坐标布局，动作延后帧数另由成片测量。</p>
<p>{{DIAL}} 的推理模块依据主体空间 Attention 图，在视频 query 到人物参考 keys 的 logits 上增加偏置，调节参考主体的影响。当前方法保持参考视频组的总概率，并把组内概率集中到同物理时刻；本轮相位实验进一步修改辅助 query 的时间旋转。</p>
<p>机舱、饮酒、书本和手帕使用各自历史配置的有效视频区间；Sam 真人书记舞保留历史第 50–65 帧窗口。五组均沿用第 7–15 次去噪前向及全部 50 个主 DiT block 的固定引导。每组保留原提示词、种子和实际缓存条件，四列为参考、普通编辑、时序引导、时序引导＋相位对齐。</p>
</section>

<section id="feedback"><h2>2　参考特征保护：组合两个方向的 Attention 修改</h2>
<p class="thesis">优先补一个成本较低、能直接解释副作用的实验：输出视频读取同一时刻的参考，同时限制参考视频在深层读回生成中的视频状态。</p>
<h3>机制</h3><p>联合 Attention 中，输出视频能读取参考视频，参考视频也能读取输出视频。虽然输入参考 latent 固定，参考 token 的 hidden states 会随着 DiT 深度变化。因此下一层使用的参考 K/V 已经包含上一层的交互结果。我们的假设是：错误的生成姿态可能经反向读取进入参考特征，削弱正向引导，或增加重影。</p>
<div class="equation">o′<sub>T</sub> = o<sub>T</sub> + m<sub>R</sub>(μ<sub>same</sub> − μ<sub>ref</sub>)<br>o′<sub>R</sub> = Attn(Q<sub>R</sub>, K<sub>除输出视频外</sub>, V<sub>除输出视频外</sub>)</div>
<p>第二式对剩余 keys 重新做 softmax。两个修改分别写入输出视频行和参考视频行；同一层的 Q/K/V 已经生成，所以参考行的修改从后续层开始影响输出。文本、人物参考图与音频仍按原定义参与。首轮沿用已有视频窗口和采样区间，以便直接比较。</p>
<p>也可复用原 Attention 的组分解来实现这一限制。对参考 query，令 <var>m<sub>T</sub></var> 为它分给输出视频 keys 的总概率，<var>μ<sub>T</sub></var> 为该组归一化 Value 均值，则：</p>
<div class="equation">o′<sub>R</sub> = (o<sub>R</sub> − m<sub>T</sub>μ<sub>T</sub>) / (1 − m<sub>T</sub>)</div>
<p>这与排除输出视频 keys 后重新归一化等价，可复用原联合 Attention 输出及一个参考到输出的子 Attention。若 <var>1−m<sub>T</sub></var> 很小，直接计算剩余 keys 的 Attention 更稳定。这里的分解是实现选择，组合实验检验的是两条方向修改后的成片效果。</p>
<h3>已有依据与最小实验</h3>
<p>此前 Sam 书记舞的同条件评审中，第 50–65 帧窗口的手臂方向匹配时差：普通编辑为 13 帧，正向同时间引导为 1 帧，单独限制反向读取为 8 帧。三条实际成片来自 R3 普通编辑、R3 正向引导与 R25 反向限制；种子、实际条件和噪声已核对。正向方法已接近对齐，组合实验主要看是否进一步减少重影、保持身份和背景。</p>
<p>四种设置为普通编辑、仅正向引导、仅反向限制、二者组合。对同一种误差量 <var>E</var> 可计算组合交互 <var>E<sub>组合</sub>−E<sub>正向</sub>−E<sub>反向</sub>+E<sub>普通</sub></var>；时间误差与画面质量分别报告。先用一个已有重影的有效样本和一个有效编辑样本，再复测另一种动作。</p>
<h3>与已有工作的关系</h3>
<p>{{ASYM}} 已采用非对称的参考交互；{{VIDU}} 已研究对应帧交互。这里借鉴它们的结构原则，研究冻结 H3 中两条边的组合效果。可形成的贡献在于：是否找到使动作时序恢复且减少编辑损伤的具体机制与适用条件。</p>
<p class="note">风险集中在参考适应性：阻断反向交互也可能让参考特征更难适配新的角色或场景。原 Attention 的额外计算量会增加，成片耗时与质量一起记录。</p>
{{FIG2}}
</section>

<section id="selection"><h2>3　按修正方向选择 Attention heads、层和强度</h2>
<p class="thesis">这是更适合继续发展为算法的方向：在本次前向内，估计“把这个 head 的时序修正加进去，会使局部运动差异变大还是变小”，再选择写入位置与强度。</p>
<h3>从 Attention 权重到实际特征改变量</h3>
<p>同样的 Attention 变化，经过不同 head 的 Value、输出投影和 AdaLN gate 后，对模型状态的作用不同。我们先计算少量 sampled queries 上的原时序修正，再把它投影到 residual stream：</p>
<div class="equation">δo<sub>ℓh</sub> = m<sub>ℓh</sub>(μ<sub>same</sub> − μ<sub>ref</sub>)<br>r<sub>ℓh</sub> = gate<sub>ℓ</sub> ⊙ W<sup>O</sup><sub>ℓh</sub> δo<sub>ℓh</sub></div>
<p><var>r<sub>ℓh</sub></var> 是固定当前 Q/K/V 时，该层该 head 的修正经过 <code>out_proj</code> 与 gate 后产生的局部增量。原 Attention 和 FFN 继续正常执行，选择开关只控制额外时序修正。</p>
<h3>固定测量位置与坐标</h3>
<p>令 <var>Y<sub>T</sub></var>、<var>Y<sub>R</sub></var> 为本层原 Attention 经输出投影与 gate 加入 residual stream 后、进入 FFN 前的输出视频和参考视频特征。<var>r<sub>ℓh</sub></var> 就在这个坐标空间内。每层使用当前状态分别判断，同层选中的 heads 合并写入。</p>
<h3>先验证一个轻量的局部误差</h3>
<p>用固定的共享线性投影 <var>P</var> 测量两侧特征。<var>W</var> 是整个局部时间窗口内固定的空间对应；参考特征先按物理时间重采样到输出时间轴。<var>D</var> 在固定空间网格计算相邻时刻的特征差，除以实际时间间隔：</p>
<div class="equation">H<sub>T</sub> = P(Y<sub>T</sub>),　H<sub>R</sub> = W P(Y<sub>R</sub>)<br>e = [ √λ₀(H<sub>T</sub>−H<sub>R</sub>) ; √λ₁D(H<sub>T</sub>−H<sub>R</sub>) ]</div>
<p>第一项比较同一物理时刻的状态，第二项比较局部时间变化。状态项提供时间相位锚点：仅比较速度时，恒速段的固定延后可能被漏掉。采用固定网格差分，是因为稳定纹理沿自身运动轨迹的特征可以始终不变，沿轨迹求导会把运动消去。</p>
<p>跨角色替换时，身份、比例、纹理也会进入这个误差；参考与输出 token 的噪声水平和条件 timestep 也不同。首先用保存的中间特征、已知时间偏移和已对齐样本，分别检查各去噪阶段的响应。共享投影、空间匹配、两项尺度与可信范围依据这一步确定，使自动判断主要响应动作偏离。</p>
<h3>选择 head，并计算引导强度</h3>
<p>在本次计算中固定参考状态，对每个 head 的修正使用同一个投影和误差定义：</p>
<div class="equation">g<sub>ℓh</sub> = [ √λ₀P(r<sub>ℓh</sub>) ; √λ₁D P(r<sub>ℓh</sub>) ]<br>s<sub>ℓh</sub> = −⟨e, g<sub>ℓh</sub>⟩</div>
<p>选择空间匹配可靠、且 <var>s&gt;0</var> 的 heads。将同层的修正合并为 <var>r=Σr<sub>ℓh</sub></var>、<var>g=Σg<sub>ℓh</sub></var>，计算：</p>
<div class="equation">E<sub>local</sub>(α) = ½ ‖e + αg‖²<br>α* = clip( −⟨e, g⟩ / ‖g‖², 0, 1 )</div>
<p>当 <var>P、W、D</var>、可信区域和误差权重在当前计算中固定时，上式精确最小化这一局部二次目标。分母为零则 α=0。每层、每次前向重新判断施加或跳过修正。首轮将 α 限制在 0–1，使操作保持为参考组内部概率重分配。</p>
<p>若与参考反向限制组合，先将已经确定的反向限制计入参考状态，再固定它选择正向修正；若两侧一起优化，误差增量应使用 <var>δH=P(r<sub>T</sub>)−WP(r<sub>R</sub>)</var>。当前层的 Q/K/V 在写入修正之前已经生成，参考状态的变化经后续层传播。</p>
<h3>进一步直接测量局部位移</h3>
<p>更直接的一版，可以从同一 residual 测量点构造局部 Q/K 匹配，得到相邻帧的 soft matching 位移。设候选位移为 <var>dⱼ</var>，匹配 logits 为 <var>aⱼ</var>：</p>
<div class="equation">p = softmax(a),　u = Σⱼpⱼdⱼ<br>δu = Σⱼpⱼ(dⱼ−u) δaⱼ</div>
<p>用位移差和同时间状态锚点定义误差，再用 Jacobian 计算修正方向。此时 α* 最小化线性化二次模型；可在少量 sampled queries 上重算局部误差，最多回退两次强度。局部匹配读出从修正所在的 <var>Y</var> 构造，原层已有 Q/K 只提供候选与置信度。</p>
<p>两版都将计算放在模型内部特征上，使用局部投影、匹配和小向量运算。核心验证是这个观测量能否预测最终动作时差，以及额外计算是否足够小。</p>
<h3>与已有工作的关系</h3>
<p>{{HEADS}} 已研究运动/结构 heads、按 Attention 熵选择 heads 和因果消融；{{REFGAP}} 根据参考组概率在线调整权重，作用层由预先分析选定；{{SPARSE}} 已动态分配跨 head 稀疏预算。我们的具体候选是用<strong>当前时序修正经过投影与 gate 后的增量，以及它相对于局部运动残差的方向</strong>来选择干预。闭式最小二乘属于已有数学工具，贡献需要来自这一观测与执行机制的实际效果。</p>
<h3>最小实验</h3>
<p>比较全 head 引导、同数量随机 heads、熵/运动可靠性选择、上述方向选择。保持候选层、采样区间一致，另做修正范数匹配，区分位置选择与单纯减弱引导。优先复测一条“时序改善但有重影”的样本和一条“身份受到干预影响”的样本。随后检查正常样本能否保持低干预。</p>
<p class="note">额外计算发生在少量 Q/K 对应、sampled queries 的投影和小向量运算中。单次局部误差下降的推导依赖冻结对应，最终视觉效果由成片检验。该候选训练成本为零；实际运行开销需在同一条推理中计时。</p>
{{FIG3}}
</section>

<section id="coverage"><h2>4　跨输出时刻分配参考视频的时间覆盖</h2>
<p class="thesis">把各个 query 独立挑选参考时刻，改成多个输出时刻共同分配参考时间的使用量，研究短事件受到长时间相似姿态竞争的情况。</p>
<p>设 <var>Aᵢⱼ</var> 是输出 query 对参考时间 bin 的归一化概率，<var>ρᵢ</var> 是参与 query 的权重，<var>bⱼ</var> 是由有效时长、局部可见运动和时间邻域确定的目标覆盖。采用软列约束：</p>
<div class="equation">min<sub>X≥0, X1=ρ</sub> KL(X ‖ diag(ρ)A)<br>　+ λ<sub>t</sub> Σ<sub>ij</sub>Xᵢⱼ(τᵢ−τⱼ)²<br>　+ λ<sub>c</sub> KL(Xᵀ1 ‖ b)</div>
<p>每行恢复到原 query 的参考总概率 <var>mᵢ</var>；参考帧内部的空间匹配保留。共享的列势使某一时刻的分配受其他 query 影响。时间成本抑制顺序置换，软覆盖避免强行要求每个参考帧使用同样多的概率。</p>
<p>当前硬同时间引导在实际施加引导的 token 范围内已经覆盖对应时刻。因此这个候选的合理用途是<strong>放开一点相邻帧上下文以减轻生硬修正，再用跨 query 约束控制新的时间漂移</strong>。先比较硬同时间、独立软时间带、软时间带＋覆盖约束。已有粗粒度记录未显示容量上界被触发，首个检查应使用实际、未平均的局部 query 分布，确认约束是否有必要。</p>
<p>{{OT}} 已给出双边归一化与软边缘的数学框架；{{FREEMIX}} 在视频编辑中用 OT 建立空间对应。此处研究的是生成 query 对参考时间的共同使用方式。聚合成小矩阵再广播到原 token 会引入近似，需要检查实际细粒度边缘误差。</p>
<p class="note">风险是覆盖均匀却动作仍错位，或背景消耗了大部分覆盖预算。只有原分布确实存在局部事件欠覆盖，且软时间带单独留下时序问题时，才值得进入这项成片实验。</p>
</section>

<section id="rope"><h2>5　只补偿部分时间 RoPE 频带</h2>
<p>本轮全频补偿对 16 个时间通道对都旋转 <var>−ω<sub>b</sub>Δ</var>。下一项坐标消融可以给每个频带一个系数：</p>
<div class="equation">q̃<sub>b</sub> = R(−g<sub>b</sub>ω<sub>b</sub>Δ)q<sub>b</sub>,　0 ≤ g<sub>b</sub> ≤ 1</div>
<p>先比较全频、低频、高频和无补偿；仅改变辅助参考分支的 query 副本。后续可根据本次 Q/K 对各频带的相位敏感度选择 <var>g<sub>b</sub></var>，检查某些频带是否主要影响跨参考的区分、另一些更影响时间对应。这种功能划分需要实际测量。</p>
<p>{{ROPE}} 已分别研究频带感知的时间重定时、共享参考 Attention 的频率调制和视频长度外推。这一候选首先承担解释本轮相位结果的作用。它的实现增量很小，适合在全频版本出现混合收益时追加两条受控消融。</p>
</section>

<section><h2>6　去噪策略与参考噪声的进一步假设</h2>
<p>Flow matching 的速度 <var>v=dx/dσ</var> 描述沿去噪时间的变化；人物运动由沿视频物理时间 <var>τ</var> 的变化描述。把 <var>v</var> 的大幅变化直接当作快速动作，容易混入纹理、颜色和身份编辑。{{FLOW}} 已用 latent 差分、速度分解或显著性控制编辑。</p>
<p>更底层的一项高风险假设，是参考条件的噪声水平与对应 token timestep 是否影响运动读取：让参考条件的噪声及其 AdaLN 时间标签成对变化，观察中间层运动匹配是否更稳定。H3 当前参考条件接近干净，强噪声会改变模型熟悉的条件分布。可先做一个固定状态的 Attention 响应检查，再决定是否值得成片；当前优先级低于前述方案。</p>
</section>

<section id="decision"><h2>7　建议的下一轮顺序</h2>
<p>本轮五组四列对照已完成。四条 IVEBench 样例加相位后的关键动作区间与原时序引导接近；Sam 书记舞的主窗手臂方向匹配时差由普通编辑的 13 帧，经原引导降到 1 帧，叠加相位后回到 12 帧。该窗口使用原有 0.3 关键点置信度阈值；连续帧中也能看到相应动作阶段延后。</p>
<p>Sam 三版 Motion Fidelity 分别为 0.85237、0.85227、0.85155，整体分数接近，局部动作时间差异明显。本轮以同帧视频与动作时间作为主要证据，MF 同时保留在结果页。</p>
<table><thead><tr><th>优先项</th><th>要解决的具体问题</th><th>最先需要的证据</th></tr></thead><tbody>
<tr><td>正向＋反向限制</td><td>时序已改善，重影或编辑副作用仍明显</td><td>组合相对已有正向引导改善质量，动作对齐保留</td></tr>
<tr><td>按修正方向选 head/层</td><td>全层修正过宽，自动起停成本高</td><td>内部代理能区分有效与有害修正，并在同预算成片中受益</td></tr>
<tr><td>部分 RoPE 频带</td><td>全频相位补偿的收益随样例变化</td><td>固定频带消融出现可重复差异</td></tr>
<tr><td>跨 query 时间覆盖</td><td>软化同时间限制后仍有事件时间竞争</td><td>实际局部分布有欠覆盖/过占，列约束有独立作用</td></tr>
</tbody></table>
<p><strong>我的建议：</strong>继续以已有有效的时序引导作为比较基础，先补正向＋反向限制的组合实验，检查对齐、重影与编辑完成度；算法方向优先推进按修正方向选择 heads、层与强度。全频相位补偿本轮暂停纳入正式方法，频带消融留作解释 Sam 退化的候选。上述下一轮方案由你选择后实施。</p>
<p>评估先检查编辑任务完成，再看同一时间轴上的动作事件误差、局部动作形状、身份与背景、重影和耗时。Motion Fidelity 作为运动相似度的补充。对失败样本的修复能力与正常样本的保持能力分开统计，完整保留本轮五组结果。</p>
<p class="foot">来源来自本文链接的原论文、作者公开代码与本项目历史运行记录。新近论文已核到方法描述，代码可用性在调研记录中单列。候选由你选择后再进入下一轮推理。</p>
</section>
'''

links = {
 'DIAL':cite('DIAL','https://arxiv.org/html/2609.11507v1'),
 'ASYM': ', '.join([cite('OmniTransfer','https://arxiv.org/html/2601.14250v1'),cite('Identity as Presence','https://arxiv.org/html/2603.17889v1'),cite('FullDiT2','https://arxiv.org/html/2506.04213v1')]),
 'VIDU':cite('Vidu S2','https://arxiv.org/html/2609.11638v1'),
 'HEADS':cite('HALO','https://arxiv.org/html/2607.11081v1')+'、'+cite('Why Do Video Diffusion Models Violate Physics?','https://arxiv.org/html/2609.23658v1'),
 'REFGAP':cite('RefGAP','https://arxiv.org/html/2609.35708v1'),
 'SPARSE':cite('EG-Sparse','https://arxiv.org/html/2610.14672v1'),
 'OT':cite('Sinkformers','https://proceedings.mlr.press/v151/sander22a.html')+' 与 '+cite('Unbalanced OT Attention','https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ipr2.12403'),
 'FREEMIX':cite('FreeMix','https://openaccess.thecvf.com/content/ICCV2025W/Findings/html/Chen_Zero-shot_Customized_Video_Editing_with_Diffusion_Feature_Transfer_ICCVW_2025_paper.html'),
 'ROPE':cite('ReTime','https://arxiv.org/html/2604.22554v1')+'、'+cite('Untwisting RoPE','https://arxiv.org/html/2602.05013v1')+'、'+cite('RIFLEx','https://arxiv.org/html/2502.15894v1'),
 'FLOW':cite('FlowMotion','https://arxiv.org/html/2603.06289v2')+'、'+cite('AV-FlowEdit','https://arxiv.org/html/2610.13072v1'),
 'FIG1':figure('01_current_attention.svg','图 1｜当前算子：保持参考视频组的总概率，重新分配组内时间 Attention。'),
 'FIG2':figure('02_direction_and_coverage.svg','图 2｜候选结构：正反向读取的四种设置，以及不同输出 query 之间的参考时间分配。'),
 'FIG3':figure('03_rope_and_head_selection.svg','图 3｜时间 RoPE 通道对；在 Attention residual 后测量修正，逐层选择 heads，并对冻结的局部误差做闭式强度选择。')
}
for k,v in links.items(): body=body.replace('{{'+k+'}}',v)
assert '{{' not in body
style='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:#152235;background:#eef1f6;font:17px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}main{max-width:1160px;margin:32px auto;background:white;padding:44px 56px;box-shadow:0 8px 42px #26354c0c;border-radius:6px}h1{font-size:36px;line-height:1.3;letter-spacing:-.5px;margin:.3em 0}h2{font-size:26px;line-height:1.5;margin:0 0 16px;padding-top:24px;border-top:2px solid #e0e6ef}h3{font-size:19px;margin:24px 0 8px}p{margin:12px 0}section{margin-top:44px;scroll-margin-top:20px}a{color:#155fbd;text-decoration:none}a:hover{text-decoration:underline}nav{display:flex;flex-wrap:wrap;gap:10px 22px;border-top:1px solid #dce3ee;border-bottom:1px solid #dce3ee;padding:15px 0;margin-top:28px;font-size:15px}.eyebrow{font-size:14px;color:#52677f;letter-spacing:1px}.lead{font-size:21px;color:#37516e;max-width:900px}.thesis{border-left:4px solid #2a78c9;padding:10px 16px;background:#f3f8ff;font-size:19px}.equation{padding:20px 24px;margin:20px 0;background:#f5f7fb;border:1px solid #dfe6f0;border-radius:7px;font:21px/1.9 Georgia,"Times New Roman","Songti SC",serif;overflow:auto;white-space:nowrap}var{font-family:Georgia,"Times New Roman",serif}code{font:15px/1.6 ui-monospace,monospace;background:#edf2f8;padding:2px 4px;border-radius:3px}.note{font-size:15px;color:#53647a;border-left:2px solid #c4d1df;padding-left:14px}.diagram{overflow-x:auto}.diagram svg{display:block;width:100%;height:auto;min-width:650px}figure{margin:26px -30px}figcaption{font-size:14px;color:#66758a;padding:10px 26px;line-height:1.6}table{border-collapse:collapse;width:100%;font-size:15px;line-height:1.65;margin:24px 0}th,td{text-align:left;padding:12px;border-bottom:1px solid #dde5ef;vertical-align:top}th{background:#edf3f9}td:first-child{font-weight:600;width:24%}.foot{font-size:14px;color:#718096;margin-top:32px}@media(max-width:750px){main{margin:0;padding:26px 20px}h1{font-size:29px}h2{font-size:23px}body{font-size:16px}figure{margin:20px -10px}.equation{font-size:18px;padding:16px}table{font-size:14px}th,td{padding:8px}}@media print{body{background:white}main{margin:0;box-shadow:none;padding:12px}nav{display:none}.diagram svg{min-width:0}h2{break-after:avoid}figure{break-inside:avoid}.equation{white-space:normal}}'''
out='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 动作时间对齐：下一步改进方案</title><style>'+style+'</style><main>'+body+'</main></html>'
(ROOT/'index.html').write_text(out)
target=Path('/Users/researcher/Downloads/H3_后续改进方案_机制与最小实验_20261020.html')
target.write_text(out)
(ROOT/'BUILD.json').write_text(json.dumps({'file':str(target),'bytes':len(out.encode()),'svg_embedded':3,'external_runtime_assets':0,'status':'method proposals, no GPU experiment claims'},ensure_ascii=False,indent=2))
print(str(target),len(out.encode()))
