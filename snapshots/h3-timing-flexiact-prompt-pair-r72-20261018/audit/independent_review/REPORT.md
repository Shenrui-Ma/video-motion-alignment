# R72 独立审查

2026-10-18。结论：CPU 准备通过本次审查，未发现阻碍按冻结方案进行首对容量试跑的问题。尚无 R72 GPU 成片或容量结论。

- **官方配对确实存在。** 归档的 FlexiAct `fitness/val_image.csv` 第 6 行（零起点）对应 `game_man_5.jpeg`，`one_leg/val_image.csv` 第 1 行对应 `movie_man_9.webp`。原始目标图 SHA 分别为 `fb2f5f3f…c0e2`、`94c1ff88…2ce9`，与 R72 输入及冻结 HF revision 的 LFS SHA 一致。两者是新目标配对，动作源仍为已用的 fitness/one_leg；不能计作两个新动作源。
- **任务分工一致。** P0 逐字等于 R66 原 prompt；P1 将 `<Picture 1>` 的人物外观与环境、`<Video 1>` 的动作及时间明确分配。两组 P0/P1 图的差异只有 `/5/inputs/prompt` 及输出、audit、conditioning 的运行 ID；种子、视频、图像、sigma、采样与其他数值输入相同。相较 R66 相应动作源，视频字节相同，人物图是本轮明确选定的新图。
- **caption 有实际图像核对。** 我查看了两张原始输入图。game_man_5 是金红色、装甲式身体的游戏人形，官方文字为 humanoid cartoon monster。包保留原 caption，并明确把 P1 的身份描述来自实际图像，避免将“monster”解读成需新增的身体结构；不需要宣称两种宽泛称呼必定逻辑冲突。movie_man_9 为穿深色西装的年长男性。人物身份描述没有来自新生成结果。
- **比较的归因范围写清楚。** P1 增加了具体源动作描述、目标身份描述、参考职责、保留要求和六节格式；这是整套 prompt 适配，不能单独归因于格式。源动作使用冻结官方 caption；两臂仍要求完整动作。该诊断与固定 ON 方法的效果须分开报告。
- **真实成对门禁合理。** `r72_contract.py:85` 比较直接 VAE 条件、原始预处理视频、Qwen 编码前呈现和目标形状；`verify_pair.py:76–85` 读取实际 AV noise PT/hash，检查两套独立 conditioning，允许联合 embedding、token/packed positions 和全部 x0 随 prompt 改变。两臂都为 Native、0 routed calls，无前六步相等要求。
- **形状与继承一致。** 158 帧、1152×768、24fps，147 有效帧；官方采样 0,3,…144 共 49 帧。视频 latent `[1,24,47,48,72]`，audio `[1,32,2,263]`。两目标图经原生预处理分别为 1248×704 / 1152×768，图像 latent `[1,24,1,44,78]` / `[1,24,1,48,72]`。`reference_geometry_matches` 核对 image/video 两参考段和实际 packed layout。六个数值文件与本地 R66 逐字相同，远端部署报告也逐项确认。

验证：独立计算 50 项 seal 的全部 SHA 相符，检查实际四份图及两份官方 CSV；读完 32 项远端测试记录；独立复跑 12 项 actual-pair verifier 回归，全部通过。回归覆盖噪声改变、blob 修改、VAE/Qwen 输入改变、错误 packed reference、旧 conditioning 误复用、快照缺失和 P0/P1 预测允许不同。记录见 `VERIFIER_TESTS.log` 与 `EVIDENCE.json`。

运行前仍沿 root 调度等待 R64 释放 GPU6，核当时实际余量及自有 peer 登记。40GiB 门槛是已授权的首组试跑条件，完整 P1 轨迹容量待实际记录。此次审查没有修改生产源码或启动 GPU。
