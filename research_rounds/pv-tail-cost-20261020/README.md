# 全量损耗归因与原基座冻结

2026-10-20。状态：本阶段完成，机制修订0次，账户运行0次。冻结原“事件确认＋结构存续”作为未晋升研究基座。右侧持有中的利润回吐属于正常代价，不是本轮待优化目标。

- [正式报告](../../docs/RESEARCH_TAIL_COST_2026_10_20.md)：结果、判断、失败和停止边界。
- [冻结记录](freeze.json)：原算法、简单交易映射、无修改决定、证据哈希。
- [全量归因](attribution/review.md)：601周期、1,417订单、28,823资产日，普通/尾部/开放权益核对。
- [机械审查](validation/mechanism-audit.md)：27序列、871退出、585闭合关联及混合周期口径。
- [原15窗口独立复盘](reviews/independent-visual.md)、[9张完整历史图复盘](reviews/root-campaign-review.md)。
- [完整行情图片索引](figures/campaign-index.json)：保存收盘/量、原信号及旧交易，非新回测。
- [案例去重清单](inputs/case-catalog.json)：15与18窗口重叠，合计18而非33；通信代理只留历史观察证据。
- [实现一致性](validation/baseline-identity.json)：原代码字节一致，27条45,534行原轨迹复现；不证明经济有效。

主损耗是未形成明显有利位移时初始结构失败，并经多次尝试累积。它不支持现在放宽保护点、统一加速重入或新增亏后冷却。仍须保留正常回吐和重新参与机会；冻结不代表达成账户目标。

## 复现边界

默认读结果，不重复运行。代码仅有读取旧数据、归因与画图；没有账户引擎调用。全部历史已经研究过。

需要单独复现归因时，使用原仓库可用Python，输出必须指定新目录：

```sh
PYTHONDONTWRITEBYTECODE=1 TradingAlarm/research/.venv/bin/python research_rounds/pv-tail-cost-20261020/code/attribute_saved.py --output research_rounds/pv-tail-cost-attribution-reproduction-new
```

`attribute_saved.py`已完成目录拒绝覆盖；冻结前增加的保护没有改变计算，执行时与冻结时代码哈希同时保留。`mechanical_audit.py`只向stdout返回诊断，不生成新交易。`verify_baseline.py`和`draw_campaigns.py`拒绝覆盖既有验证/图片，不能直接当成自动重跑队列。补充30%路径描述可用`ordinary_excursions.py --output 新目录`重现，仍不是可成交利润。

实际使用Python3.13.7及已装pandas/numpy/matplotlib，依赖版本见一致性记录。原仓库虚拟环境可能仍是旧机器链接；本次使用审阅工作区的`TradingAlarm/research/.venv/bin/python`，没有安装新包或补数。

## 已记录的纠错

归因初次将log保护点当价格，检查异常后修正为指数转换，最终输出为修正后结果；详见归因报告。不同floor定义及多次成交导致的计数差异已逐笔厘清。主agent一度把回吐概括为“仍是问题”，按用户补充更正为正常代价，未因该观察改变算法。旧市场、模型和账户证据均未覆盖。
