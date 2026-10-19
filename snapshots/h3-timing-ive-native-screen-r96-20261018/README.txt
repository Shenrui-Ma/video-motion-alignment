R96：.41 单卡 Native-first 素材片段实验

本包迁移 R92 的全部五个来源，顺序为 long_0047、long_0123、long_0167、long_0173、long_0174。输入视频、原视频、clip/PTS 映射、P1-local-v1 提示词及六份数值文件保留原字节。每条先生成普通编辑，actual Native gate 通过后由 root 写 guide 或 skip。首个实际 guide 配对完成后再做一次结果审核。等待审核最多30分钟，届时精确释放当前服务；没有自动续跑或自动重发 POST。

两种方法都在 .41 新生成，20 Euler、CFG1、video/audio sigma shifts12/3、无 Turbo LoRA。固定引导保持 alpha1、indices6…14、50层、有效物理时间对应的所有位置bin；纯尾padding不纳入。已有 .9 输出不能替代本包 Native，也不作跨机器逐位相等主张。

运行来源：已有 .41 R72/R84 的隔离 ComfyUI、Python、dependencies 和模型目录。输入、输出、temp、cache 位于 /data4；模型仍从 /data3 原路径加载，不复制模型，不升级依赖。具体版本和导入证据在 audit/ACTUAL_CPU_IMPORTS.json，实际9个core hash/PTS/测试在 audit/TARGET_CPU_VERIFIED.json。

首次加载行政准入：GPU2 可用显存至少40GiB，normal/reserve8；cgroup 所有实际祖先的有限 high/max 中最小余量至少64GiB，并核 /user.slice high100GiB/max112GiB。64GiB是本次保守加载余量，模型实际峰值待实测。首次仅一张本用户卡，是否加第二张由 root 检查这次内存轨迹后决定。其他用户照常。

内存记录包括启动/preCUDA、每次原有资源采样及退出时的 memory.current、PSI 和 memory.events 差值。历史 high 累计计数不触发失败；祖先统计也包含其他用户，不能归因于本任务。运行中可选内存观测失败记录 UNKNOWN，已有 HTTP UNKNOWN/准确 PID 收尾和原总期限机制保留。

素材范围：IVEBench 素材连续片段探索。total/valid 分别107/97、158/144、158/144、158/145、158/145，1312×736@24fps，评估crop16,8,1280,720。原始有理 PTS 选择和尾padding记录随包保留，不宣称完整官方benchmark复现。

当前只完成CPU准备和被动部署；GPU及模型加载未由准备者启动。实际运行需root现场资源与精确身份审查。
