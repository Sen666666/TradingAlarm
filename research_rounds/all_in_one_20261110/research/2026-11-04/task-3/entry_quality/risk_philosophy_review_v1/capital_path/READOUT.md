小CORE与全户大回撤：原No60资金路径，只读复盘

结论：小CORE只限制这一笔早期仓位，并不封住后续mobile、全组合持仓市值或长期累积损失。原No60三年期末637989.61（−36.20%），最大DD38.09%；2022年末704487.85（−29.55%）。这两个结果不与单笔CORE很小矛盾。以下不新增回测、账户或参数。

代码事实（冻结代码与原RUN_METADATA SHA核同）
1. CORE原all-in保护线名义预算为NAV×0.0025，且整手/名义cap会进一步缩小实际买款；不是账户终身只允许亏0.25%。[study.py](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:42)。
2. 原新mobile按当前NAV×2% gross与单股余量规划，不按首笔CORE实际本金同比例授权；2%是买款目标，不是2%风险预算。[joint_v3.py](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:259)。
3. 此No60实际启用NoAccountBudget；其有效route/request保留现金、probe/confirmed池、行业资本/风险和单股约束，但没有全户3%名义风险admission检查。confirmed池60%不是全户20%/30%回撤上限。[adapter.py](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/adapter.py:9)、[route](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/route_without_account_check.py:13)、[request](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py:240)。
4. shared_loss_budget虽记录20000，exhausted_policy却是record_only，累计亏损记录并不自动拒绝所有新尝试；ACT另按收盘NAV/episode峰值工作，收盘触发后才提出退出，实际执行在后续OPEN。[joint_v3.py](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:16)、[planning](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:221)。

账户事实：小试单之后可以出现大得多的连续出资
盈新发展000620的2022Jan11-Feb8完整campaign：CORE实买306.18，随后5个mobile实买款合计92,622.48，整个campaign净-17,850.15。这是买款周转，不是同一时刻投资92622元；原实际并发mark峰61,614.00、basis峰55,124.42另保留。小CORE没有按比例约束后来总资金，也没有证明后续趋势正确。

长期资金桥（原互斥阶段；三组连续路径，非新回测）：
阶段 | 期初NAV→期末NAV | 阶段财富 | 新买款周转 | 前收盘平均仓位 | old/first/add/reentry财富
P01_2022H1 | 1,000,000.00→818,776.54 | -181,223.46 | 5,580,540.13 | 53.93% | 0.00/-126,958.00/-41,499.23/-12,766.23
P02_2022JulNov | 818,776.54→799,294.49 | -19,482.05 | 3,322,552.31 | 83.07% | -9,851.35/-20,257.52/22,328.38/-11,701.56
P03_Dec2022 | 799,294.49→704,487.85 | -94,806.65 | 1,158,992.09 | 87.24% | -53,407.03/-14,327.96/-13,870.13/-13,201.52
P04_2023JanApr | 704,487.85→877,747.56 | 173,259.71 | 2,688,641.64 | 89.65% | 3,686.62/55,566.28/80,204.16/33,802.65
P05_2023MayJul | 877,747.56→745,426.96 | -132,320.60 | 2,676,965.48 | 79.00% | -29,563.86/-19,683.46/-39,934.70/-43,138.58
P06_2023Aug_2024Jan | 745,426.96→745,426.96 | 0.00 | 0.00 | 0.00% | 0.00/0.00/0.00/0.00
P07_2024FebMay | 745,426.96→734,782.26 | -10,644.70 | 873,604.30 | 20.85% | 0.00/-4,061.37/-5,263.67/-1,319.65
P08_2024Jun_Sep23 | 734,782.26→625,724.23 | -109,058.02 | 2,260,017.71 | 74.67% | -24,809.51/-36,019.41/-13,595.97/-34,633.13
P09_2024Sep24_Oct8 | 625,724.23→805,043.93 | 179,319.69 | 121,446.43 | 83.11% | 145,291.12/0.00/26,443.96/7,584.62
P10_after2024Oct8 | 805,043.93→637,989.61 | -167,054.32 | 2,839,637.22 | 75.78% | -54,596.72/-45,595.78/-32,488.11/-34,373.71
2022H1先亏181223.46，Jul-Nov另亏19482.05，Dec再亏94806.65，故年末约−29.55%；Dec包含旧87层−53407.03和新122层−41399.61，不只是初始CORE失败。2023Jan-Apr赚173259.71后May-Jul亏132320.60；2024Sep23→Oct8赚179319.69后至年末亏167054.32，后段同时有旧75层−54596.72及新303层−112457.60。

