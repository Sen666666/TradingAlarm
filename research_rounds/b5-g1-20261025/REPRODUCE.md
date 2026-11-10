# 复现边界

本轮来源全在仓库，无下载或认证。使用TradingAlarm/research/.venv/bin/python，运行时设置PYTHONDONTWRITEBYTECODE=1、MPLCONFIGDIR=/private/tmp/b5-g1-mpl、XDG_CACHE_HOME=/private/tmp/b5-g1-cache。

不要直接重跑：所有入口以本轮目录为常量，输出已存在会拒绝覆盖。重放先在独立研究副本恢复freeze.json代码/输入身份，改为新输出目录并保存路径差异；不是用当前其他同名模块替换冻结来源。

原运行顺序：

1. code/replay.py，核对原B5/E0和七旧来源，输出原量价/B5图。
2. 记录RAW_REVIEW.md；code/prepare_grade.py；code/checks_g1.py；实看全部主/连续图；PRE_ACCOUNT_REVIEW.md。
3. code/run_accounts.py freeze；code/run_accounts.py run。冻结243文件，216账户只运行一次成功经济矩阵，没有按结果改模型。
4. code/audit_accounts.py首次因CSV文本dtype比较失败；原冻结审计器保留。实际成功核验使用code-audit-v2/audit_accounts.py，修复仅为声明schema序列化，仍exact比较；不重跑经济账户。
5. code/analyze_g1.py、code/report_g1.py是结果后报告算术，不能用其后验关联重定阈值。

恢复验证：原交易引擎来自temperature-regime-comparison-20261025/code/engine.py；B5四核心与B4核心均冻结哈希加载，未修改。old-identity-before.json包括原算法登记、B4/B5完整结果和旧切换研究/账户，完成时再次全量比对。

初始两个适配失败在technical-attempts保留：旧freeze路径相对基准误读（账户前、尚无新模型输出）；inactive floor为None和旧NaN的比较（账户前，评分/政策未改）。第三个审计失败在所有账户完成后发生，无经济结果修改。

本轮报告为自包含HTML，无远程脚本。可离线打开report/index.html；本地服务只监听127.0.0.1:8789。UI已核对场景/成本/交易筛选，截图和记录在report/browser-qa.*。
