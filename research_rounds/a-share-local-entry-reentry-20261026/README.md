# A股局部入场、局部失效与再次入场：LER-01

本轮已结项。先12原始量价图、后一个候选与12轨迹图检，再28有限资金路径（4旧控制＋24新增经济），最后8实际结构图复查。低胜率可以盈利，但本候选没有稳定优于原I，也未普遍实现大赢家独立覆盖全部亏损；不晋升默认。

- [完整结论](CONCLUSION.md)：基础/压力结果、严格尾部覆盖、同结构全部试错、裁决。
- [图表报告](report/index.html)：中文摘要、净值、原始图和实际成交图。
- [事前协议](PROTOCOL.md)、[冻结规则](RULES.md)、[实际执行合同](EXECUTION_CONTRACT.md)。
- [原始量价阅读](RAW_REVIEW.md)、[经济前候选图检](MODEL_REVIEW.md)、[经济后实际成交复查](TRADE_REVIEW.md)。

## 有效版本

|阶段|有效证据|
|---|---|
|原始图与事前选样|`raw/`、`raw-freeze.json`|
|新局部收据与模型图|`signals-v1/`、`model-charts-v1/`、`model-freeze-v1.json`|
|公式与物理前缀|`technical/model-receipt.json`|
|短技术及独立核账|`technical/short-v2/`、`technical/short-audit-v1/`|
|经济前冻结|`economic-admission.json`、`account-freeze.json`|
|唯一资金运行|`accounts/`、`economic-v1.log`|
|独立核账与逐笔/结构归集|`analysis-v1/`|
|旧I恒等|`old-I-identity.json`|
|真实截断资金前缀|`technical/prefix-v2/`、`technical/prefix-receipt-v1.json`|
|经济后图检与描述|`review-v1/`、`report/`|
|最终完整性清单|`complete.json`、`integrity.json`|

分析入口为`analysis-v1/summary.csv`、`campaigns.csv`、`structure-clusters.csv`；39,200日账核验见`analysis-v1/accounting.json`。`review-v1/risk-coverage.csv`区分“尾部独立覆盖全部亏损”与“尾部覆盖普通净损耗”，交易费用已经纳入各笔损益，不能重复扣费。`old-I-top-contribution-comparison.csv`仅为事后原I主要贡献股的说明，不用于改名单。

## 失败保留与复现

1. 首次绘图因nullable Int64被当条件导致`.where`异常：`code-model-v0/`、`signals/`、`model-charts/`及`technical-model-attempt0.json`保留。修绘图布尔掩码，公式不变。
2. 首次短执行在E0已失效、支持不可用时输出诊断NaN，严格JSON序列化失败：`code-execution-v1/`、`technical/short-v1/`、`technical-execution-attempt1.json`保留。诊断保护字段回退到已绑定局部位，既有E0退出决定不改；在经济前修复。
3. 首次真实前缀有股票截至截断日尚未上市，空表`anchor_day`元数据由字符串变浮点导致严格比较失败：`prefix-v1.log`、`technical-prefix-attempt1.json`保留。另存`audit-code/prefix_run_v2.py`只规范空表元数据，其余数值/非空检查不变，金融代码未改；有效结果精确匹配10,178日账/决策。

经济运行一次，结果后经济规则修订0、经济重跑0。短技术和前缀重建不算新增经济账户。所有经济/图表脚本的输出目录默认排他创建；不要原地重跑覆盖。需要复现时，复制整个本轮到另一个新目录并明确重新冻结所有路径，保持本轮证据只读。代码入口分别为`code/raw_review.py`、`prepare_model.py`、`run_local.py`及`audit-code/`；事后描述代码为`post/`。完整性脚本只读核验输入和旧证据，再写本轮清单。

当前固定股票池、名册/行业/市值快照、已见开发历史及日线成交代理限制继续保留。未下载新行情，未发布远端，无实盘。上一轮I-RB1风险仓位候选未在本轮实现。本轮不自动搜索新阈值、换股票池、改排序/仓位或续跑全市场账户。
