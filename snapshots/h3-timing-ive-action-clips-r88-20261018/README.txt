R88：IVEBench 素材片段探索

目的
在五条按原片动作选定的连续片段上比较普通编辑和固定时序引导。先检查官方编辑任务与原场景是否保留，再判断动作时序。五条全部保留结果。这一批属于素材片段探索，不报完整官方 benchmark 得分。

输入与次序
long_0047：原始帧0…119，原PTS [0,4.004)，男人换女人，107总帧/97有效帧。
long_0123：原始帧45…224，原PTS [1.5,7.5)，白面团改红，158/144。
long_0167：原始帧9…158，原PTS [0.36,6.36)，动画角色土色服装改白，158/144。
long_0173：原始帧105…248，原PTS [4.379375,10.385375)，成年女人换老人，158/145。
long_0174：原始帧9…152，原PTS [0.375375,6.381375)，女人白衣改黑，158/145。
严格有理数边界见 design/INPUT_PLAN.json。24fps输出按 clip_start+i/24 在固定原帧范围内选择最近PTS，等距离选较早原帧。有效采样时刻严格落在原区间内；之后末帧重复满足17k+5。二维像素处理复用R64的1280x720 resize，加左右16/上下8黑边，得到1312x736。
inputs/ 保存完整官方原视频、映射后的无损MP4、全部帧MD5和逐帧原索引。官方LFS SHA、revision、origin_mapping及URL保留在源选择清单。两个恰好6秒片段的t=6.0重复帧明确计为padding。audit/CLIP_BOUNDARY_CORRECTION.json保留封存前修订。

同源关系
configs/source_selection/ORIGIN_CROSSCHECK.json 按官方 source_name/URL交叉核对R73/R80/R83/R87。五条与这些已登记原视频无重复。R83/R87同七个源的两次登记只算七个来源。来源文件不同不证明拍摄者或场地独立。

方法与配对
每条依次 Native→forced。种子2026101701，20次Euler/20NFE，CFG1，沿原video12/audio3 sigma，未加载Turbo。固定引导为mass_preserve alpha1、Transformer全部50层、去噪索引6…14、全部有效时间相交bin中的空间query；纯pad bin保持原计算。无在线观察器。
六个核心数值文件逐字继承R87；R63原始图为共同模板。每对使用相同P1提示、原片、初始AV噪声与六份条件。正式结果门核前六步AV x0 exact、20次预测和最终快照、Native0/forced450次路由、真实同服务代次和输出几何。
提示遵循官方Subject/Shot结构；官方edit/source文本逐字保留。自写Subject描述只用于绑定可见对象和保留场景，未输入人工动作时窗。模板唯一适配为“photographic appearance”改为“original visual style”，保留动画原风格。官方target caption原样存档。

执行范围
当前仅本机CPU准备，未部署或启动GPU。.9 GPU0/8553为待root确认的运行模板，40GiB空闲门、normal reserve8；107/158帧及新prompt组合的实际容量尚待测。失败保留原数据并精确释放自己创建的进程，不自动更换数值设置。
首对0047实际pair gate完成后等待root查看，批准后才提交余下四对。ROOT_HANDOFF.txt给出入口；远程CPU验证和真实资源核验必须在启动前完成。
