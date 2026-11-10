# MOBILE已卖出后，后续申请要求G1≥2：原路径筛选

**主任意历史同股退出口径：2022—24触及52笔原实际fill，原净贡献+2461.93元；2026H1触及6笔，原净贡献−9489.37元。不能把后者当可赚9489元，亦不能把前者当已经证明候选损失2462元。** 全部只是固定原路径覆盖；没有新账户、策略修改、候选收益或资金再分配。

## 先更正太保的历史范围

太保原layer639在2022-09-30 09:30已实际卖出700股（原trade索引1260、receipt `fill:601601.SH:3795`），root=`601601.SH|0|2022-08-11`。2024年的1904/1914/1931属于新root=`601601.SH|0|2024-08-19`。

因此9/18 grade−3的原MOBILE信号，按**任意历史先退出的主口径会触门**；按**同当前root的附口径不触**。假设1904已9月提前卖出，则附口径也可能触，但该假设不插入本次原路径统计。我前面把“当前2024结构未卖”误称成“连续原历史未卖”，已向父线程更正；本次52/12和6/4数字从一开始均使用真正全账前缀，未为预期说法缩窗。

## 实际原公式为什么允许G1未暖时MOBILE买入

原No60 [joint_v3.py:213–245](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)：

```python
event[sid]=BP.A.eligibility(s,ss,clock,'S0')
continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
if cpr and continuing[sid].q is True:roles.append('mobile')
```

原 `G1_I` 在 [policies_g1.py:16–34](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:16) 将两件事分开：I持有状态active只因E0 shadow失效或收盘破旧I线退出；新的I buy opportunity另需ready、grade≥2与entered/fresh。MOBILE把S0的buy_allowed换成market_buyable，所以不要求当日I buy新事件或G1≥2，但仍受其余原S0、fresh CP、ACT、待单、行业和资金等门约束。

`G1<2`在此叫**未达暖**，含grade1修复，并不等于原生cold。原生cold为`ready & (grade<=−2 or acute_down)`，另列字段。2022—24全部1767个MOBILE fill中117未暖，只有79属原生cold；2026H1的390个MOBILE fill中18未暖、12原生cold。筛选触及的52层里35属原生cold，其余含16个grade1和1个grade−1；六个2026层均原生cold。

## 两个冻结口径与因果时钟

主口径：只要同一原账户中，此前已有该股**实际sell receipt内MOBILE/add part shares>0**，之后MOBILE申请就要求本次decision的ready G1≥2。部分卖出立即建立记忆，不等整层、全部MOBILE或全股清空；不按退出是否亏损筛选。没有此前实际MOBILE卖出时，不加这个门。主记忆不随新E0/I/CP或行业attempt刷新，所以“首次新结构”也不必然等于“该账户从未先卖过”。

附口径：将同一条件再限定为sell part与当前信号的原 `stock_structure`完全相同。它是身份敏感性，不按结果选择主门或当成参数调优。原root按J190–194的因果lookup从事实缓存读取，全部2634个实际MOBILE fill与原metadata精确核同。

实际sell时间必须**严格早于decision_at**；同日OPEN卖出、CLOSE申请算已有退出，等时间戳不算。2026层739招商南油就是2/3 OPEN实际先卖、当日CLOSE未暖再申请的例子。2026H1保留strong原账2025H2的真实交易记忆，例如思源1102的先退在2025-11-24；没有把统计窗口当重启账户。G1按真实decision读，未再shift一bar，也未用fill日close或日后退出标签作输入。

## 原机会、实际意图、已拒单和fill分开

| 原窗口／记忆 | CP+continuing合格机会总数 | 记忆成立且G1<2机会 | 其中原已有barrier | 真正原MOBILE intent | 原OPEN已拒 | 原实际fill | 末日未到下一OPEN |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2022—24／主any | 56315 | 3101 | 1039 | **2055** | 2003 | 52 | 0 |
| 2022—24／附same-root | 56315 | 378 | 41 | **335** | 323 | 12 | 0 |
| 2026H1／主any | 11954 | 356 | 0 | **354** | 346 | 6 | 2 |
| 2026H1／附same-root | 11954 | 121 | 0 | **121** | 116 | 4 | 1 |

“真正原intent”是planning实际生成的MOBILE意图，不仅是CP+continuing资格；少数barrier-free机会仍因原size/floor等没有intent，未算新增拒绝。原OPEN已拒含原route/preview失败，细分原原因保存在JSON；不是全部都由同一资金门拒绝，更不能把它们算成已经避免的持仓损失。这里没有reserved但未fill的受影响申请。两个主口径末日意图为2026-06-30芯海688400、埃斯顿002747，原账已结束，未捏造下一OPEN。

