用途：中文论文式进展 HTML 的独立整合模板；全部写入当前目录，不覆盖 Downloads 交付。

当前产物
- DRAFT_NOT_DELIVERED.html：约9.8MB，4条已完成开发视频及1条消融对照、Attention SVG全部内嵌。
- build.py / template.html：事实读取与排版分开。每组三列烘焙进同一个MP4，共用一个播放器；derived_assets保存来源SHA、裁剪坐标、逐帧对应和时间戳校验。
- benchmarks.template.json：FlexiAct与IVEBench各5条固定任务，当前正式分数留pending。
- benchmark.schema.json：公开评分接口JSON Schema。build.py额外校验固定ID顺序、策略冻结、数值证据和SHA。
- DRAFT_MANIFEST.json / STATIC_CHECK.json：素材与数据来源、静态检查及浏览器尚未检查状态。

重建
python3 build.py --data benchmarks.template.json --output DRAFT_NOT_DELIVERED.html
可另建同目录内的实际数据JSON；builder限制输出位于当前目录。

接入正式结果
1. 保持benchmark和case原顺序、planned_denominator=5；每例同时保留ordinary与automatic。
2. 完成的metric要求status=complete，value与evidence指定JSON路径的原值一致。
   evidence格式：{"path":"/absolute/result.json","sha256":"...","json_pointer":"/cases/0/mf"}
   JSON pointer遵循RFC6901；未知/失败/pending的value必须为null。
3. official_motion_fidelity还需evaluator{name,revision,protocol_id}，记录实际运行的官方评测版本与适配协议。
   timing_lag_ms单位ms，正晚负早；edit_success是布尔值，需实际评价JSON证据。
   timing_lag_ms为complete或unknown时，case还需timing_evaluation={body_part,frame_interval_inclusive:[start,end],fps}；同组普通/自动共用该评价部位和帧段，表格同时显示部位、帧段和两组时间差。
4. video/source_video格式：{path,sha256,mime:"video/mp4",width,height,fps}。
   原单视频省略panel_count/panel_index；已拼接视频可指定列总数和零起始列号。
   visible_height可去除既有底部标签，保留画面；网页重新显示Source/普通编辑/完整自动法。
5. IVEBench政策先由R53独立证据冻结。policy_id选delay_only_R50或signed_R53；policy_evidence绑定正式POLICY_SELECTION.json。
   两个policy应独立报告，切换策略不能混合旧结果。当前R50始终标为延后检测。
6. 每例主图三列；消融放独立节。新增消融需读取已有事实并说明改动，不能将固定引导收益归于局部区间选择。

事实口径
- 0.5是固定的相对误差gain筛选阈值；Attention强度alpha=1。
- 检测从固定去噪索引0开始；自动的是干预启停。±24帧搜索边界及间隔至少4帧且误差差距不足5%的多峰拒绝为UNKNOWN。
- 当前修正选定time bin内全部空间位置、全部50层；没有人体空间mask。
- 时间差表0.3/0.5两数字对应姿态置信阈值。UNKNOWN保留。
- 已有消融：片段05自动+83ms、异位+42ms；40372自动-42ms、相同四次全片0ms、单次全片+83ms。
  直接结论：支持时序干预有效，尚未建立局部选择的额外收益。

检查范围
已检查证据SHA、现有数字读取、未完成分数保护、固定分母、策略未冻结时禁止自动结果，以及15组各3列的HTML结构。
浏览器布局/播放尚未检查，未尝试绕过既有浏览器policy block；本文件仍为草稿。
本次仅用本机FFmpeg生成5条三列展示视频；各141帧，逐帧PTS与来源一致，最大差为0。没有新推理、姿态计算或GPU任务。
python3 check_revision.py 可重跑14项内容/数据/播放器结构验证。
