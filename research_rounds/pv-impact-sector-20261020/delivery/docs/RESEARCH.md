# 研究路线和证据

2026-10-20第二阶段已完成量价冲击诊断、20组ETF／历史三股对照和4组费用差异压力测试，见 [RESEARCH_ROUND_2026_10_20_IMPACT_SECTOR.md](RESEARCH_ROUND_2026_10_20_IMPACT_SECTOR.md)。放量回撤效应受时间混杂，当前top2排序漏掉腾讯尾部；不新增过滤器、不晋升模型。下一动作是冻结“暂时冲击／持续价格重估”的一个新量价状态机制，先合成与实际轨迹复查，再固定账户；详细执行顺序见报告第5节。R2保持关闭，R5未启动；目标仍未实现。


2026-10-20新结果：[量价分段首轮报告](RESEARCH_ROUND_2026_10_20.md)。24组固定账户及两轮主观复查完成；本候选不晋升。`trend_cash_book`必要修复与执行政策影响已分开验证，下一轮回到量价机制。

> 当前方向必须遵守 [RESEARCH_CONSENSUS.md](RESEARCH_CONSENSUS.md)，下一步执行 [NEXT_RESEARCH_TASKS.md](NEXT_RESEARCH_TASKS.md)。下文保留历史研究和证据索引，不是模型自动晋升规则。新增审查见 [2026-10-19复盘](reviews/2026-10-19-tradingalarm/REVIEW_AND_PLAN.md)。

完整脚本、结果目录和摘要文件路径见 `catalog.json`。下述路径均相对 `TradingAlarm/research/`。结果本身优先于文字四舍五入；每组范围、成本与年份必须看 `protocol.json`。

## 研究阶段

1. 公开研究与早期基准：趋势跟踪/时间序列动量、均线、Donchian、252 日动量，ETF/港股组合与不同仓位方式。原始研究 JSON、协议和结果保留在研究根目录及 results 中；全文线索可搜索 `Moskowitz|Hurst|time.series|momentum|趋势动物`。没有证明某公开论文的历史回报可直接移植到当前 A/HK 账户。
2. 执行与会计：从单资产信号发展到多资产现金共享、真实股数/手数、公司行为、HKD/CNY、派发证券持仓。`monthly_ah_engine.py`、`campaign_claims.py`、`portfolio_data.py`；分别检查数据加载器和引擎假设，不能把一套完整会计等同于所有输入都完整。
3. 趋势拟合：几何/局部斜率、量加权成对斜率、多尺度、冲击/衰减/结构变化、预测状态等；保留所有尝试，详见 `trend-model-inventory`。过去汇总为 666 原始 case 行、378 唯一 case、63 个名字/61 个实现指纹；这不是 666 次独立样本外试验。
4. 个股与组合：A485 补数、相关性代理板块、初始等额分仓、first-cross、短期退出/减仓/恢复、随机排序与准入诊断。
5. 当前瓶颈：普通交易亏损与排序区分力不足；行业历史成员不足；2026 趋势阶段拟合需要解释而非只报告净值。

## 历史对照信号与引擎入口

`pairwise_trend_strength.py`：21 个对数价格点，两两斜率的加权中位数；时间权重 exp2(age/5)，量权重 clip(sqrt(volume/median), 0.25, 4)，以 21 日对数收益 RMS 归一化；强度形如 `5 + 5*tanh(sqrt(5)*slope/RMS)`。确切边界/缺失值以源代码为准。

`geometric_strength.strength_exposure`：当前研究基准上穿 5+5*tanh(1)≈8.80797 入场，≤5 退出，缺失状态保留。该阈值是基准，不是用户指定最优参数。`trend_slot_selection.py` 管理持仓/待执行单的槽位与分组门槛。

`trend_workbench.py`：固定协议，ETF17/HK7、base/cost2/delay1；`workbench_episode_report.py` 做包括 claims 的交易周期归因。`broad_shared_slot_experiment.py --first-cross` 是 A485 基准入口；不少结果目录预存协议，不能只换 `--output` 而不提供协议。

## 已完成的重要检验

| 结果目录 | 问题 / 结论 |
|---|---|
| `broad-shared-first-cross` | 初次过阈值 + 分组准入共享账户；+11.086% / 回撤16.229%，未达目标 |
| `broad-shared-short-half`、`broad-shared-short-exit` 等 | 短期退出、减仓、恢复、graded/linear 版本均未形成稳定优势，不能只选最优一种 |
| `strength-volume-clock` | ETF全期4.155→5.044%、HK5.058→7.294%，但HK2026更差；未采用 |
| `volume-clock-phase-audit` | 24资产42732有效观测零阈值方向完全一致；正分母改尺度不能修复方向退出滞后 |
| `trend-coverage-audit` | 某些年份下行捕获高于上行捕获；不能只展示牛市 |
| `trend-tail-distribution-audit` | 高强度对均值与尾部概率的排序不一致，跨样本不稳定 |
| `trend-entry-horizon-attribution` | 原入场后的持仓/空仓对数收益拆分，含重入；不是可执行收益报告 |
| `matched-trend-exit-audit` | 同一入场比较多尺度退出；5组年份更好、5组更差，2026 ETF/HK更差 |
| `forecast-mechanism-review` | 重算250011预测；90单元MSE均差于不变预测，不能仅凭此作交易效用结论 |
| `sector-admission-audit` | 3392机会，2176门槛关闭、81分组缺失、983槽位/排序拒绝、152选中；与实际买单对齐 |
| `sector-admission-outcomes` | 同日同组入选对照；2026样本少、优势不稳定 |
| `sector-ranking-random-controls` | 20固定随机种子；12/20收益高于趋势排序。保留全体，不挑最佳随机模型 |
| `ordinary-loss-attribution` | 21账户3239交易，普通交易费用加回仍全部亏损，不能归咎于手续费 |
| `sector-gate-opportunity-audit` | 同日近强度匹配，门槛效果随年变化；匹配不是因果证明 |
| `sector-membership-source-audit` | TuShare/恒生官方资料线索；未取得合格历史成员表 |
| `ths-sector-cache-audit` | stocklink与代码名称关系、静态方法元数据；不是历史成分数据 |
| `ths-industry-snapshot` | 当前A/HK行业成员缓存已恢复；禁止回填历史 |

部分实际目录可能带版本后缀；完整目录及 review/validation 文件由 catalog.json 精确列出。

## 回测可信度边界

A485 用复权价格、极小分数单位、合成大成交量模拟资格允许日的成交，缺少全量历史真实交易规则。485 是500候选中通过检验者，15排除，详见 `data/ths-refresh-20261018/validated-input-balanced-second500.json`。当前存续样本不能消除退市偏差。

板块代理来自过去126日与9个行业ETF相关性，每日因果更新，但不是官方行业。9槽/每组3槽是数量准入限制，不是每组实际市值上限。已有赢家不会因每天等权而被强制卖出。

ETF/HK 引擎较完整，不代表每一种分红税、费用、流动性和可借券条件都被覆盖。这里没有实盘交易回报证据。所有结果是研究回测或诊断。
