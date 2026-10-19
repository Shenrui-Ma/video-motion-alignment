# 停止时加入经验误差余量：现有证据够不够

结论：**现有资料足以说明必须把读出误差当作限制，并足以给一个开发变体提供明确动机；不足以校准出能可靠保证±2帧的停止余量，也不足以推荐现在直接用“停止阈值改成0或−1”作为下一实验。** 当前先保留观察器分辨率/误差限制，等已排R13桥接与R14正常筛查结果，再决定是否更换观测部位。本文没有实现、运行或选择新阈值，也不声称新颖性。

## 计数和比较定义

只审查实际控制器采用的**全画面 same_phase_gap5**：原不等宽名义时间中心、5latent-bin（17物理帧）跨度差分、±24整数帧搜索、冻结退化/歧义/边界门。`e = 独立姿态lag − gap5 lag`，正e表示gap5低估延后。方向为原主指标，腕部单列；两置信阈值是敏感度检查，不是两份独立样本。unknown不填零、不算准确，更不能被接近0的未合格最优点替代。

这里只统计**已有并有来源绑定的读数与同阶段独立姿态**。同视频的多个窗口、多个去噪快照、两阈值、同张量精确重放都高度相关。下面的“格数”不等于样本数；没有抽样总体、统计置信区间或普适覆盖保证。

## 校准来源与范围

| 资料 | 范围/是否当前开发素材 | 已知与unknown | 已知最大绝对差与限制 |
|---|---|---|---|
| VAE人为移位控制 | source05原人物，1312×736×141；原片/延后4/延后8/恒定帧，原四窗。正是当前素材，但非身份编辑 | gap5零/4/8共12格均正确；恒定4窗拒判 | 对人工移位真值差0。只证明这组原始输入控制；不校准跨身份、去噪端点、负向提前或亚17帧短事件 |
| R2跨身份冻结对照 | source05/07→Sam；05原生与全程mass各index5/10/15/final，07两轨迹仅final；均1312×736×141 | 全画面gap5共38窗：strict pose可用21、未知17。方向59已知/17未知（76阈值格）；腕57已知/19未知 | 方向maxabs2，e∈[−1,2]；腕maxabs2，e∈[−2,2]。不是独立于当前开发样例的校准集 |
| 同机R4 native预检 | .41 source05/Sam/seed1，同几何；精确重放R2 | final方向7已知/1未知、腕6已知/2未知；9快照36个内部读数均accepted，但当时early pose未测 | final方向maxabs1、腕maxabs2；不能把final真值复制到early。后来R6 index5补出3帧反例，见下 |
| R7有意选出的正常native | 同source05/Sam/seed1但1024×576；index5/10/15/final，与旧正常成片精确重放 | 16窗32阈值格：方向27已知/5未知；腕25已知/7未知。三个early的组合门8可用/4未知 | 方向、腕maxabs1，e均在[−1,1]。这是几何变化且按已知正常结果选的负控；不能当同1312分布自然正常集 |
| R6、R9闭环开发诊断 | .41同source05/Sam/seed1，同1312几何；见下方全部主窗同阶段行 | R6 index5已知、10/15部分或全部未知；R9 guided6/7未知、native8已知。R9 inherited5与R6相同，不重复计数 | native11对独立14，已经出现maxabs3，早于R12。说明旧“≤2”经验范围不覆盖这些已存数据 |
| R12停止点新诊断 | .9当前开发病例；index10/15实际native端点 | 两点方向/腕共8个阈值格全已知 | index10内部2对方向/腕4；index15内部2对方向3、腕4；maxabs2。是结果后诊断，不能当未见测试集 |

原始相邻差分、整体去均值、phase_mean_centering和constant模板都有各自失败，保留在旧报告；不能把不同观察器的误差混进当前gap5余量，也不能换ROI拿更有利结果。pose自身的人为时移/幅度校准是另一个测量层，不是gap5真实预测误差的证据：它已证明角运动幅度减半仍可给lag0，因此“停止时phase合格”也不等于动作完整。

## 当前主窗开发诊断：所有已解码同阶段项

`U`为冻结独立姿态拒判；表内未使用final给early补标签。两阈值按0.3/0.5排列。

| 轨迹/实际分支 | index | gap5 | 方向 | 腕 | e或unknown |
|---|---:|---:|---|---|---|
| R6 native前缀 | 5 | 11 | 14/14 | 14/14 | +3；是已存在的反例 |
| R6 Full | 10 | 10 | 13/U | U/U | 已知方向+3，但组合门未知 |
| R6 Full | 15 | 11 | U/U | U/U | U；不能证实误差小 |
| R9 Full | 6 | 1 | U/U | U/U | U；重影/关节覆盖不足 |
| R9 Full | 7 | 1 | U/U | U/U | U；不把未合格近零最优点当真值 |
| R9 native | 8 | 11 | 14/14 | 14/14 | +3 |
| R12 native首次OFF | 10 | 2 | 4/4 | 4/4 | +2 |
| R12 native继续OFF | 15 | 2 | 3/3 | 4/4 | 方向+1，腕+2 |

