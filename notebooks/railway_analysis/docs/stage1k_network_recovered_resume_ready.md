# 17:10网络诊断已通过；原6组恢复版待用户执行

用户截图及保存JSON：`data/diagnostics/network_check_20261113_171026_410500/network_diagnostic.json`。
同pda312解释器，实际代理为空，DNS/TCP/TLS均通过，GET_kyfw HTTP200（1.89秒），GET_www HTTP302。用户明确浏览器能正常打开。
仅说明诊断时网络可达，不能确定两次此前超时原因，也不保证后续请求成功。

辅助模块stage1k_manual_retry.py新增显式marker参数和collect_recovered/analyze_recovered入口；不作全局猴子补丁。
原始两个失败目录及其代码快照、阻断文件、旧marker不变。当前辅助模块新增参数版本与旧失败的归档版本区分保存。
新恢复marker：evidence/stage1k_recovered_current_job.json，助手未创建。新数据目录user_stage1k_recovered_*。
恢复入口先核验两个失败均初始化且0列车检查点、诊断在第二次失败后且近1小时HTTP200、原48小时deadline未到。
每请求30/45秒等待、3秒间隔、证书验证、固定解析器不变，无自动重试，保留诊断路径哈希与失败引用。

新TXT“第一阶段K_网络恢复后继续6组_核心28至29.txt”：仅新版28→29，无需重跑27或诊断。
同6组查询，不全面续采119，不预言992/992。结果合并使用恢复marker，避免读旧失败目录。
8项离线检查通过，含拒绝HTTP403不授权恢复、未知marker拒绝、超时/HTTP拒绝不自动重试；TXT语法及分支选择检查通过。
助手本轮未联网、未代用户执行恢复采集。

待用户回传新版28/29；若32完整再集中处理澳门接驳/台北惩罚和地理节点资料。报告简写采集排障，R助手使用skill，DOCX仍待确认。
