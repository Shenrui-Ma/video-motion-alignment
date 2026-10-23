# 参考自身时间指纹的 CPU 留出诊断

该包只研究参考自身的内容时间分布能否辨识参考时刻。它不估计生成视频动作偏移，也不输出动态 alpha。原配对读出和已完成视频结论保留。

## 冻结范围与数据隔离

`POLICY.json` 固定 short_0358、layer25、steps9/19、56heads、8probes、32物理bins中31完整有效bins，并锁定已通过身份及数值检查的两份 NPZ 字节SHA。输入只需两份 NPZ 与上游完成 STATUS，不加载带成片事件或收益的旧 summary。整个归档的SHA核对只检查字节身份。

解码白名单恰好为 `qrn_kn`、`qrw_kw`、`valid_bins`、`physical_frame_spans_inclusive`、`spatial_ids`。NPZ里即使存在无法解码的 generated 概率成员，入口也不访问它们；回归测试通过注入损坏的 `qn_kn.npy` 验证该边界。两reference分支各自分析，不根据其原方法效果进行选择。

程序不依赖 PyTorch、不加载模型、不调用GPU。生产CLI从当前目录 `READY.json` 核对所有固定资产，再读取固定POLICY。Python层 `execute(..., policy)` 保留合成fixture的显式policy参数；它不是新的CLI配置入口。

## 固定计算

每个step、reference分支、head分别计算两个fold：偶数probe训练/奇数测试，再交换。

- 模板为该时刻4个训练probe的概率均值，再逐元素开方。距离为 `||sqrt(p)-sqrt(q)||₂`，等于常规定义Hellinger距离的 `sqrt(2)` 倍。
- 主候选半径由训练组内部LOO得到：每个训练probe与另外3个probe均值的距离，取全部训练时刻/probe最大值 `ε_train`。正式留出距离使用4个训练probe均值。3与4的样本量不同；该经验半径没有跨fold或generated域覆盖保证。
- 对每个留出probe完整保留距离及 `{t:distance≤ε_train}` 候选集合，报告空集、单点、多点、时间直径、正确时刻是否在集合中。单点只描述参考指纹定位，不是语义或控制准入。
- 最近邻保留全部数值并列候选，分别保存最好/最坏时间误差；不通过argmin自动选最早时刻。并列和候选边界数值容差固定为float64的64eps。
- 每个实际正时间中心差 `Δ` 都保留 `d_min(Δ)` 以及 `d_min−2ε_train`。使用留出正确时刻最大残差的margin另外保存，仅为描述，不能替换训练半径制造覆盖。
- 线性辅助码使用中心化最小范数LS，不搜索ridge。`X=(C−C₀)−mean(C−C₀)`，`y=τ−mean(τ)`；截断阈值为 `eps·max(shape)·||C||₂`。保存全部奇异值、权重、不可恢复时间分量、逆增益以及每个留出probe误差。此数值秩约定针对浮点稳定性，不是收益选择阈值。

所有fold/heads先独立计算，之后才产生摘要。未实现跨native/weak字典迁移、连续时间插值或新的角色专用读出。role5周期仅作为必须保留歧义的合成反例。

## 输入与执行

输入JSON结构：

```json
{
  "schema": "h3-reference-only-diagnostic-input-v1",
  "upstream_status": "path/to/STATUS.json",
  "steps": {
    "9": "path/to/step009_all_probabilities.npz",
    "19": "path/to/step019_all_probabilities.npz"
  }
}
```

相对路径相对输入JSON。仅在独立审查及root放行后，远端CPU执行：

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python run.py --inputs inputs.json --output new_result_directory
```

两步所有输入先完成校验，之后才计算。缺失/未完成为pending；失败、错SHA、非法shape或padding为invalid。二者只有STATUS，不输出诊断数组或分数。已有输出目录拒绝覆盖；成功结果以临时目录整体原子发布。

## 输出与边界

4份NPZ（2step×2reference分支）保存全部head/fold的模板、距离、候选mask、半径、全分辨率曲线、谱和逐probe误差，并保留原validmask/spans/spatialids。主距离数组为 `[56,2,31,4,31]`；候选直径的NaN专门表示空集，JSON中空集统计使用null，不伪装为0帧误差。其余数值应有限。

`summary.json` 保存每head/fold小摘要、输入/数组SHA和CPU耗时。policy摘要哈希使用明确的sorted-key JSON表示，`READY.json`另外绑定原POLICY文件字节SHA。大数组留远端，只回summary/STATUS/receipt。

合成测试覆盖静态、role5周期、非对角但可辨识、近静态病态逆、LOO与测试隔离、概率列置换、空间fold交换、已知完整shape、损坏generated成员未被解码、padding与错误入口。外观伪装反例明确：即使reference自身空间留出全通过，零动作延迟的外观改变也可能产生另一个时刻的完全相同指纹。

本包尚未运行真实参考数据。参考诊断通过后仍需独立generated域辨识与控制方向导数研究；它不会自动放行GPU控制器。
