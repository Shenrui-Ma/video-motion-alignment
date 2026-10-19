R92：先检查普通编辑，再决定是否生成时序引导

研究素材、提示词与推理计算
本包继承未执行的R88五条源素材及原P1文本：long_0047、long_0123、long_0167、long_0173、long_0174。有效/总帧分别97/107、144/158、144/158、145/158、145/158，24fps。所有原视频、裁片映射、输入视频、设计和P1文字保持字节；六个数值文件保持R88原SHA。20Euler/CFG1/无Turbo/video12audio3，选择引导时仍为alpha1、index6..14、50层、全空间及有效时间相交bins。这里只改变任务执行顺序。

每例流程
1. 先生成Native。history成功、成片闭合后，以CPU验证20NFE、0路由、20个x0、实际noise/条件缓存、视频尺寸与时基，写NATIVE_RUNTIME_GATE.json。
2. root看普通编辑是否完成原任务、是否有可见时序错位，再写guide或skip及原因。决定绑定当前Native gate SHA、成片SHA、noise/条件/graph/history SHA、服务PID与身份，原子创建且不能覆盖。
3. guide沿原fixed图在同一服务继续，共用实际noise和clean条件；完成后pair gate要求两条条件/noise和前六次AV x0逐位相同。
4. skip保留Native-only记录。没有forced job/history、pair gate或虚构的引导成功数。五条固定分母、选择理由和全部结果均保留；选择后的修复比例须标明只针对被选中的普通编辑。
5. 首个实际guide的pair完成后，暂停等待root检查实际容量与画质，再进入后续素材。首例0047也可skip。五例全skip时guided容量和效果仍未验证。

执行与安全边界
每次review等待最多1800秒；达到边界时精确释放该服务，已完成文件和待审状态保留。watchdog空闲计时从其观察到空队列开始，可能比controller review计时略早，统一按同代服务的有界空闲退出记录处理。新的HTTP UNKNOWN只继续观察，不重发POST或重置任务/服务deadline。服务最多57600秒，每任务10800秒。资源准入、GPU UUID、preCUDA exactpeer、最多两张己方GPU、进程代次校验和CUDA退出确认沿原流程。

计划 .9 GPU0 UUID GPU-REDACTED / port8557，normal reserve8，启动空余>=40GiB。实际新输入容量与质量需要root运行确认。大PT保留远端。当前仅CPU准备与被动部署，未启动服务、GPU或watcher。

恢复边界
本包故意不自动恢复已存在的job/ledger。若审核超时导致服务释放，后续推进应先核现有成片与owner收据，再另建明确恢复attempt；不能把新代服务forced与旧Native自动混为同服务配对。必要恢复由root单独批准，保留本次全部失败和未执行项。

证据路径
configs/runtime_kernel_hashes.json：六数值文件继承。
audit/INHERITED_BYTE_BINDINGS.json：R88输入/设计/P1/原来源逐字绑定。
audit/CHANGE_MANIFEST.json：代码与行政配置变化。
audit/SCREEN_LEDGER.json：实际完成的paired或native_only，单独于controller.completed真实成功列表。
analysis/postrun/<source>/NATIVE_RUNTIME_GATE.json 与PAIR_RUNTIME_GATE.json：独立Native和真实pair证据。
重复核验仅顶层created_unix不同会保留旧gate字节；其他证据变动拒绝覆盖。
