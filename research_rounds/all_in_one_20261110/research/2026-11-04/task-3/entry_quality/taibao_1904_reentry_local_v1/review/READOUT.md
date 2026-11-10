# 太保1904早退出与海能达：独立局部复核

**结论：原码与关键原日志核同；只能给条件下的申请时点，不能给候选成交或收益。** 本轮没有运行账户、策略、window或候选现金路径。

## 核心原事实

9/9早原账已经买入1914/400，晚间1904/400＋1914/400合800股。A2仅对1904发退出假设，不会自动卖1914，因而不是全股清仓。9/10原runtime bar的OPEN30.04乘0.9995得**30.024980**；这是价格参考，不是原账存在的1904卖出receipt。

[pilot.sell104–115](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:104)按目标层汇总剩余数量。[SectorAccount:746–797](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:746)在部分目标真正卖够后，即使还持有1914，也可删sid.exits；未卖够则继续pending。[J247](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:247)仍挡同股新买。没有候选fill，就不能声称9/10已解锁；也不能用原未调用的cancel_reduction机械API当新CP自动撤旧单的恢复规则。

## 9/18冷CP是关键证据

独立从原facts、canonical receipt、opportunities、decision和trade交叉核同：

- 9/18 grade=−3、g_ready=True、I_target=1、i_buy=False。
- 新CP为`e65332ba…74ef`；原opportunity第1121236行mobile_Q=True、core_Q=False、roles=[mobile]、held=True、barriers=[]。
- 同日原decision生成同CP的MOBILE intent，cap400；原1931在9/19 OPEN记录400股。这是原研究账事实，非假设路径获资。
- canonical原件中，9/9之后至9/18没有更早的新CP。

原码解释是确定的：[G1_I:8,20–33](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:8)是entry-only，use_x=False；cold不直接使既有I失效，warm约束新I opportunity/i_buy。[Facts.packet44–45](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py:44)先把i_buy并入s.buy_allowed；[J218](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:218)的continuing又以market_buyable替换该字段。S0资格不直接核grade；fresh CP＋continuing可作为MOBILE申请资格，不能另加“必须再暖”的原规则前提。eligibility memo缓存完整输入，不是这个差异的来源。

**若**1904的目标已实际完成、旧退出/买单障碍已清，候选ACT与其它财务门仍允许，并沿相同原市场序列，最早新的MOBILE申请资格是**9/18 CLOSE**，最早调度9/19 OPEN。仍有1914，CORE的not-held条件不成立。若到9/18尚未卖清，旧退出继续挡买；该日CP不能在后来无新证据时任意顺延。不能保证最迟重入日。

9/9早1914用的是9/6信号；不能把9/9晚才知的cold反推成早盘已知。9/18才是“信号本身cold、仍有MOBILE资格”的直接证据。

## 海能达价格对照与经济边界

独立读取原runtime raw及原book核同：11/4 O22.84/H26.15/L22.84/C22.84，非flat；O×0.9995参考为**22.828580**。原11/5卖出代理价为**22.98850**，前一日参考反而低。11/1信号时不知道这一开盘gap或后来回升；H>L仅排除平盘这一项proxy拒绝，不证明容量、盘口队列或按参考价成交。没有用盘中26.15替换开盘价，也没有造候选sell/cash/PnL。

市场CP/G1/I日期可列，但1904早退出会改变数量、现金/应收、费用、NAV、池/行业占用及后续获资竞争，ACT也可能变化。原9/19的400股、原后四次拒绝及原cap不能照抄给候选；也未证明原拒因中哪项唯一binding。1914仍在、后续重新加层的峰从哪起算等，均应按已冻结规则处理，不能拿原10月利润倒推早卖损失。

root READ_FIRST关键结论无异议。独审范围为上述原字段/原码、最早新CP日期和三个价格参考；22日全财务表、反事实份额、费用、收益和完整重入路径没有重算。原源/原账未改。
