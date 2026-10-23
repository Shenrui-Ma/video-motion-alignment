# H3 局部链源码映射与最小被动采集计划

这是对项目已经保存的 H3 实际实现的只读映射，不是通用Transformer示意。源文件：`innovation/partial_rope/sources/host41_model.py`，SHA256 `0d5edcf32b4b98d704eaa51de60ed71f507d0c7d9845947f566647dc76fb8dfe`。未来若在别的runtime执行，先比对该实际model文件SHA和有效wrapper；本文件不声称已做新的远端采集。

## 已核实的逐token边界

| 代码位置 | 实际操作 | 局部复算要求 |
|---|---|---|
| Attention.forward 173–201 | qkv_proj→reshape→每head Q/K RMSNorm→96/128维split-half RoPE→联合attention→out_proj | 联合attention是跨token操作；本方案从其已经算好的O、D开始。out_proj就是W_o，需保留真实量化实现。 |
| `_mod_row/_mod_scale_shift/_mod_gate` 229–247 | 按segment或逐tokenmod_row读取shift/scale/gate，原地施加AdaLN和residual | 不可令全部probe共用一个gate；保存每个被选token的实际mod_row。 |
| DiTBlock.forward 291–298 | norm1+AdaLN→attention gate残差→norm2+AdaLN→SwiGLU MLP→MLP gate残差 | 从attention输出以后到本block结束均为tokenwise；RMSNorm归约最后hidden维，不跨时间/空间。 |
| MLP.forward 209–210 | fc1后SwiGLU，再fc2 | 此处没有temporal convolution、token pooling或第二次attention。 |
| `_forward` 625–694 | target video时刻t_v，reference视觉时刻max(t_v,.999)，audio时刻t_a；mod_index=t_row*3+tag，video=0/text=1/audio=2 | reference和canvas虽然都是视频tag0，时刻及gate仍可不同；masked输入还可能每token不同。不得用canvas的gate重放reference。 |
| `_forward` 745–764 | 生成共享RoPE表，顺序执行50个blocks；patches_replace可包装block | 相邻block之间没有额外跨token算子；必须同时核验活跃blockwrapper没有加入其他操作。prefetch仅搬运模型。 |
| Attention.forward（下一block）173–195 | next norm1/AdaLN之后，qkv linear与Q/K norm、RoPE | 要读下一层preRoPE Q/K；不要以当前层K替代下一层K。 |

TokenRefiner发生在主blocks之前，final_layer与audio sigma换算在blocks之后；两者不在当前attention输出到nextQ的局部链。当前O已经融合文本、音频和参考，因此该局部链保持这些输入贡献，不代表忽略音频条件。canvas修改只限视频segment，音频/参考token在当前block的attention输出保持同一次原值。

## 数值oracle应逐项覆盖

用有差别的reference/canvas mod_row、非零shift/scale、两道非零gate、最后维RMSNorm、SwiGLU和W_o/W_Q，核验以下两条等价：

- dense全部token的当前block后半段→nextQ，与只取同一probe token的局部计算一致；不含额外attention。
- 有限差分的query变化与链式导数一致；gate=0时相应路径导数为0；W_o方向翻转能翻转相位收益；reference gate不小心共用canvas gate的负例必须失败。

FP64 toy oracle用于数学和索引；不能把它写成真实INT8 kernel验证。活模型上稀疏batch的量化scale和舍入可能不同，需要实际kernel的dense-vs-sparse数值核对。

## next参考K何时可用

被动诊断可在原轨迹自然走到next层时读取其真实K。若未来想在当前层提交alpha前用nextK控制，下一层K尚未正常产生。可以把**固定参考probe**的当前O也走本层后半段和next K投影，得到稀疏reference bank；其参考gate与目标gate分别读取。空间bank始终是每bin固定8个probe，读出明确称稀疏内容观测，不称原完整Attention的精确概率。

若想对全参考空间位置做精确LSE，就要提前重算整参考段的FFN与next K，不再是少量probe代价。不得偷偷拿当前层K配nextQ，或缓存上一采样步K后声称同前向。该边界已与数学代理对齐。

## 仅用于下一阶段申请的最小被动采集

当前不执行。先等CPU可辨识性/反例通过，再由主线程决定是否进行。

固定case为旧0358/0059，各native/weak；零基steps9/19、layer25；保持原prompt/seed/cache/geometry，8个空间probe、56heads、全部完整有效时间bins。记录实际bin/frame_spans/packed indices、mod_row、sampler sigma、checkpoint/model源码/hash、当前x_n与对应已保存预测x0的身份。没有提前结束20步的生产任务，不另排成片。

相位读出阶段只需：目标Q、参考Q、参考K（各同一层和step）；不需要V。fused RMS+RoPE实际在qkv buffer上原地执行，因此最保守的采集点是**在融合kernel之前把被选Q/K投影行独立clone**，连同Q/K norm的128维权重与eps离线归一化，避免保留随后会被原地修改的view。也可以只读postRoPE副本做逆旋转，但需另报BF16旋转/舍入误差；不能假装当前实现已经存在无误差的preRoPE tensor。

最大T=47、P=8、H=56、D=128时，每种特征native BF16约5.14MiB，三种约15.42MiB/捕获；T=32时约10.50MiB/捕获。四个case×method组合、每组两步的8份捕获，三种特征总上界约103.69MiB（FP32保存约207.38MiB），小元数据另计。使用完整latent_t只是容量上界，分析仍按真实有效bin遮罩。单head分块计算时间/空间相似度，回传时间分布与小JSON，不下载特征至本机。这个阶段不保存full QKV、不增加VAE或DiT调用。

上述容量不含局部方向复算需要的O/D/hidden/gates；那些只在相位观测先通过后另订小采样计划。不要一开始把所有状态和巨型矩阵都存下来。

采集必须通过被动性核对：不修改QKV、hidden、RNG、dtype/device和wrapper返回值；副本与独立索引、捕获前后张量签名及正常输出一致性留证。插入clone会改变运行时间和内存，计入开销，不能把“数值不改”写成“没有成本”。若重放旧状态，先核对同一步预测x0；只对比最终latent不足以验证中间状态。现有缓存仅x0而非x_n，所以在重放一致性通过前，不称它是原轨迹Attention。
