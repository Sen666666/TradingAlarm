# 三组更码与成交量单位适配原型

2026-10-22 离线生成。经济准入 **false**；网络 0 次、账户 0 次、趋势机制改动 0 次。只覆盖已公告核实的 000022→001872、000043→001914、300114→302132 三组，不能外推为全池历史主表、行业、股本、公司行为或可成交性认证。

代码：[identity_adapter.py](../../code/identity_adapter.py)。输入证据：[三组身份复核](../revalidation-20261022/identity-review.md)。全部来源先对照上一份证据哈希，读完再复验未变；不修改源文件、不联网、不覆盖已有结果目录。

## 结果

- 输入 20,328 条：原价库三条继承历史和两份 BaoStock 旧代码文件。
- 输出 16,109 个连续证券/交易日唯一记录：15,723 个有效趋势观察，另 386 个零量停牌观察保留但不进入趋势时钟。
- 同一证券同一天的重叠记录去重 4,217 条，全部 OHLC 按 Decimal 精确比较一致；成交量先按已验证单位转换再比较一致。
- 2 条旧代码实施日的空价/空量终止哨兵移至独立文件，不能解释为新证券停牌、退出损失或现金兑付。
- 29 项核验全部通过，包括三组生效日前后、连续内部 ID、真实重叠去重、价格/量冲突拒绝、来源内重复拒绝、停牌不计趋势观察、未知来源单位拒绝及三个截断日期的前缀一致性。

2018-12-20 记录展示代码为旧码 000022，来源键仍为 001872；12-21/24/25 停牌原记录保留且无有效观察；12-26 展示/执行身份切换到 001872。代码改名不会创建价格、交易日、买卖事件或复权调整；后续消费者仍须自行验证真实交易状态与资格。

## 输出契约

`observations.parquet` 保留内部 `security_id`、当日 `symbol`、原 `source_symbol`、原价 OHLC、`volume_shares`、有效趋势观察标志、全部来源和 SHA256、源单位及倍率、未知字段和经济准入 false。内部 ID 只是这三条法律/持仓连续性的研究键，不是官方发行人注册号。

价格及股数以十进制字符串保存，防止适配层添加浮点误差；消费者需明确解析。Tushare 原库三例的量乘以 100，BaoStock 原量保持不变；规则拒绝其他证券/来源组合。仅比较原价，不应用复权，不把更码 1:1 等同公司总股本不变。

`source_symbol` 指采用的原始记录；`provenance` 保存同日所有核验来源。完整记录优先，通常采用原库原始行，不拼凑不同源字段。任何非空价格或统一单位后的量冲突都拒绝输出，不静默选择更好看的源。

`boundary-observations.csv` 展示实施日前后 7 个自然日中的真实记录；无观测的日期不补行。`terminal-symbol-sentinels.json` 保留两条被隔离的旧码空行；`input-manifest.json` 和 `protocol.json` 保存来源身份、代码哈希与运行参数。

## 复现

使用项目已有 Python 环境运行以下命令，并给出尚不存在的新输出目录：

```sh
/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python \
  /Users/bytedance/Documents/ChatGPT/money/research_rounds/sector-stock-20261021/code/identity_adapter.py \
  --source-repo /Users/bytedance/repos/TradingAlarm/TradingAlarm \
  --source-parquet /Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet \
  --identity-evidence /Users/bytedance/Documents/ChatGPT/money/research_rounds/sector-stock-20261021/coverage/revalidation-20261022 \
  --out /新的尚不存在目录
```

源价格库当期覆盖截至 2026-05-15；两条 6,000 行继承历史不是自上市以来完整证明。全部输出仍缺历史公司市值、历史行业、精确公告可知时间、权益完整性及执行/结算认证。其用途仅是为下一阶段适配消除已证实的重复证券和百倍量跳风险，不能直接启动经济账户。
