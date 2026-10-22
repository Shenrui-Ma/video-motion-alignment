# H3 参考背景泄漏：初始实验

2026-10-08：六次推理完成，使用 `.9` 的单张 A100 80GB，累计工作流执行 24935.145 秒。没有在 `.41` 启动推理。两个 ComfyUI 服务及本地保活进程均已停止；GPU 0 恢复到运行前的 4 MiB。

完整结论见 `REPORT.txt`。现象在独立生成和固定历史续生成中都复现；自动中和背景的两个配对都消除了所观察到的舞台侵入。修正参考覆盖与发布区间后，原图仍然泄漏。当前证据支持一个真实的条件干扰案例及强预处理基线，不支持新机制、跨样例泛化或论文新颖性声明。

## 结果入口

- `analysis/continuation_original_vs_neutral.mp4`：原图与中性背景的固定历史配对，完整 158 帧。
- `analysis/part1b_original_vs_neutral.mp4`：独立生成配对，完整 175 帧。
- `analysis/aligned_source_vs_output.mp4`：预期源时间区间与修正工作流输出，完整 170 帧，不做时间缩放。
- `analysis/experiment_ledger.json`：六次真实执行、种子对应任务、哈希、帧数及用时；明确列出未执行的准备项。
- `analysis/completed_five_integrity_review.json` 与 `analysis/final_run_integrity_review.json`：独立配置、内嵌工作流、媒体和 latent 一致性核验。
- `analysis/aligned_source_landmarks_preregistered.json`：在查看最终输出之前固定的五个源动作事件。
- `analysis/related_work_audit.json` 与 `analysis/long_video_related_work_audit.json`：有界的一手论文核查，不是“没有其他论文”的证明。
- `processes/verified_stop_39809.json`、`verified_stop_17996.json`、`verified_stop_local_caffeinate.json`：进程、端口和显存释放证据。
- `analysis/final_checks.json`、`logs/unit_tests_16.log`：运行与脚本验证。

## 复现材料与范围

`configs/` 保存配置和输入、模型、运行环境清单；`logs/` 保存任务记录与 ComfyUI history；`outputs/` 保存未经比较视频重编码的原始生成结果及续接 latent。`analysis/` 保存全帧缩略图、描述性颜色代理与独立 AI 视觉判读。帧数统计不是独立样本数量，动作边界也不是人工标注基准。

脚本位于 `scripts/`，对应测试位于 `tests/`。`extensions/H3ReferenceBranchSwap/` 只做过 CPU 单元测试，未启用、未进行机制实验。部分额外配置与参考图只是准备材料；不能把每个配置文件都当作一次已执行实验。

本轮没有修改共享 ComfyUI 核心或模型，没有安装新依赖。结论限于当前量化 H3/Qwen、ComfyUI 和续接插件组合；没有验证相同设置在 48GB 卡上运行，也没有完成新的多段长链实验。

远程原始运行目录：`/data5/researcher/h3_runs/background_leakage_pilot_20261007`。现有同名任务记录用于防止误重复提交；后续实验应建立新的运行目录、任务名和所有权记录，先检查 GPU 占用。`.41` 仍须遵守最多一个视频推理进程的限制。
