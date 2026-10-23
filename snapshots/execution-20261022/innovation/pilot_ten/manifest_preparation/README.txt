主十组新方法配对材料

catalog.json：10个任务的原prompt、seed、geometry、reference、native/global_weak原始graph映射、历史成片映射。
graphs/：20个graph原样副本，SHA256见catalog。勿直接向运行服务提交，里面保留原服务路径、缓存与历史审计节点。
*_CONDITION_CACHE.json：旧6组条件缓存的原清单副本，含远程张量路径与哈希。
missing_assets.json：本地参考视频/参考图和条件清单缺失0项；远程文件存在性尚未核对。
verification.json：10组种子、prompt、20步、alpha=.25、step[0,20)检查通过。

配对条件
- 普通编辑与新方法以该任务自己的原prompt/seed/参考/geometry保持一致。
- 共同对照：全程弱引导alpha=.25，20步Euler，所有50个block，radius=0,time_offset=0，物理时间范围0至valid_frames-1。
- 所有10组sigma序列和shift一致，参考弱引导alpha一致。跨任务geometry/帧数不同，seed仅机舱short0252为2026101703，其余2026101701。
- 旧6组prompt为历史结构化prompt；新增4组为冻结20261022简单prompt。旧6组不可改成官方短prompt后继续声称与历史成片同条件。
- 旧6组global_weak使用条件缓存和每步CPU x0 capture/audit；无每步VAE解码。这些记录影响时长，后续如关闭审计，应明确新采样耗时的范围。
- 蹲起为FlexiAct，官方目标caption内容与源动作冲突，因此采用已冻结的H3最简reference绑定句。主10组由9个IVEBench+1个FlexiAct组成。
- 未生成新graph、未改队列、未启动GPU、未做视觉检查。
