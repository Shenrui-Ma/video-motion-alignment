合成可证伪候选v1；真实63项暂未授权重新评分。

PROTOCOL_FREEZE.json在实现前写入，CODE_FREEZE.json和CASE_MANIFEST.json在任何合成评分前写入。原始8个零warp输入由test_profile检查逐位一致。全部样例由确定性解析式构造，登记seed=2026101707，随机抽样次数为0。

Python:
/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python

命令（每次attempt唯一）：
  <PY> <本目录>/run_once.py tests --attempt correctness_attemptNNN
  <PY> <本目录>/run_once.py case --attempt case_NNN_attemptNNN --case-id <CASE_MANIFEST中的id>
  <PY> <本目录>/run_once.py finalize --attempt finalize_attemptNNN

runner每次获取共享Mac锁，busy退出75，最长120秒，最多4线程。每case完整RESULT及EVIDENCE分别保存，科学接受条件失败也正常提交证据。只有执行/实现异常会exit1。最终SUMMARY明确scientific_pass，不能把执行exit0理解为方法成功。

EVIDENCE保存两臂、两阈值的完整49lag×141×141 profile loss；包括未知/无支持区域的inf。另有失败位图、首要状态、最优lag、J、目标值、相位集合端点、共同mask。矩阵的[a,b]表示0-based闭区间；长度小于8和下三角不属于搜索族。RESULT保存每个已选段全部相位曲线、旋转角、raw误差和拒判计数。低信息/多峰/缺支持区间保留为UNKNOWN。

在多个阈值上检查相同49相位支持；不同confidence阈值各有自己的共同mask。代价和门都按PROTOCOL固定，保持前述0.05rad容忍度及2帧分辨率。已知旧反例属于开发诊断，新source尚未验证。

当前只实现观察器A，未改H3注意力、MLP、位置编码、采样器或执行器S。常量SO2、条件信息与DP是标准数学。代码不是新的配准理论的证据。