上述8行中方向已知9/16阈值格、未知7；腕已知8/16、未知8；所有已知最大abs3。只取更理想的早期跨身份表而丢掉这些3帧项，会造成选择性校准。R9 index5继承R6同一张量和pose，不另加一行提高样本量；R6从未保存index6/7/8，不能补造。

末步模型端点与sampler_final存在浮点Euler差异，未额外逐位/独立解码核实的末步读数—成片配对只作辅助，不混入上面精确同阶段误差界。已有辅助记录也没有补齐unknown：R6末读11对final13/U、腕13/U；R9末读10对final12/U、腕13/U；R11连续末读1对方向0/0而腕U/U；skip7末读11对13/U与腕13/U；R12末读2对final方向3/3、腕4/4。没有任何一项能证明统一两帧界。

## 为何不能从“有误差”直接推出可用停止阈值

若独立达标要求 `|L|≤τ=2`，并且假设（仅是假设）误差有对称界 `|L−h|≤m`，区间安全的停止条件是：

`[h−m,h+m] ⊆ [−2,2]`，等价于 `|h|+m≤2`。

已知3帧反例使 `m=2` 不能覆盖所有现存可判数据。取 `m=3` 时，**停止集合为空**，没有任何中心h可以让宽6帧的误差区间容纳在宽4帧目标内。即使按已观测的有符号总范围 `[−2,+3]`，区间宽5帧也超过目标宽4帧。样本最大值本身仍不是未来误差上界；不能把这条代数检验说成概率保证。

因此，把原停止界2改为0可以写成“假设m=2时的开发规则”，但它既没有覆盖已知3帧反例，又可能只是同一开发数据上的容差调节。当前不建议为了让R12跨过±2而试0、1、−1一排阈值。

## 可以明确写出的候选规则，以及为什么当前不推荐执行

唯一可写清的**单侧开发候选**是：已有明确正延后触发之后，取旧数据已见最大低估 `m_+=3`，只有 `h+m_+≤2` 才按“残余延后足够小”退出。形式上是 `h≤−1`；保留未触发时的native、不把unknown视为合格、保留原负向安全关闭及原最大index19终止，不引入阈值搜索。

它不是绝对相位停止证书。该余量主要来自大延后native11→pose14，是否适用于接近0的停止状态未校准；会要求读数进入提前区，带来过调。现有Full端点常给0，可能使这类规则一直不停，增加已有ghosting/身份或背景损伤风险。若严格延续R12只观察native，Full读数不直接参与停止，但仍没有证据保证该历史下native会到−1；不能拿R10固定Full历史的读数预测另一新控制历史。

所以本候选只作为**未实施的可证伪设计记录，不作为当前推荐下一实验**。若后续决定试它，必须在新结果前冻结一条规则和全部失败处理，称开发变体，不能称已完成误差校准、架构创新或保证修复。

必要对照是：同actualcondition/noise的native；原未改R12；固定 `[6,7,8,9]`；固定Full `[6..14]`；才是该单一margin变体。6–9来自开发样例实际mask，6–14是已有效强基线，不能删掉其一而仅与native比较。先用已知seed2做坏例迁移，再结合R14是否得到同几何自然正常例，均保留背景失败、unknown、四窗/shape/common-support和固定质量帧。若margin变体只是固定延长且不优于Full，不能说实例适应或误差处理有独立收益。只记NFE/调用位置/耗时，不做速度诊断。

## 数据缺口与分布外边界

- source05是反复用于开发的同一主样例。source07属于相关舞蹈、同目标Sam且原生高阈值多unknown；并非独立动作类别/身份域。
- 近零校准多数是全程mass已经修正的端点，不能代表所有native停止状态。R7虽是native正常，但分辨率不同且事先按正常成片筛选；当前没有已完成的同1312自然正常控制验证。
- 已经见到Full端点的视觉重影并使pose拒判；这些未知格没有可计算误差上界。固定margin不能弥补观测不可判。
- 5bin差分跨17物理帧，约0.708秒，可能混合很短的动作。人工正向延迟4/8控制不覆盖更短事件、真实周期/重复动作、摄像机运动、多主体、遮挡、快速切换、不同编辑要求、不同identity/source、其他VAE/帧率/几何。
- same-input原生观察消除了本次执行器的直接读数影响，但当前状态已经受到历史干预；它仍不是独立未干预轨迹。
- pose是独立特征测量而非人工标注的无误差真值；两套特征之间的偏差不能直接当物理相位的真实误差分布。

