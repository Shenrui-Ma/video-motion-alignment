R33：同预算、异时间位置的单次 Full 对照
设计版本 v1；仅设计，尚未实现、尚未启动 GPU。R31 新素材优先。

问题与范围
这条实验在已经看见 R27 开发样例成功后提出，检验那一次操作的位置是否重要。R27 在去噪索引 4 选择了 Full，其余 19 次选 Native；实际写入目标视频 bin 13–17。R33 固定同一索引和同一预算，只把写入位置移到 bin 23–27。它是事后机制对照，不能当成前瞻泛化验证或新的自动算法。

采用 source05 真人书记舞 / Sam Altman / seed 2026101311，1312×736、141 帧、24fps。原视频、肖像、文本、clean reference、embedding、标签、position IDs、AV 噪声、sigma 网格、模型和 attention 数值路径均绑定 R27 的实际记录。

实际位置核验
已读取 R27 归档的真实 position IDs 与 token tags，用 reference kinds、latent shapes 和 packed segments 区分肖像与参考视频。标签只有 6960 个文本/呈现项，不能单凭它给全部 87592 个 packed token 分类。
视频有 42 个时间 bin，最后索引为 41；空间 patch 网格为 23×41。时间名义跨度按 (1,4,4,4,4) 循环，最后还有 bin 41 覆盖 137–140 帧。只数 41 个 bin 会漏掉这四帧。这里的名义范围是位置映射，不是神经 VAE 精确感受野。

                      R27 Auto4             R33 Displaced4
query bins            13,14,15,16,17         23,24,25,26,27
原自动请求物理窗       44–59                 无在线请求，静态对照
实际名义帧范围         43–59                 77–93
各 bin 跨度            4,4,1,4,4             4,4,1,4,4
编码周期内相位         3,4,0,1,2             3,4,0,1,2
每层写入 query 行数    4715                  4715
同 bin 参考 key 数     每 query 943          每 query 943

移位为 +10 个 bin，恰好两个完整的五 bin 周期，即 +34 名义物理帧；没有使用 bin×4 估计。对应的 target/ref 空间坐标一致，时间坐标原生相差 235 RoPE 单位，保持不变。235 不是影片动作延迟。选中 query 仍读它自己时刻的参考 bin：这是换操作位置，不是读取错时间 key。
完整的十个 bin 行号/坐标及全部 42 bin 表在 evidence/ACTUAL_LAYOUT_CHECK.json；真实小 tensor 同目录封存。

最轻的严谨实现接口
采用独立的 FrozenWindowReplayRouter，复用 R27 的“当前 Native → 同输入可选 Full → 返回一个端点 → 一次 Euler”事务结构。固定 20 项 decision plan：仅 index 4 为 Full，bins=[23,24,25,26,27]；其他项为 Native。索引从 0 开始，index 4 是第 5 次 Euler 更新前的模型预测位置；这一位置的 Native/Full 分别是 NFE index 4/5。

每步都计算当前 Native，index 4 额外计算 Full，因此严格为 21 NFE、20 Euler updates、20 callbacks、1050 个 DiT block 调用、50 次 Full route。每次 route 写入 4715 行，全 50 层合计 235750 query-row-block 次写入。保持全 42 bin 的 router plan 和 R27 的二值 QueryGain；不可改成窄 query plan 以优化算量。

Full 沿用 R27 公式 O + g*m_ref*(A_same−A_ref)V_ref，alpha=1、radius=0、time_offset=0、所有 50 层。只读参考视频组；保留肖像、音频及其他组。必须保持现有 Flash/LSE、FP32 correction、dtype cast 和操作顺序。相同输入时非选中行与同数值后端的 prewrite full output 逐位一致，Q/K/V 不变。

这个静态机制对照不运行 20 次在线解码/pose/scan，也不调用 persistence selector。记录 online_observations=0 和 static_plan，不能伪造 20 份测量。保留所有 state/condition/noise/sigma/RNG 守卫及回调审计。R27 当前 POLICIES 只允许 automatic_windows；设置残留 fixed_indices 不能产生该模式，须在新 R33 目录做独立适配，不改 R27。

20 NFE 的简化方案会省掉 index4 被丢弃的 Native，改变分支预算并失去该处实际 Native 端点门，因此本版不选。以后若采用，必须显式修订设计。R33 省去 observer 的墙钟时间不能用于宣称自动控制更快；只记录效率成本。

