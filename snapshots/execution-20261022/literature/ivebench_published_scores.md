# IVEBench 已发表成绩核查

核查日期：2026-10-22。完整逐项数据见 `ivebench_published_scores.json`。

## 官方基准结果

下表来自 IVEBench 作者的官方榜单；论文 Table 2 给出较低精度的同组数据。short 有400条，long 有200条；AnyV2V 的 long 排除65条 OOM，StableV2V 排除102条，其余方法该表未列排除。每项指标按适用任务计算，十二项均为越高越好。

|方法|short MF|long MF|short IS|long IS|short CF|long CF|
|---|---:|---:|---:|---:|---:|---:|
|InsV2V|0.855546|0.678833|3.0625|3.1000|4.0488|4.1250|
|AnyV2V|0.815908|0.824666|3.3350|3.2519|2.7500|2.6519|
|StableV2V|0.751333|0.773338|3.5600|3.4490|1.7875|1.7857|
|VACE|0.885873|0.883994|2.1625|2.2700|4.0325|3.7350|
|Lucy-Edit-Dev|0.677938|0.734630|2.8375|2.6450|3.8250|4.1300|
|Omni-Video|0.507224|0.551065|3.3600|3.5300|2.8450|2.5900|
|ICVE|0.457221|0.483956|3.6175|3.6250|3.5500|3.4750|
|Ditto|0.789851|0.728152|3.8700|3.9250|3.6350|3.6850|

[官方完整十二项榜单](https://ryanchenyn.github.io/projects/IVEBench/)；[论文 Table 2、3、Appendix D](https://arxiv.org/html/2510.11647v2)。

## 后续方法论文

|论文中的方法|Total|Quality|Compliance|Fidelity|
|---|---:|---:|---:|---:|
|LucyEditDev|0.6220|0.8164|0.3679|0.6817|
|Kiwi-Edit-5B|0.6936|0.8101|0.5182|0.7524|
|Qwen-Video-Edit|0.6765|0.7752|0.5256|0.7286|
|VidToMe|0.6297|0.7826|0.4010|0.7056|
|WANEdit|0.6072|0.7973|0.2801|0.7441|
|FlowDirector|0.6264|0.7771|0.3765|0.7255|
|StreamEdit|0.6229|0.8238|0.2921|0.7530|
|EditVid|0.6847|0.8114|0.4587|0.7839|

[EditVid Table 3](https://arxiv.org/html/2609.04190v1#S5.T3) 报告上面四个 IVEBench 聚合分数。EditVid 使用 FLUX.2-Klein-9B、4步；论文未单列该表的MF和实际样本数。另整理的50条分为24条一般编辑、26条参考引导编辑，使用独立VLM及人工评价。

[AVE Table 2、3](https://arxiv.org/html/2610.11037v1) 的 short/long Total 为0.7058/0.6875，Motion列为89.26/88.95，CF为4.10/4.16。其表注称Motion为motion smoothness，而基线值逐一对应官方MF×100；展示保留Motion原名。采用Wan2.2-I2V-A14B，并训练710M参数的运动编码器与ControlNet。

[Kiwi-Edit原文](https://arxiv.org/html/2603.02175v1) 的测试集是OpenVE-Bench、VIE-Bench和RefVIE-Bench；上表的Kiwi IVEBench成绩由EditVid作者报告。

## 与本项目展示并列的方式

内部十组与纯IVE九组分别求均值。外部表单独写样本范围和原始绝对分；本项目另列MF相对参考视频的差值。外部论文未提供参考自评分，外部MF差值留空。跨论文数据用于观察成绩水平；同方法配对排序使用本项目相同样本。
