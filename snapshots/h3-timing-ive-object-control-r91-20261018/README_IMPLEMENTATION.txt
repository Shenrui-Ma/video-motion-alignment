R91：IVEBench 两条运动物体编辑的同主机对照

short_0114 官方任务：Replace the basketball with a neon-lit ball。
使用完整 109 帧、25fps 原视频，按实际有理 PTS 最近帧映射到 24fps，共 105 有效帧，末帧补齐至 H3 的 107 帧。
long_0039 官方任务：Adjust the color of book to blue。
使用原视频 [0,150) 帧，对应 [0,6) 秒，共 144 有效帧，末帧补齐至 158 帧。该条属于 IVEBench 素材片段探索，评测范围限于片段。
原始完整视频、官方 LFS oid、下载收据、原始 rational PTS、每一输出帧到原视频的映射、lossless 回读 MD5 均保留。原片变换为 1280×720，再以左右16、上下8像素黑色边补齐至1312×736；评估裁掉黑边并仅用有效时间。

原始 root 设计与两个 P1 文本保持字节不变。P1 只描述原片动作与被要求的物体外观编辑。Native 与 fixed 使用完全相同的提示词、输入、实际缓存噪声和条件；前六次 AV x0 必须逐位一致。两组都在当前 .9 runtime 重新生成，不使用 R64 旧 P0 成片作为配对输入。

数值代码沿 R88 原六文件逐字继承。20 Euler / 20 NFE，CFG1，无 Turbo LoRA，video/audio shift12/3；fixed 为 mass_preserve alpha1，预测 index6..14，全部50层，全部空间位置，覆盖有效物理时间的 temporal bins。107帧 video latent T32/audio T178；158帧 video T47/audio T263。两种视频 latent H46 W82。
篮球路由 bins[0,32)，覆盖位置0..106，其中补齐的105、106共享最后一个时间格；取书路由 bins[0,43)，覆盖0..144，其中补齐的144共享边界格，纯补齐的其余4格保持原生。评估统一排除全部padding。首次实际执行的layout、1000 attention调用、forced450路由调用、20次预测和20次Euler更新须由实际记录核验。

四次顺序：篮球 Native→fixed，root 核实际 pair gate 并看成片，再批准取书 Native→fixed。首次 gate 重验只有顶层 created_unix 变化时保留原文件字节；其余字段变化会拒绝覆盖。这样人工审批绑定的原SHA不会因批尾重验失效。

运行：.9 GPU3 UUID GPU-REDACTED，port8556，normal/reserve8，启动余量至少40GiB。同用户最多两张GPU；root 按真实服务PID/UID/start/cmd绑定peer并在CUDA启动前登记。新的107/158帧P1容量、吞吐和任务质量均需实际执行确认。出现OOM保留失败并精确释放，不自动更改科学条件重试。只root启动GPU。

已有数据估算：四次总计530输出帧，预计新增8GiB；启动磁盘至少剩16GiB。大型latent/condition保留远端，展示仅下载视频和必要JSON。所有成功与失败均保留。
