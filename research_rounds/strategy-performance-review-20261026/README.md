# 已有趋势算法和交易策略综合复核

日期：2026-10-26。只聚合已有结果；新增经济账户0、下载0、参数修改0。

- [综合评价与主要结果](ASSESSMENT.md)
- [静态结果表](index.html)
- [数据范围与执行口径](tables/dataset-registry.csv)
- [四固定股票池全部政策与情景](tables/fixed-stock-pools-all-scenarios.csv)
- [单资产全部政策、窗口与情景](tables/single-assets-all-policies.csv)
- [全市场资金策略，保留新旧执行身份](tables/broad-universe-all-scenarios.csv)
- [早期63名称](tables/legacy-63-model-summary.csv)
- [早期378去重case](tables/legacy-378-deduplicated-cases.csv)
- [源哈希及去重计数](REVIEW_RECEIPT.json)

重复I/E0控制在核对收益与回撤一致后去重。不同数据池、时期及执行引擎不能拼成同一排行榜；案例均值不是可交易组合结果。没有重新独立核账全部旧账户，沿用各源研究的数据及成交限制。全部历史均为开发资料，不因本次汇总转为样本外。

`code/review.py`是一次性聚合脚本，已存在tables时主动拒绝覆盖；本轮没有运行任何策略引擎。
