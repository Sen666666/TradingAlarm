# 实现复核与范围
本轮只读复核未发现已冻结实现中的实质后验、时钟、标签或 AUC 数学错误，没有运行账户、重拟合或据新结果筛选模型。

- 部分折叠 Gibbs 顺序正确：来源分配后，积分掉子端点更新 pi0，再重新抽子端点。Gamma 比率与 logit Jacobian 正确，子端点使用冻结的 Dirichlet(20*pi0)。
- 月初前 entry_t<=cut-120，对应 entry_t+119 为含出生当日的第120个共同交易观察。晚于 H 的退出仍为 U。1814行 signal/entry 日期与 MARKET_CLOCK 索引一致，entry_t>=t。
- AUC包括并列半分与正确影响函数；配对差使用共享样本。20共同交易观察块、股票及交叉聚类后取最大单向/双向方差，与冻结说明一致。
- 1814项新特征前缀核验只证明截断既存 facts/CP 缓存后新特征不变，不能认证上游缓存生成或历史版本PIT。未来污染核验只改不可用/晚于H的PnL，未改closed/close_t；标签门控经代码复核，不能宣传为覆盖所有上游污染形式。
- 结构窗口精确为 a-21 到 a，共22个价格点，包含锚日。不要把简称“锚前21观察”误写成21点且不含锚日。
- 聚类区间条件于已拟合模型，未涵盖重拟合不确定性；全部已见历史仅为研发诊断。

复核文件：FREEZE.json、NUMERICAL_AMENDMENT_BEFORE_FIT.json、prepare_features.py、run_inference.py、evaluate_once.py，以及FEATURE_AUDIT_SUMMARY.json。