当前合理动作是保留这些限制，完成已排R13/R14再判；本报告不支持自动扩阈值搜索，也不否定日后用新独立校准集建立任务化观察器或经验规则。

## 附表A：冻结跨身份全画面gap5的全部38窗

下面同时报告所有known和unknown，没有只摘通过项；原strict门对final主要检查方向双阈值，对early另含方向/腕一致性，不能混称全都双特征精度通过。

| source/轨迹 | snapshot | 窗口 | gap5 | 方向 .3/.5 | 腕 .3/.5 | 方向/腕已知最大绝对差 | 原strict pose门 |
|---|---|---|---:|---|---|---|---|
| 05/native | x0_step005 | 50–65 | 10 | U/U | U/U | U/U | U |
| 05/native | x0_step005 | 69–81 | 9 | 9/U | U/U | 0/U | U |
| 05/native | x0_step005 | 80–92 | 8 | 8/U | U/U | 0/U | U |
| 05/native | x0_step005 | 99–111 | 3 | 4/4 | 4/4 | 1/1 | known |
| 05/native | x0_step010 | 50–65 | 11 | 13/13 | 13/12 | 2/2 | known |
| 05/native | x0_step010 | 69–81 | 9 | 9/U | 9/U | 0/0 | U |
| 05/native | x0_step010 | 80–92 | 7 | 8/8 | 8/U | 1/1 | U |
| 05/native | x0_step010 | 99–111 | 3 | 4/4 | 4/4 | 1/1 | known |
| 05/native | x0_step015 | 50–65 | 11 | 13/13 | 13/12 | 2/2 | known |
| 05/native | x0_step015 | 69–81 | 9 | 10/U | 10/U | 1/1 | U |
| 05/native | x0_step015 | 80–92 | 7 | 8/7 | 8/U | 1/1 | U |
| 05/native | x0_step015 | 99–111 | 2 | 4/4 | 3/3 | 2/1 | known |
| 05/native | sampler_final | 50–65 | 11 | 13/13 | 13/12 | 2/2 | known |
| 05/native | sampler_final | 69–81 | 9 | 10/U | 10/U | 1/1 | U |
| 05/native | sampler_final | 80–92 | 7 | 8/U | 8/U | 1/1 | U |
| 05/native | sampler_final | 99–111 | 3 | 4/4 | 4/4 | 1/1 | known |
| 05/mass | x0_step005 | 50–65 | 0 | 0/0 | 0/0 | 0/0 | known |
| 05/mass | x0_step005 | 69–81 | 0 | 0/U | 0/U | 0/0 | U |
| 05/mass | x0_step005 | 80–92 | -1 | 0/0 | 0/0 | 1/1 | known |
| 05/mass | x0_step005 | 99–111 | -1 | -1/-1 | -1/-1 | 0/0 | known |
| 05/mass | x0_step010 | 50–65 | 0 | 0/0 | 0/0 | 0/0 | known |
| 05/mass | x0_step010 | 69–81 | 0 | -1/U | -1/U | 1/1 | U |
| 05/mass | x0_step010 | 80–92 | -1 | 0/0 | 0/0 | 1/1 | known |
| 05/mass | x0_step010 | 99–111 | -1 | -1/-1 | -1/-1 | 0/0 | known |
| 05/mass | x0_step015 | 50–65 | 0 | 0/0 | 0/0 | 0/0 | known |
| 05/mass | x0_step015 | 69–81 | 0 | -1/U | -1/U | 1/1 | U |
| 05/mass | x0_step015 | 80–92 | -1 | 0/0 | 0/0 | 1/1 | known |
| 05/mass | x0_step015 | 99–111 | -1 | -1/-1 | -1/-1 | 0/0 | known |
| 05/mass | sampler_final | 50–65 | 0 | 0/0 | 0/0 | 0/0 | known |
| 05/mass | sampler_final | 69–81 | 0 | -1/U | -1/U | 1/1 | U |
| 05/mass | sampler_final | 80–92 | -1 | 0/0 | 0/0 | 1/1 | known |
| 05/mass | sampler_final | 99–111 | -1 | -1/-1 | -1/-1 | 0/0 | known |
| 07/native | sampler_final | 54–69 | 16 | 15/U | 15/U | 1/1 | U |
| 07/native | sampler_final | 75–88 | 17 | U/U | 15/15 | U/2 | U |
| 07/native | sampler_final | 98–111 | -4 | -5/U | -5/U | 1/1 | U |
| 07/mass | sampler_final | 54–69 | 0 | -1/-1 | -1/-1 | 1/1 | known |
| 07/mass | sampler_final | 75–88 | 0 | -1/-1 | -1/-1 | 1/1 | known |
| 07/mass | sampler_final | 98–111 | -2 | -2/U | -2/U | 0/0 | U |

