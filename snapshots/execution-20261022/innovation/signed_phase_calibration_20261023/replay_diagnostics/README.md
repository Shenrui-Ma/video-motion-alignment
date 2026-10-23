# 被动 Q/K 的数值定义检查

该工具只读取远端 capture，验证保存的 raw Q/K、实际 RMS 权重与 eps、RoPE 表能否重现 actual Q/K。它不改变历史 AV 重放门槛，不判断动作相位是否可辨识。

最终结果按原地 q.copy_(q_out) 语义转换回原 Q/K dtype；因此 BF16 raw 搭配 FP32 norm weight 也正确覆盖。

主 oracle 通过 AST 直接执行已核 SHA 的原 eager `_rms_rope1` 和 `apply_rope_split_half1`，保留 RMSNorm 的输入 dtype 及中间 materialization、旋转表 dtype、split-half96和原32维未旋转尾部。显式 FP32 mean/rsqrt/weight 乘法后转换 BF16 的版本另外报告，避免把数学等式当作完全相同的计算顺序。

已读取真实 triton rms_rope.py：其 partial rot_dim96/head_dim128入口直接委托 eager，而非使用该文件的全维 fused kernel。此源码事实不是运行时 backend选择日志；若实际注册表选择其他实现，CPU oracle差异仍按预定门槛报告，不能自动归为舍入。CPU/GPU RMS reduction也可能不同，保留数值值而不宣称逐元素一致。

在实际 capture 结果出现前，POLICY.json冻结：仅BF16，每个branch(Q_C,Q_R,K_R)每个head分别要求NRMSE≤0.01、P99绝对误差/RMSactual≤0.03、最大绝对误差/RMSactual≤0.10；全部head通过。96维旋转前缀、32维尾部和完全相等比例独立报告，不用全head平均掩盖单head错误。其他dtype保留数值但标hold。逆旋转采用保存2×2矩阵的FP64逆，单独对比materialized preRoPE norm；它不能恢复BF16量化损失，未设exact要求。

9项CPU测试通过：原eager AST exact复算、BF16中间物化与尾部、非零逆旋转误差、错时间RoPE、错norm权重、非finite、dtypehold、生产geometry、奇异矩阵。测试使用小张量，实际捕获尚未评估。

调用（服务器CPU，无CUDA；qk不传本地）：

    CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python diagnose.py --capture /isolated/on/qk.pt --capture-sha256 <actual_sha> --output /isolated/QK_NUMERICAL_DIAGNOSTIC.json

输出文件必须不存在；源码不改capture、不改REPLAY_GATE、不启动模型。独立CPU目录 /tmp/h3_replay_diagnostics_20261023 暂留供复核。
