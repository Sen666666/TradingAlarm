# 太保1904的9月9日假设退出：后续原信号与局部可行范围

本轮只读原No60代码、原账、原价格和信号；不运行账户/回测，不构造候选成交、回款、重入或收益。假设仅为1904层在9/9 CLOSE因A的2s条件提出退出，不同时修改1914、行业授权或新增资金规则。

## 1. 9月9日收盘并非只持有1904

原实际买入：

| 原层 | 原信号→原OPEN | 原数量/代理价 | 原池 |
|---|---|---|---|
| 1904 | 8/30→9/2 | 400股，29.664825 | confirmed |
| 1914 | 9/6→9/9 | 400股，30.775380 | confirmed |
| 1931 | 9/18→9/19 | 400股，30.41520 | confirmed |

年份均2024。9/9早1914已经买入，不能当成晚间尚未执行意图。9/9 CLOSE原1904/1914各400，合计800股；两层均MOBILE、同旧保护线raw29.3632134616，1904的A2触发本身不自动卖1914。

1904在9/9的A2依据为前已知峰30.99、当收30.06、原CP冻结s=0.01176672843，对数回撤2.5894s；没有使用后来924或10月高点。

9/9信号的次市场OPEN是**9/10**：raw O30.04/H30.18/L29.65/C29.88，V23568055股；5bp卖价参考30.02498。1904原9/2买入，按原A协议T+1静态应9/3可卖；1914的必要日期为9/10。这里只核日期、价域、数量格点及非flat等必要事实，不生成400股候选fill、费用或可用现金。历史可卖状态仍有proxy，盘口/ACK缺失。

原原子目标规则：`pilot.sell(ids={1904})`只请求对应400股reduction；native真实模拟fill卖够remaining_target后即删sid.exits，即使还有1914持仓。partial未满仍pending且阻止同股新买。当前No60没有新CP自动调用cancel_reduction撤旧退出的流程，不能把它当作恢复捷径。

## 2. 最早重新申请：9/18 CLOSE，条件下最早调度9/19 OPEN

**前提必须写在结论之前：假设1904的目标400股确已成交并清除退出pending，1914仍400股，之后没有其它退出/待买阻碍。** 在这个前提和相同原市场价格/信号下：

| 原CLOSE/OPEN | 原市场信号与原账户记录 | 对假设路径可说明什么 |
|---|---|---|
| 9/9 CLOSE | 原CP无新receipt，I_target=1，i_buy=False，grade−3；原未卖 | A只提出1904退出，不能当已卖 |
| 9/10 OPEN | 原O30.04、5bp参考30.02498 | 只是最早候选执行窗口，不确认fill |
| 9/10—9/13 CLOSE | I_target仍1、原mobile_Q=True；无新CP | 即使卖清，也没有原MOBILE新证据可重申 |
| 9/18 CLOSE | 新CP `e65332ba…74ef`；grade−3、i_buy=False、I_target=1；原mobile_Q=True、roles=[mobile]、barriers=[] | 这是9/9后的第一个原合法新CP申请日；不必等到9/24暖信号 |
| 9/19 OPEN | 原1931为confirmed400股、cap400，价30.41520 | 证明原路径确有该申请；不是反事实重入成交或数量 |
| 9/23 CLOSE | i_buy/core_Q=True、无CP，原held=True、roles=[] | 有新I买入事件不等于原已持仓可以新CORE；本例假设保1914仍不flat |
| 9/24、9/26、9/30、10/8 CLOSE | CP与i_buy同真，原均生成mobile intent cap300 | 是后续原市场证据日期；获资仍需新账重算 |
| 9/25、9/27、10/8、10/9 OPEN | 上述四意图原均被现金/池/行业门拒绝 | 这些原拒因不能搬到少持1904的新账 |
| 10/9 CLOSE→10/10 OPEN | 原三层才因CP退出，1200股原代理卖价36.66166 | 是原终点，不是A退出后的终点 |

9/14—17没有插入虚构交易日；9/18为原session中的下一次新CP资格。

本例是**MOBILE减仓后恢复扩仓资格**，不是已全股清仓再首次入场。CORE原规则仍要求not-held和原eventQ/epoch等条件；MOBILE不要求flat。若目标400到9/18 CLOSE仍未卖清，`exit_pending`继续阻新，9/18凭证不能在后来随意补用；再申请需等待后续当时合法的新证据及其它门通过。不能给保证最迟重入日。

## 3. 最重要的代码事实：冷级别也可有continuing MOBILE资格

J218分别计算event与continuing，后者的实际原文为：

```python
continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
```

J244–245：

```python
if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
if cpr and continuing[sid].q is True:roles.append('mobile')
```

原Facts.packet将当日i_buy并入stock.buy_allowed；continuing替换该字段为市场可买性，因此不再要求当日新的暖I买入事件。原G1_I又是entry-only：cold只有在use_x分支才退出，当前use_x=False，所以I_target可继续有效。

