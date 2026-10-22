# 书本终态恢复解码

已保存真正 Euler sigma=0 终态，20次 forward / 1000次 attention / 450次路由完整。仅使用 `sampler_final.pt`；step019 是更新前预测，和终态有细小浮点差异。

恢复沿原图 node3/4 的 VAELoader，node11 VAEDecode，node12 原 vae_decode_audio，node13 CreateVideo，以及 node14 原生 save_to 调用。音频已有 process_latent_out 归一化，直接交给 VAE；不重复除4。全107帧、1312×736、24fps、8bit sRGB、MP4/H264/CRF16，保留音频。评测有效域仍106帧；文件不裁帧。

`BINDING.json`固定旧图、终态、capture manifest、router、旧service/attempt、0字节MP4/历史文件及原生核心代码SHA。两VAE复用原封存checkpoint hash，并锁实际路径/stat；本次未再通读5.2GB/0.6GB权重。原attempt2无COMPLETE，新的成功只写独立RECOVERY_GATE。

CPU：实际终态tensor SHA/finite/shape通过，真实Comfy导入通过，2帧16×16带音频的原生封装烟测通过，CUDA未初始化、未加载VAE权重。6个本地和6个目标CPU测试通过。

启动命令见 HANDOFF.json。Root待GPU1或2释放且RAM准入后执行；脚本要求目标GPU健康、free≥40000MiB、used≤64MiB、util=0、无compute owner。默认attempt1新目录；失败保留新目录，后续尝试改新名称。

成功文件：`attempt1/RECOVERY_GATE.json`，绑定DECODE_RESULT/RELEASE文件SHA、精确decoder owner（含boot_id）、新视频SHA/ffprobe属性与旧终态SHA。RELEASE只有子进程退出且其CUDA记录消失后通过。脚本最长900秒；中断只结束本次Popen直接子进程。
