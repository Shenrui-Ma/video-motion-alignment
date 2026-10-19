R94 fitness/game_man_5：单条官方任务的同主机配对

旧R72 .41 P1审阅发现0.75–1.75秒上举进度偏慢，身份盔甲保留，目标图背景继承不完整。本包把它登记为已观察的development诊断素材，旧成片只作独立历史参考。

两条新结果均在.9按同一P1、source/portrait、seed2026101701、20Euler/CFG1/noLoRA、normal/reserve8生成。Native→固定alpha1 same-bin引导indices6..14/all50/0..146物理帧。后者只干预44个与有效区重叠的latent bins，最后bin覆盖145..148、其中147..148为padding；purepad149..157保持Native。

完整源49帧8fps，repeat3得到147有效24fps帧，补11帧至158。1152×768输出，按0,3,…144回到原49个采样时刻。角色原图1920×1080，经同原生match规则至1248×704，latent[1,24,1,44,78]，858patch。图像/视频reference角色绑定保持。

P1原文SHA483333ae6c3ac5d5afa7956579c241b524c3e8d12268f386f8262cffd927a150；R72实际success history中的graph、R84已准备forced graph原件与来源SHA在design/ancestry和audit/PARENT_BINDINGS.json。源视频、图、provenance原字节保持。当前pair使用新R94缓存；不导入R72旧噪声/conditions。

完成两条后精确释放服务与CUDA，再核本次actual history/workflow、8类条件blob、同实际AV初始噪声、20步轨迹完整及0..5 AVx0逐位相等；Native0/forced450路由。20次采样、全job、capture耗时分别保留。科学效果由root按全段动作、身份/场景完成与伪影审阅。

预定.9GPU3/8559，free40GiB、最大2张自用GPU。R85service16003/start2634847475的最后任务成功、原代次进程与CUDA释放及cleanup receipt是启动前置条件。外部任务继续运行；未登记的己方进程和不一致PID身份拒绝准入。HTTP只读UNKNOWN保留期限，提交不自动重试；任务或服务期限结束精确收尾。

本次仅CPU准备/被动部署；未启动GPU、服务或watcher。实际容量、输出、配对轨迹和效果待root运行。
