R90：one_leg → movie_man_9 的 P1 提示词控制

只生成一条 Native：r90_one_leg__movie_man_9_seed2026101701_native。
沿用 R85 P0 的同一源视频、目标图、seed2026101701、1152×768、158帧/24fps、147有效帧、20Euler。P1使用此前R72已登记文本的完整原字节，文件SHA11efbddcdd973499bea0f716f55429f789a5c0275462bc82d6c5fd925cd2207f。
这条任务由参考图提供人物和场景，由参考视频提供动作。P1包含主体定义、完整动作文字及参考职责，比较的是整个prompt bundle的效果；单项措辞的因果作用需另外控制。

固定时序引导未加入本队列。实际执行要求20次预测、1000次原生Attention调用、0次路由；本次独立记录条件、原始AVnoise、20份x0与最终采样结果、完整成片及效率。
启动前从R85原缓存按字节复制AVnoise，只写R90目录。参考视频和目标图的VAE重新编码、Qwen条件重新计算，实际生成后严格核对输入RGB、两种clean VAE reference和原AVnoise与R85完全一致。新prompt改变的联合文本embedding、packed文本长度/位置和所有x0允许不同。

运行环境：.9 H3_SERVER_A，GPU3 UUID GPU-REDACTED，port8555；Comfy/core、Torch2.5.1cu121及6数值文件沿R85。normal/reserve8，fresh free>=40GiB；已登记己方GPU合计<=2，其他用户进程按既有资源门核对。新P1实际token长度和峰值待测。

root_run_native.py 是唯一计划启动入口。先验证R85原service16003/start2634847475的最后rotate forced成功、/proc与CUDA均释放且清理收据吻合；随后建立本次精确owner，peer登记完成才GO。控制器单任务finalize=True，结束后精确释放自身服务；失败独立保存原错并执行exact-owner清理。HTTP只读暂时不可用记录UNKNOWN，原14400秒job和18000秒service期限继续；提交POST不自动重试。

GPU启动由root负责。当前交付包含CPU准备、被动部署、实际远端CPU测试；未进行新推理。必要输出留远端，Mac只接收视频/JSON。