当时实际暴露与同时风险参考（pct_NAV字段为百分数，不是比例）：
日期 | NAV | 市值/仓位 | 股数/行业数/层数 | 已付basis至参考线%NAV | 市值至参考线%NAV | 最大股/行业市值占NAV
2022-01-04 | 1,000,000.00 | 0.00/0.00% | 0/0/0 | 0.00 | 0.00 | 0.00%/0.00%
2022-06-30 | 818,776.54 | 736,534.88/89.96% | 55/36/61 | 5.92 | 9.41 | 4.75%/10.16%
2022-11-30 | 799,294.49 | 717,749.97/89.80% | 65/32/87 | 3.09 | 6.91 | 10.85%/15.32%
2022-12-30 | 704,487.85 | 631,570.40/89.65% | 66/34/75 | 7.15 | 6.62 | 3.97%/11.24%
2023-04-28 | 877,747.56 | 790,316.69/90.04% | 66/34/82 | 2.06 | 9.25 | 15.86%/16.05%
2023-07-20 | 748,193.45 | 664,996.26/88.88% | 69/36/81 | 3.99 | 4.33 | 6.04%/11.76%
2023-07-21 | 745,426.96 | 0.00/0.00% | 0/0/0 | 0.00 | 0.00 | 0.00%/0.00%
2024-05-06 | 745,426.96 | 0.00/0.00% | 0/0/0 | 0.00 | 0.00 | 0.00%/0.00%
2024-09-23 | 625,724.23 | 422,398.40/67.51% | 43/21/58 | 3.19 | 3.87 | 5.89%/16.88%
2024-10-08 | 805,043.93 | 723,064.52/89.82% | 50/23/75 | 0.61 | 7.06 | 6.08%/21.06%
2024-12-23 | 640,851.59 | 556,373.00/86.82% | 79/44/89 | 7.07 | 5.11 | 5.18%/8.80%
2024-12-25 | 637,989.61 | 0.00/0.00% | 0/0/0 | 0.00 | 0.00 | 0.00%/0.00%
2024-12-31 | 637,989.61 | 0.00/0.00% | 0/0/0 | 0.00 | 0.00 | 0.00%/0.00%
这些已知线仅是原尺度风险参考，不保证能按线成交，也不是永久保护最初本金。每日股/行业数、实际mark及现成HHI列于CAPITAL_PATH_FACTS；类别多不证明收益独立，同行业或不同行业仍可同涨同跌，此处没有估计协方差或把65行业当65份独立风险。

ACT实际时钟，而非20%硬损失保证：
2022-04-20 15:10:00+08:00收盘暂停（NAV 785,066.18，本episode DD 21.49%），首次实际flat CLOSE 2022-04-21 15:10:00+08:00、NAV 779,819.31；恢复 2022-06-17 15:10:00+08:00。
2023-07-20 15:10:00+08:00收盘暂停（NAV 748,193.45，本episode DD 20.62%），首次实际flat CLOSE 2023-07-21 15:10:00+08:00、NAV 745,426.96；恢复 2024-05-06 15:10:00+08:00。
2024-12-23 15:10:00+08:00收盘暂停（NAV 640,851.59，本episode DD 20.40%），首次实际flat CLOSE 2024-12-25 15:10:00+08:00、NAV 637,989.61；恢复 期末未恢复。
2022Apr20的退出在Apr21已平；2023Jul20在Jul21已平；2024Dec23到Dec25才全部flat（Dec24还有原持仓余量），不能一律写触发次OPEN全平。原暂停后flat至恢复NAV不变；市场机会格虽仍记录，但去掉ACT后究竟哪些原信号可获资未识别，不造潜在无买账户或补计市场上涨。

推断（不冒充已识别因果份额）
单笔名义风险控制的是一次当前出资/当前参考线。持仓陆续止损并释放资源后，系统可以再给其他原合法CP出资；重复小亏可以累积，盈利后的市值回吐也会产生大阶段财富下降。高至约90%的实际股票暴露使全户财富对共同下跌敏感；分行业上限与记录性共享亏损计数不能推出长期DD上限。
ACT是事后收盘episode回撤制动器，存在观察/下单/可售执行时差，并在恢复后开始新的episode峰值；它没有把最初100万元的累计损失永久封在20%。这解释了“有小CORE、仍可全户20—30%甚至38%DD”的允许路径，不证明每笔亏损可提前识别或某条替代规则有效。

核查入口：原[阶段桥](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/STAGE_WEALTH_CAPITAL_MATRIX.json)、[ACT原时钟](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/ACTUAL_ACT_EPISODES.json)、[全部campaign](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/2022_2024_CAMPAIGNS_FULL_ACCOUNTING.json)、[原日风险参考](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/scale_concentration/results_v3/2022_2024_DAILY_CAPITAL_RISK_CONTEXT.json)。0finance/0新账户/0参数。

真实源账行入口：[2022H1](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/STAGE_WEALTH_CAPITAL_MATRIX.json:5)、[Dec2022](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/STAGE_WEALTH_CAPITAL_MATRIX.json:817)、[2023Jan-Apr](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/STAGE_WEALTH_CAPITAL_MATRIX.json:1195)、[2023May-Jul](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/STAGE_WEALTH_CAPITAL_MATRIX.json:1611)、[2024Sep24-Oct8](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/STAGE_WEALTH_CAPITAL_MATRIX.json:3001)、[Oct8之后](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/STAGE_WEALTH_CAPITAL_MATRIX.json:3365)、[三年合计](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/accounting/results_v2/STAGE_WEALTH_CAPITAL_MATRIX.json:3774)。
