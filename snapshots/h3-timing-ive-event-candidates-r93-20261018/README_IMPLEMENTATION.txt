R93：五条动作事件候选，逐条普通编辑审核

来源与有效帧（24fps）
short_0370：完整88原帧，24000/1001fps → 89有效/90总帧。
long_0163：原25fps的[52,202) → 144有效/158总帧，原2.08–8.08秒。
long_0059：原25fps的[175,325) → 144有效/158总帧，原7–13秒。
long_0081：完整149原帧，30fps → 120有效/124总帧。
short_0203：完整90原帧，24000/1001fps → 91有效/107总帧。

每个24fps目标时刻严格位于原始半开时间区间；以实际有理PTS选择最近原帧，同距离选较早帧，尾帧补到合法H3长度。输入1312×736，评估裁剪16,8,1280,720，全部padding排除。完整原视频、官方LFS与SHA、原始PTS及逐输出帧映射保留在inputs与design/INPUT_PLAN.json。准备后逐帧lossless回读MD5核对。

前四例为主体或接触物体任务；0203为独立style extension。0163与0059属于IVEBench素材片段探索，评估不可写成完整官方片段得分。source-only事件审核计划只用于评价。

root原8份design文件逐字保留，五份P1候选直接进入相应两份图，提示词未追加。R92的六份数值文件逐字继承；20Euler/20NFE、CFG1、无LoRA、video/audio shift12/3，固定引导alpha1、indices6..14、50层与所有有效物理时间。所有有效时间重叠的latent bin生效，纯padding bin保留原生。

每个Native实际成功并通过NATIVE_RUNTIME_GATE后等待root决定guide/skip。决定绑定实际服务身份与输出、noise、conditions、graph、history等SHA。guide才提交该例forced；skip记录native_only及理由。第一个实际guided pair完成并通过真实配对门后再等root审核。审核等待上限30分钟，结束精确释放。原资源和生命周期守卫完整继承，最大2张自有GPU；没有自动重发POST或自动跨服务恢复。

本轮准备不启动GPU或watcher。正式启动、资源准入、服务身份登记、审核选择均由root执行。实际GPU显存与编辑效果待运行。所有五例及失败/跳过理由保留。
