R86：氧气罩样例的真实在线时序引导准备

目标
在 R73 short_0252 的同一个 P1 角色编辑任务上，新增一次 visible_only 在线闭环结果。每个 Euler 步都从当前 Native endpoint 解码、测量、判断。选出的时间窗和启停随新轨迹变化，使用原 R59 阈值。R81 已有的离线观测只用于 CPU 回归，生产程序没有读取这些测试观测的入口。

指定对象与自动化范围
成人 bbox 中心横坐标 .40–.75 是按源片和编辑任务指定的空间筛选，原 largest/IoU 选中人若落在范围外，该帧记为无人可测。时间窗口、开始和停止由当前 x0 自动选择。当前引导覆盖选中时间 bin 的全部空间 query，未实现身体局部空间 mask。

执行
每步 Native forward → 同步隔离 VAE → CPU DWPose → R81 成人筛选 → 原 R59 scanner/Controller → 可选同状态 Full forward → 原 Euler 更新一次。alpha1、50层、mass-preserving same-time attention；20 次更新，NFE=20+实际触发次数。科学 UNKNOWN 返回 Native；技术失败保留错误并收尾。

数据与可比性
输入、原 P1 提示词、seed2026101701、sigma、CFG1、20Euler、1312×736×107@24、有效98帧沿 R73；配对噪声复制原实际缓存。6个干净条件和父噪声在 CPU 验证。全部20旧 Native x0可用；首个实际 ON 之前及该步 Native 必须与父轨迹精确一致，后续永久退出历史逐步相等比较。
R73固定算子与 R59 query_gain 全一的 FP32/bf16 dense-attention CPU 比较逐位一致。实际 GPU Flash路径的运行核验仍依赖首轮成片和真实审计。图像VAE/姿态跨主机边界变为 .9，因此首次触发无需与旧 .41 解码的 R81 index2一致。

来源与限制
复用已完成 R59 的观察和同状态分支代码、R73的条件/噪声/被动x0记录器、R81成人筛选。当前属于既有方法的单案例闭环验证，无新公式主张。序列中间和最终结果仍须检查任务完成、动作、伪影、物理时差和官方MF。
原 core.py 中弱兜底字段是未启用的继承审计元数据，本包只注册 visible_only，所有触发 alpha=1。未新增弱兜底实验。

资源
.9 GPU3主推理，GPU1隔离decoder，端口8551；同时占用两张己方卡。启动前需 root 核定两卡可用并留 main40GiB、decoder16GiB实际空闲。16GiB是受控试跑预算，.9在线107帧峰值尚未实测；R81 .41 full107 decoder峰reserved5.613GiB仅作历史依据。原 normal/reserve8、kernel和checkpoint不变。
单任务deadline14400s，服务上限18000s；读取HTTP超时/unknown_missing继续等待原截止时间，POST仅一次。根controller消失时watchdog精确停止原服务；decoder/observer按父代次清理。清理回执分别核主进程和每个实际登记的CUDA子进程。
正式程序、CPU测试、输入约64MiB；预计新增条件/轨迹/20段观测视频共约2–4GiB，启动门保留8GiB磁盘余量。大型PT保留远端。

当前状态
本地CPU实现准备。实际父材料重核、.9 CPU imports、两个GPU容量、真实online完整执行尚未完成；所有缺项会阻止正式launch。旧R59/R73/R81/R84文件未更改。