必须通过的可比性门
1. 读实际成功 history、源/模型/条件/噪声/网格和准确输出名；所有失败单独保留。COMPARABILITY.json 已核 R3 N/F 与 R27 小条件记录除五处保存/行政字段外一致，噪声除三处行政字段外一致，实际视频 sigma 相同。
2. 新运行的 actual original/processed condition tree 与 R27 比较，只允许 original.positive[0].uuid 和 processed.positive[0].uuid 两叶不同，且每棵树两叶是相同、有效 UUID。其他叶全部保留。R27 大树容器已由实际 inventory 绑定，本次只做了小条件和前缀证据核查；实施时须提取并真正比较。R3 历史完整 postaugmentation 树缺失的边界不抹掉。
3. 逐份读取五个实际 R27 Native PT（0–4），核原 SHA、seed/shape/normalization/sigma，并比较视频和音频张量。0–3 的 chosen/Native 都须逐位相同；4 的当前 Native 在改变 Full 前须相同。packed input4 原记录是签名，未另存旧 raw input4 文件，不能写成两份旧新原始文件比较。精确签名和路径在 evidence/ACTUAL_PREFIX_0_TO_4.json。
4. 新 Native4 与 Full4 使用同一实际 x、sigma、条件和 RNG。Full4 及后续的旧轨迹从此永久 N/A，不能因后续回到 Native 就恢复历史逐位资格。
5. 保存全部 20 个 chosen intermediate + sampler final、20 个 Native branch +1 Full branch、实际 input4，逐项验 metadata、finite、SHA 和计数。成片 141 帧、24fps、PTS=i/24，完整 1312×736。
6. root 独立批准资源和启动；精确 owner 代际守卫、最多两张自用卡、服务驻留/释放按实际证据记录。这份设计本身不给 GPU 权限。

CPU/model-free 验证只覆盖接口，不先做新的生成锚点：实际 bin/row 映射、两个等预算 mask、原 R27 operator 的 selected/nonselected 行、QKV/RNG、21/20/1050/50 计数和错误输入负例。小型真实 Comfy fixture 验证单 Euler 事务和 cache 状态。任何额外完整的原位置重放均属新增推理，由 root 另定。

评价冻结
主窗仍为 50–65，另外三窗为 69–81、80–92、99–111。两置信度 0.3/0.5，49 个 lag −24..24，原 arm_direction / wrist_relative 主指标及拒判门完全不变。左右单臂和 body_xy 仅作敏感性。全片仍扫长度 16/32、stride4、三种手臂视图的 186 行；重叠行不是独立样本。

保留 Native、固定 Full6..14、Auto4 和 R33 全部输出。同时做四生成臂共同支持，以及 Auto4/R33 两臂共同支持；在源和所有输出有效交集上使用相同最小 clipped confidence 权重，沿用 >=0.8 的可用覆盖门。原四窗、全片、43–59 及补集不换；77–93 及补集作为预定诊断补充。UNKNOWN 原样输出，不用某个单臂或新窗代替失败主指标。

质量仅看预定 55/86/105 帧、42–82 含端点短片及完整 141 帧。Auto4 与 R33 用固定随机顺序作方法标签盲排，seed=2026101713；映射在检查新结果前写入。检查重影/额外肢体、编辑身份存在、房间、手部模糊和连续性，无法可靠区分记 UNKNOWN。姿态接近不等于身份或全片画质通过。

判读
- 若实际前缀/条件等门都通过，Auto4 四个主单元都在 ±2 内，而 R33 四单元均可判且相对至少差 4 帧、同帧误差在两门下也更差，且质量失败不能解释差异，可称该开发例存在位置敏感作用。较小或混合差异只描述，不贴成功标签。
- 若 R33 同样保持四个主单元 ±2 且没有明确全片/质量损伤，这条样例就不支持原选择位置的必要性。局部操作可能通过 joint attention 带来全局改善，这是重要反证。
- 77–93 有真实动作，且覆盖辅助评价窗，绝不是预知无效的空白区域。不同结果也可能包含内容/状态差异，不能推出原选择最优。
- R3 固定 Full6..14 是九次干预、另一物理支持，仅为既有表现参照。关于位置的主因果比较是 Auto4 对 R33。
- 只是一条事后开发机制对照，不证明自动算法普遍有效，不构成新的架构或文献首次性。

既有结果状态
独立 priority final 已完成：Native 主窗方向 13/13、腕 13/12；Auto4 方向 2/2、腕 2/1；固定 Full 均为 1。Auto 全片 186 行为 1 delayed /0 advanced /161 aligned /24 UNKNOWN。原始四窗和全扫都随 COMPARABILITY 封存。正式 R27 observer 重放/最终比对仍是另一条证据链，不能用这份设计替代。正常 seed 与新素材结论不由这条对照推导。
