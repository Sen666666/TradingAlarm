# 高参与下跌跨日收复：冻结的算法阶段成果

**准入下一阶段有限简单策略经济检验。不是交易策略盈利晋升；本轮账户0次。** 最终候选`results/v0-input-fixed`，一个候选、机制修订0次。主报告：`docs/RESEARCH_PARTICIPATION_RESPONSE_2026_10_20.md`。长期共识不变，禁止为单个反例继续改此候选。

建议阅读：

1. `protocol.md`与`reviews/admission-before-results.md`：事前假说及六门。
2. `reviews/algorithm-contract.md`：原量价事件＋结构存续、新跨日量记忆、独立排名的语义。
3. `reviews/root-market-prior.md`、`market-prior.md`、`root-model-v0.md`、`model-independent-v0.md`及`event-chain-review.md`：原量价和18窗/全部26恢复的主动判断。
4. `reviews/numeric-input-amendment.md`、`source-precision-independent.md`与`validation/source-precision-review.md`：失败、代数修复及有限数值边界。
5. `reviews/event-chain-final-addendum.md`：旧图为何可沿用于最终事件链，哪些上游字段真的改变，不能声称全部新图重看。
6. `reviews/admission-final.md`：独立六门裁决。
7. `strategy-contract.md`：主研究者采用的下一阶段简单映射；执行器尚须适配，本轮不运行。
8. `freeze.json`、`evidence-manifest.json`：最终身份；正式仓库交付收据另见`docs/reviews/2026-10-20-participation-response-delivery/receipt.json`。

最终事实：14条/27,655观察、226记忆（115否决、84原通道消费、26独立恢复、1未决）。26恢复增加91资格观察，19随后与基座汇合；6短失败，9短期重试。18固定窗只有C2改变3观察，其余17同基座；范围窄、晚启动和普通试错均保留，不宣称收益或胜率已验证。

数值验证分开记：准备98/98，候选761/761，上游103/103；排名10组合成+98真实通过；未改参与机制的28组合成通过（内含114状态和76账本前缀）。不相加成独立市场样本数。原candidate-attempt2的10失败、numeric旧失败及前一轮11失败保留。

输入与结果身份：

- `inputs/`原14条CSV与上轮字节一致，不改来源/企业行为，不补数。
- `prepared/source-precision-v1`是独立精度修复视图，9条因子只在企业行为日递推；3A股保留THS信号价，2指数无复权；全部量值不变。最大价格相对变化约5.94e-15。
- `results/v0`首次候选信号保存，数值失败不能覆盖。
- `results/v0-input-fixed`最终输入/同一机制结果，各run-freeze记录代码、源/准备manifest与修订协议。
- 58份保存CSV中55份全字段合同相同；3上游共5行极值日期/confirmation真改变，`validation/input-fixed-result-comparison.json`的false保留。所有状态、事件/账本/排名/18窗离散输出相同，图检沿用有独立附录。

复现优先读保存结果，不自动重跑。只需重新算信号时，使用已配Python，令`--output`为本轮results尚不存在的直接子目录：

```sh
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/private/tmp/pv-mpl TradingAlarm/research/.venv/bin/python research_rounds/pv-participation-response-20261020/code/run_study.py --output research_rounds/pv-participation-response-20261020/results/reproduction-new
```

若正式仓库venv仍指向旧机器，使用已验证的工作目录venv路径，不重新安装或调用旧账户。数据准备器拒绝覆盖；loader固定读取本轮prepared并核对源、准备器和输入hash。当前派生输入完整，不需要重复准备或联网。

全部相关历史已见，所有后续链观察明确是事后复盘，不是事件当天输入。新算法仅声称有因果量价机制并值得经济检验；不保证主导趋势每次正确、不提前锁盈，不冒充“趋势动物”专有算法或已获账户肥尾。