9/18不是理论推断：原facts、canonical CP、opportunity、decision、9/19实际1931收据交叉存在。grade−3/i_buyFalse并不阻止该次CP+continuing申请。原20k record_only不因此新增损耗冻结。保护1904提前退出本身也不会重置外生CP生成器、清空旧CP消费、撤销行业confirmed或强制该股等I重新变暖。

所以保护线设计的关键不只是‘卖得早不早’，还包括：退出是否只减少该层，还是改变后续新增授权；当前假设没有加入新的重入禁令。

## 4. 为什么不能照抄原9/19获资或后四次拒绝

下列原拒因是路由多池结果汇总，不是唯一binding门：

| 原执行日 | 原拒因 |
|---|---|
| 9/25 | cash_or_original_reserve, probe_risk, sector_capital, sector_risk |
| 9/27 | cash_or_original_reserve, sector_capital, sector_risk |
| 10/8 | cash_or_original_reserve, probe_risk, sector_capital, sector_risk |
| 10/9 | cash_or_original_reserve, probe_risk, sector_capital |

假设1904卖出会改变该股数量、已实现费用/损益、现金与应收、probe/confirmed和行业资源、NAV及后续全市场PVR顺序中的获资。释放的钱可能先被其它股票使用，ACT也可能随新路径NAV改变。即使市场指标日期不变，原held/exit_pending/buy_pending/预算和实际数量不能照抄。

最小能给的是条件时间下界9/18→9/19，而非‘一定买回400’。原cap400、后续cap300只是参照；反事实cap还随新NAV及10%单股余量变化，不能将原cap当严格上界。原申请槽前available、每池搜索q与成功binding向量未保存；本轮也未构建新账户，因此可能获资为0，任何正数量须按新状态和整手重算。

## 5. 海能达11/1：可预见与不可预见

11/1收盘时已知H=28.20、C=25.38、s=0.0385112561、A2已破而旧CP23.637660678尚未破；可知道下一市场OPEN是周末后的11/4，并存在跳空、未成交风险。

当时不知道的后来原事实：11/4 raw O22.84/H26.15/L22.84/C22.84，5bp卖价参考22.82858；原策略11/4 CLOSE才触CP，11/5 rawOPEN23、实际原代理卖价22.98850。早一日参考价格反而较低，原因是下一开盘向下跳空，而原后一日开盘稍回升；不能把这两个后验价称为9/9式策略的完整收益，也不能声称事先知道应该等一天。

11/4并非flat day（H>L），但这只排除原代理的单项拒绝，不证明队列/容量或本单真实成交。盘中后来到26.15不能被拿来事后替换OPEN成交；若选择盘中限价或触线单，必须预先定义且需要相应历史数据。本轮只比较原价参考，没有新fill。

## 6. 决定保护线设计仍需明确的变量

1. **作用范围与许可**：触发只卖该层、全部MOBILE还是整股？保留I_target时，是否仍允许冷grade下新CP再加？这两件事不能由‘更紧保护’自动决定。
2. **新层的峰与尺度**：新申请是重设入场后峰，还是继承旧机会的峰/失败记忆？当前A按层，卖后新层不能直接继承旧1904的事后高点；需单独定义，尚未修改。
3. **执行合同**：信号后开盘/开盘后报价/限价如何处理跳空、partial与未成交？历史日线不能认证盘中止损价或后来高价可得。
4. **再分配反馈**：新现金、行业/池额度、PVR竞争、新NAV和ACT会带来多少新申请及新损耗？原日志只证明原路径，本轮不能给数值结论。
5. **凭证与时钟**：退出未完成时新CP如何处理？原代码是阻新、不会自动顺延旧凭证；若改变，需要明确新规则，不能靠原记录补用。

在这些变量未定前，既不能用‘9/9早卖’直接算错过10月利润，也不能用原9/19买入证明一定能恢复趋势暴露。

## 原始交付

- [22日原链与获资/拒单](original_chain/READOUT.md)、[逐日原字段](original_chain/ORIGINAL_DAILY_CHAIN.csv)、[全部CP/I日期](original_chain/CP_I_BUY_TRUE_DATE_SETS.json)、[9/10原必要执行状态](original_chain/SEPT10_OPEN_NECESSARY_STATE_ONLY.json)。
- [冷CP原facts/opportunity/decision/收据独核](review/COLD_CP_ORIGINAL_CROSSCHECK.json)。
- [实际接口原文](interfaces/EVIDENCE.md)：`joint_v3.py:213–259`规划、`:302–324`开盘调用；生效route为`native_adapter.py:17`的`P.ROUTES[True]`，不是J272原route；`pilot.py:104–115`层级sell、`sector_account.py:746–797`部分目标fill完成。原J全局3%/confirmed60已覆盖，不能误当本例生效门。