## 附表B：R7实际已解码三点与final的全部16窗

该表补入原R7观察器报告之后完成的独立early pose。其余已存latent但未解码时刻没有标签，不能作为更多校准样本。

| R7 snapshot | 窗口 | gap5 | 方向 .3/.5 | 腕 .3/.5 |
|---|---|---:|---|---|
| x0_step005 | 50–65 | 0 | -1/-1 | -1/-1 |
| x0_step005 | 69–81 | 0 | U/U | U/U |
| x0_step005 | 80–92 | -1 | 0/0 | 0/0 |
| x0_step005 | 99–111 | 0 | 0/0 | U/U |
| x0_step010 | 50–65 | -1 | -1/-1 | -1/-1 |
| x0_step010 | 69–81 | 0 | -1/U | -1/U |
| x0_step010 | 80–92 | -1 | 0/0 | 0/0 |
| x0_step010 | 99–111 | -1 | -1/-1 | -1/-1 |
| x0_step015 | 50–65 | -1 | -1/-1 | -1/-1 |
| x0_step015 | 69–81 | 0 | -1/U | -1/U |
| x0_step015 | 80–92 | -1 | 0/0 | 0/0 |
| x0_step015 | 99–111 | -1 | -1/-1 | -1/-1 |
| sampler_final | 50–65 | -1 | -1/-1 | -1/-1 |
| sampler_final | 69–81 | 0 | -1/U | -1/U |
| sampler_final | 80–92 | -1 | 0/0 | 0/0 |
| sampler_final | 99–111 | -1 | -1/-1 | -1/-1 |

## 证据文件

以下均为本地已存一手结果；本次只读取并汇总，未调用GPU/远端或重新估计pose。

- `/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/vae_phase_calibration/cross_identity/POSE_COMPARISON.json`；SHA256 `6404e0d35a055b7127dac0552f73cde73e7f404ca689a9c17d262e62a1f5a145`。
- `/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/vae_phase_calibration/SUMMARY.txt`；SHA256 `20a4bbe7456446a1f4e0908caee184b111e106c49866541b8ac02c1db3753530`。
- `/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/metric_calibration_20261016/RESULTS.txt`；SHA256 `137a9fc7c11bac1972bfd7d6e46026621c3dc8a99dc2958f96d6ae784f4e3df5`。
- `/Users/researcher/DevProjects/h3-timing-feedback-r6-20261016/analysis/native_observer_precheck/RESULTS.json`；SHA256 `41c5e0dc44af85f4b20ce50b38b4965f448d54045f5417ed92fa4c27e0f39a16`。
- `/Users/researcher/DevProjects/h3-timing-normal-replay-r7-20261016/analysis/observer/RESULTS.json`；SHA256 `ee20e02a47563aa361d30d6ef6cdeb4f3122ceb885bdfb38dc275a9131f7fc6f`。
- `/Users/researcher/DevProjects/h3-timing-normal-replay-r7-20261016/analysis/observer/POSE_COMPARISON.json`；SHA256 `51d1fd787df9f460609bbfb7374c051007a9174d970a8f6edfcfff9b590d7c1c`。
- `/Users/researcher/DevProjects/h3-timing-normal-replay-r7-20261016/analysis/pose/R7_EARLY_POSE_REVIEW.md`；SHA256 `0e2dae887fd82d82aa120662c3b576eb8f18278e761b8fd57df5ec7c95626c54`。
- `/Users/researcher/DevProjects/h3-timing-feedback-r6-20261016/analysis/pose/R6_EARLY_STAGE_REVIEW.md`；SHA256 `bb19913d9508f40730c9f5216caeff76d7685c323219677ffe34a859682db5a4`。
- `/Users/researcher/DevProjects/h3-timing-hold-control-r9-20261016/analysis/pose/R9_EARLY_TRANSITION_REVIEW.md`；SHA256 `8cbc9865e96d9fff6d4110fe345a6510c9acb0e81981bb26a98b8b739253d016`。
- `/Users/researcher/DevProjects/h3-timing-native-observer-r12-20261016/analysis/pose/early/R12_EARLY_REVIEW.md`；SHA256 `b9ee675e5a3ca922ccd08a86c628d898eb42a6406cb61f8c1989f6c1bbe2c127`。

写入时间UTC：2026-10-16T11:38:43.826662+00:00。R14消费者仍未启动，等待实际launch通知。