主fill窗口与signal窗口分别计：2026H1原MOBILE390个新fill中629的decision在2025-12-31，已明确列为边界并保留；不为对齐而漏掉。来源账是strong独立的2025-07—2026-06原账户，未与2022—24的交易记忆串成一个账户。

| 窗口／记忆 | 触及原fill | 原正贡献 | 原负贡献 | 原净贡献 | strict realized | 未实现 | 分红AR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2022—24／主any | 52 | 24651.51 | −22189.57 | **+2461.93** | +1987.96 | 0 | +473.97 |
| 2022—24／附same-root | 12 | 8229.17 | −7507.02 | **+722.15** | +722.15 | 0 | 0 |
| 2026H1／主any | 6 | 89.35 | −9578.72 | **−9489.37** | −9489.37 | 0 | 0 |
| 2026H1／附same-root | 4 | 89.35 | −5025.30 | **−4935.95** | −4935.95 | 0 | 0 |

这些是已发生原层截至原账户末的净贡献（含真实费用；分红AR不是已收到现金），没有把cash负买款误当未平层亏损。所有受影响52/6层都已原实际闭合；全未暖18个2026层有1个仍未平，但不在六个受影响层内。

## 2026H1被触及的实际fill与半导体信号

| 原层／股票 | decision | grade | 原净贡献 | 同root附门 |
|---|---|---:|---:|---|
| 739 招商南油601975 | 02-03 | −3 | +17.14 | 触 |
| 753 海油发展600968 | 02-06 | −3 | +72.21 | 触 |
| 836 金开新能600821 | 03-16 | −3 | −1770.87 | 触 |
| 867 广汇能源600256 | 03-19 | −3 | −94.25 | 不触 |
| 897 豫能控股001896 | 03-27 | −3 | −3254.43 | 触 |
| 1102 思源电气002028 | 06-01 | −2 | −4459.17 | 不触 |

半导体原行业`URFI881121`：2026H1有1096个CP+continuing机会，其中81未暖。主门触及19个**已生成原intent**，同root附门9个；19个原本全部在OPEN已拒，没有实际fill。原H1实际半导体MOBILE24层都没有被此门触及（另一个CORE不在MOBILE母体）。这既不能说新门已避免半导体损失，也不能从原未获资推断换路径后仍不会影响赢家资金。

19个原intent完整清单在 [2026H1_SEMICONDUCTOR_BLOCKED_INTENTS.csv](2026H1_SEMICONDUCTOR_BLOCKED_INTENTS.csv)，含真实先退receipt、grade和原拒因：北斗星通1/23；东芯1/26、2/27；珂玛2/10；京仪2/10、4/22、6/11；华天2/13、6/16；德明利2/24；燕东微、立昂微、雅克2/25；甬矽2/26；新洁能4/30；立昂微5/25；长电、晶晨6/16；金海通6/18。

## 交付、核验范围与限制

- 快读：[COMPACT_SUMMARY.csv](COMPACT_SUMMARY.csv)、[MAIN_AFFECTED_ORIGINAL_FILLS.csv](MAIN_AFFECTED_ORIGINAL_FILLS.csv)、[MAIN_NEWLY_BLOCKED_ORIGINAL_INTENTS.csv](MAIN_NEWLY_BLOCKED_ORIGINAL_INTENTS.csv)。
- SUMMARY保存两窗口／两身份的完整signal与fill分解；TAIBAO_SEP18_SCOPE_CORRECTION保存原639 receipt和1931资格；ORIGINAL_MOBILE_SALE_RECEIPTS保存实际先退物理收据与MOBILE parts。
- ORIGINAL_QUALIFIED_SIGNALS是全合格机会明细，含原JSONL索引与原intent/OPEN记录；文件较大，日常复核先看小CSV。ORIGINAL_MOBILE_FILLS_WITH_MEMORY保存全部原MOBILE实际fill的时钟、G1、root、两种记忆与贡献。
- cost统计独立核1767／390全部fill的前一市场CLOSE=真实decision、grade/ready与事实源精确；feedback独立从两原book的实际sell.parts核52/12、6/4及八组原贡献聚合。独审未重扫全机会大表，此限制明确保留；全机会计数由本脚本、原行索引与源hash支持。

筛选没有修改已有持仓/退出；除了本次条件门，没有新增等待日、1R、仓位梯度或永久禁重入。未使用未来损益作信号，未对未知grade/身份填暖（本母体两者未知均0）。完整账户中删意图会改变PVR竞争、现金、实际先退历史、仓位及ACT；此处不把静态原贡献差额当因果收益、避损金额或样本外经济支持。
