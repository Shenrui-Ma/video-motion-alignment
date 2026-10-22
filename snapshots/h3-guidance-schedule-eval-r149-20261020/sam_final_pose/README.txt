R149 Sam 成片后手臂时差测量

固定设置来自 PLAN.json：
arm_direction；参考区间 50–65、69–81、80–92、99–111；
关键点置信度下限 0.3 / 0.5；最大时移 24 帧；全141帧24fps，无裁剪。
主展示使用50–65与0.3，其余结果保留在测量说明。

源、普通编辑、原7–15步引导的三份pose原样复用，路径与SHA在PLAN.json。
新四方案各只提取一次最终成片pose。原始缺测保留，未获可靠时差写null。
此项为成片后的CPU评测，独立计时，不计入实际采样时间。

每个新方案先完成 collect_job.py / ingest.py，再执行（将late替换为所需方案）：
  python3 sam_final_pose/prepare_request.py --schedule late

将生成的REQUEST.json、extract_final_cpu.py和已核SHA的actual/.../video.mp4，
通过现有SSH仅上传到REQUEST.json指定的R149远端output_dir。
远端CPU入口见RUN_AFTER_UPLOAD.txt；直接复用R148代码/现存权重。
入口在执行前校验脚本、两个权重、两个实现文件及视频SHA；
CUDA_VISIBLE_DEVICES为空、CPUExecutionProvider、4CPU线程，禁止安装和下载。
只读取最终MP4，不访问生成进程或去噪中间tensor。

完成后只回传EXTRACTION.json与video.pose.json并核验receipt内pose SHA，然后：
  /Users/researcher/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
    sam_final_pose/summarize.py --schedule late --pose sam_final_pose/late/video.pose.json

RESULT.json沿用原timing_metrics.py；需由REVIEW.json引用其SHA后进入展示。
当前early已完成：总CPU提取102.87秒、141帧，全部人物选取明确，无GPU。
其余方案必须等各自实际视频通过摄取后再执行，不循环等待或自行启动生成。
