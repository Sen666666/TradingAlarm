# ACT冻结与重启：现行代码复盘，不运行新回测

**ACT20_BREAK是“本活动阶段收盘回撤达到20%后，请求全退出”的开关，既不是小额试错控制，也不是最多亏20%的保证。恢复后直接回到原交易权限，没有账户级分批恢复。** 本文只读冻结源码及已有原账；新增回测、账户、参数测试均为0。

## 精确条件和执行时钟

实际调用是`ACT20_BREAK`，不是`ACT20_FAST`。

```text
on时：peak = max(原peak, 当前收盘NAV)
dd = 1 - NAV / peak
on且dd >= 0.20：on=False，记录pause
off时：peak冻结；只有flat且breakout才on=True
resume时：peak=当前NAV；episode += 1
```

原代码位置：[risk_policy.py:8](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py:8)，调用及全退出位于[joint_v3.py:222](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:222)。阈值为`>=`而非严格大于；首阶段峰值初始化为100万元。活动阶段每天按收盘NAV更新峰值；暂停期间不更新峰值。

`flat`精确为：所有真实position shares均为0，`a.exits`为空且`a.buys`为空。股息应收、卖款应收不要求归零，但应收不能冒充可用现金。[risk_policy.py:24](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py:24)。

原`breakout`公式为：

\[
M_t>\max(M_{t-63},\ldots,M_{t-1}),\quad M_t>M_{t-1},\quad B_t>0.60.
\]

使用已完成当日CLOSE；此前63高不含当日。M是原股票收益按行业等权构成的合成市场，B是原有效行业内量价动量为正的广度均值；不是沪深300、510300或63日均线。公式见[ORIGINAL_COMPUTE_RECOVERY.py:15](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/market-proof-lifecycle-readonly-20261101/ORIGINAL_COMPUTE_RECOVERY.py:15)。当日缺恢复行，`breakout=False`。ACT20_BREAK不另要求广度先关后开；该edge条件只属于ACT20_FAST。

以下是原`on`布尔值与持仓/订单状态的组合，便于理解，并非声称原代码已有这四个enum状态：

| 当前组合 | CLOSE决策 | 随后实际行为 |
|---|---|---|
| 活动且dd<20% | 更新peak，继续活动 | 原入场/追加/退出和资金约束继续 |
| 活动且dd≥20% | 当CLOSE转off | 对全部真实活层发ACT_pause退出，封新买；不在该收盘即时卖出 |
| off且未真实flat | 保留off/旧peak | 原退出责任持续，不能因价格突破绕过未完责任 |
| off且flat且BREAK63 | 当CLOSE转on，peak重置当时NAV | 最早下一合法OPEN按原完整交易权限申请资金，无新增分批恢复上限 |

退出请求位于[joint_v3.py:225](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:225)，封新买位于[同文件:246](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:246)。原OPEN执行先处理退出、结算和原资源同步，再处理新买；T+1、合法数量、容量、费用及HL日线代理仍有效。请求不等于成交，未ACK责任不能提前释放。完整实际执行限制由原native engine维持，本次没有新认证交易所排队或真实开盘可成交性。

## 已审原账户路径：20%触发之后还会有损失

单位元；均是各自真实连续路径，不将旧账户暂停日历注入新策略。

| 原路径 / 暂停CLOSE | 活动阶段peak | 暂停NAV / 回撤 | 首次真实flat CLOSE / NAV | 原恢复CLOSE |
|---|---:|---:|---:|---|
| No60 2022/4/20 | 1,000,000.00 | 785,066.18 / 21.4934% | 4/21 / 779,819.31 | 2022/6/17 |
| No60 2023/7/20 | 942,596.01 | 748,193.45 / 20.6242% | 7/21 / 745,426.96 | 2024/5/6 |
| No60 2024/12/23 | 805,043.93 | 640,851.59 / 20.3955% | 12/25 / 637,989.61 | 截止年末无 |
| D_GROSS10 2024/6/11 | 1,043,124.49 | 830,555.12 / 20.3781% | 6/12 / 825,930.51 | 2024/9/27 |
| D_GROSS10 2024/12/23 | 905,257.60 | 721,608.02 / 20.2870% | 12/25 / 718,642.10 | 截止年末无 |

No60首阶段清仓后相对阶段峰值已亏22.0181%。损失主要在触发前形成；上述暂停到首次flat的进一步损耗各约2,766—5,247元，不能把整个20%损失归因于清仓执行等待。部分交易另有真实代理受阻例子，不据此泛化为全部清仓畅通。

D在2024/6/12已flat，直到9/27 CLOSE仍须等原BREAK63；9/24、25、26、27的OPEN均暂停，最快9/30 OPEN才买。9/30实际买49笔后，CLOSE股票市值占NAV已82.90%。这是**恢复等待偏慢与恢复后直接大规模授资**的组合，不是持续10%账户试探。新增D10门并未绕过ACT；当附加市场DOWN门不生效时，仍回到原No60权限。

原risk_checkpoint的resume行，`episode_drawdown`先按旧peak计算，然后state内peak已改为NAV；不能把同一行两字段误读为新阶段立刻又回撤20%。上表已与原独审日账/H时钟核同，来源见[EXISTING_FACTS](act_recovery_candidate_v2/EXISTING_FACTS.json)、[2024账户独审](audit_2024_account_v2/ACCOUNT_2024_INDEPENDENT_AUDIT.json)。

## 与小亏大赚目标的冲突及边界

1. **20%属于账户损失已经很大后的强退。** 它没有约束此前多次试错的累计支出；35%也没有作为此函数的触发阈值。用户的35%边界不能反过来证明ACT设计合格。
2. **阶段重置不是全历史回撤约束。** 恢复把peak重置为较低NAV，财务亏损仍保留，但下一次防守不再参照更早财富峰值。纯算术例子：即便每次都精准止在−20%，100→80→64，两段累计已−36%；真实执行还可能超阈值。原No60三年实际收盘MDD38.09%，与单阶段20%没有矛盾。
3. **停机后要求全flat且BREAK63，可能推迟参与；恢复则没有原生的小额阶段。** 该条件是保守重启资格，不是“早试错、后随证据逐步加仓”的账户级实现。不能只缩短63日而保留恢复后立即大仓，便称已解决风险哲学问题。
4. **不是单笔保护。** 原mobile价格保护与core的I结构退出另有时钟；二者均可能在ACT之前累积亏损。ACT不会把过去失败消耗记入每次新单许可，也不检验新买是否为同一相关风险的重复尝试。

明确的机制方向是拆开三件事：先收缩新增风险权限、原股结构保护是否退出、真实flat后如何分阶段重授资金。任何新机制都必须保留未成交/取消责任、费用和缺口风险，并明确累计亏损消耗何时及凭何种新证据恢复，不能每次换股/迁池/新CP1就自动返还失败预算。**本次只提出合同要求，没有把某一阈值、P20或分批方案证明为有效，更没有运行回测。** NOT_DOWN新买质量仍由另一条研究线负责。

更快恢复的旧P20/21已有先前研究；2022年末及原strong路径没有ACT暂停，不能人为插H后称实际改进。首日暖启动是否特殊与持续期风险许可，另按原2024后段303层及60日实际资源审查，不能用首日一例代替整段历史。
