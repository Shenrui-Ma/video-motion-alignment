R57: IVEBench 五条固定 P1 prompt 的普通编辑对照。
P0 使用已完成 R54 的真实归档；P1 仅改变节点5 prompt。
CPU 预备，尚未部署或运行 GPU。原视频在外部 input_bindings 记录中，Mac 未重复复制。
顺序调度：R55 完成并释放后由 root 审查 R57 新 prompt 容量/运行前门，再启动。
使用与 R54 相同启动参数，无 reserve-vram 新参数。
逐项解释见 COMPARABILITY.txt，真实运行后 verify_batch.py 检查初始 AV noise 与参考视觉实体相同。
工程 revision2：启动前实际 free≥48401MiB；允许同卡其他用户；PID退出/查询瞬态最多600秒重查；非关键统计不可用会记录null。v1完整证据保留在audit/revision1及原bundle。
