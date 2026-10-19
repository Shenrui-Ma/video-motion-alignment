R98：FlexiAct 俯卧支撑角色替换修复复验

目标：使用 game_man_4 的短黑发动漫男性身份、绿披肩、棕外套、浅色衬衣/领巾、深色裤子与浅色交叉绑带、深色靴子及腰侧装备，复现 human2animal_1 的完整低伏、撑起、伸背、拱背动作。背景沿目标图保持纯白。这与旧 R66 请求的角色与场景来源相同。

唯一一条 Native：r98_human2animal_1__game_man_4_seed2026101701_native。
当前没有时序干预、第二条任务或自动追加实验。GPU 推理由 root 单独启动。

变化与保留
旧 R66 实际图来自 incoming/native_graph.json，与原 history 对应。新图逐字段变化见 audit/PARENT_DIFF.json：唯一科学输入变化是 node5.prompt；其余变更为新的 run ID 和审计路径。源视频、人物原图、seed、20 Euler、CFG1、video/audio sigma12/3、模型名、参考图 match 尺寸、semantic_fps2、phase0、158总帧147有效帧全部保持。
实际 R66 原 AV noise PT 已从 .41 复制并逐字绑定；本次重新编码新提示和参考条件，保存全部条件及20步x0和最终latent。六个数值模块与 R66 原文件逐字相同。

旧 R66 在 .41 Torch2.11.0/PyAV16.1.0；R98 使用 .9 Torch2.5.1/PyAV16.0.1。该任务属于跨环境的任务修复复验，旧/新结果差异不能独归提示词。旧 clean VAE/Qwen 像素哈希会作为描述记录；本次真实输入必须精确符合生成前在 .9 独立 Comfy CPU 解码所得 expected_input_pixels_host9.json。原始AV噪声必须逐字一致。新文本联合embedding、文本长度、clean VAE数值和x0可随提示/运行环境变化。

官方依据
https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md
完整原文与下载响应保存在 design/official_ref-en.md 和 OFFICIAL_GUIDE_SOURCE.json。
按六段格式定义 Subject1 角色、Subject2 白背景、Subject3 动作；Picture1 仅作为 Subject 的外观来源，Video1 作为连续结构/时间来源。任务前缀 reference generation，使用 [Shot 1]；没有添加绝对动作时刻。

输入与形状
原人物 JPEG 975×600，SHA4e6ba7513b5e1580e3c713cdaea8df23c71411764e5ead2a59facd07bb50d33e。
原 native match 960×608，clean image latent 1×24×1×38×60，570视觉token。
视频 1152×768、158@24；前147为49@8逐帧重复3次，末11为最后一帧padding。有效评分可取0,3,...144；展示取0...146。

验收
runtime gate 只验证正确执行和数据归属。角色、衣服、背景、动作阶段与伪影分别由成片审核，具体规则 design/TASK_ACCEPTANCE.json。衣服转移但源脸/长辫残留，或中段短暂动漫脸，均不等于角色替换成功。新结果待实际推理。
