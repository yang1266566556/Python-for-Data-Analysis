# 6组采集初始化超时；独立手动重试版待用户运行

原分支：`data/raw/user_stage1k_20261113_164250_874496`。
16:42:50官方首页GET，16:43:03记录ReadTimeout(read timeout=10)。没有HTTP状态或字节响应，0列车检查点，6组均not_collected。29正确跳过合并。
无法由此确定网络/服务端原因，不能称为封禁，也不是解析或数学矩阵错误。

不修改stage1_collect.py或stage1k_residual.py等已固定代码，不删除原blocked.json、不覆盖旧marker。
新增stage1k_manual_retry.py：先核验原失败仅发生在初始化、无列车检查点且旧代码和方案未变，再建立独立分支。
每请求显式连接/读取超时30/45秒，TLS验证保持，无自动重试，3秒间隔；仍用原6组、原日期、原解析器及21:28:30.987887截止。
独立marker：evidence/stage1k_manual_retry_current_job.json（助手未创建/未运行）；再次异常保留分支且不自动重发。
成功后analyze显式核验手动分支，再调用同一stage1k_matrix.evaluate验收，不错误读取原失败分支。

TXT沿用“核心28手动重试版→核心29”，无需重跑27，不给排障继续增加核心编号。
5项离线测试通过：真实失败核验、超时与TLS参数/字节哈希、ReadTimeout不自动重发、HTTP拒绝不重发、底层transport retry=0。
助手本轮网络请求0，实际联网成功与否待用户运行。TXT语法通过，用户三张截图原样归档。

报告正文只简述采集质控，失败和恢复过程不逐次堆叠。R仍助手负责，未进入降维或DOCX。
