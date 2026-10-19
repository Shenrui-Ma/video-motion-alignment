# R14 被动原生筛查验收计划

仅准备，尚未启动消费者、轮询或GPU。等主控确认真实启动后复用共享CPU锁串行验收，R12优先。

正式ID：`r14_s05_seed1313_native`。实际配置seed是 **2026101313**；不是字面1313。固定source05/Sam，1312×736、141帧、24fps，20步Euler。

1. 核实际success history/config一致、精确输出文件名、前后与本地SHA、完整几何和时基。
2. 核新seed和实际noise绑定；与.41 R11逐项比较输入RGB/VAE、Qwen语义输入/embedding/tags/layout、采样/backend。记录每项差异，仅允许已登记seed及其原生reference augmentation变化。不得要求新seed的张量或RGB等seed1；不得把此实验称作仅改变初始噪声。
3. 核实际policy=off、空fixed mask、20NFE/20更新/20callback、每次50block、总1000block、0路由。被动observer可以建议ON，实际执行必须始终OFF。
4. 实际captures必须恰为5/6/7/8/9/10/15/19八项且唯一，连同final核9文件真实SHA、有限性、shape、dtype及metadata绑定。
5. 沿用冻结原四窗50–65/69–81/80–92/99–111和0.3/0.5置信阈值，不重选。主窗只有direction与wrist在两阈值均可靠且lag在±2内才能记normal；unknown不能记normal。固定55/86/105只检查明显背景/编辑/形体问题。
6. 保留所有失败、unknown、背景或形体损伤。只记录NFE/时间/observer开销。不会自动换seed1314，也不新增速度诊断。

这是已知素材上的预选未测seed，不是盲测或自然失败率估计。最终正常也不能代替早期x0正常的独立证据。更细执行门和冻结文件SHA见ACCEPTANCE_PLAN.json。
