# CORE/MOBILE 单位风险修订 v1（待检初值；无回测）

**只改定量与共享额度。** 保原CP/G1/I触发、PVR顺序、CORE的I持有、MOBILE逐层CP退出及先旧线检查后ratchet；无1R、固定等待、加仓次数或额外重入禁令。不启用v3全户.64/ACT空间硬帽。以下不是最优/实亏上限，未运行新账户。

**价格、波动与一笔订单。** 同source段的原adjusted CLOSE记C；`r_t=log(C_t/C_(t−1))`，`s63_t=max(1e−8,1.4826·median(|r_(t−63)|,…,|r_(t−1)|))`，严格shift、不含当前收益，沿原CP/PVR暖机/断段规则；缺失为UNKNOWN，不补ε/0。h为**该层真实计划退出线**换到当时raw域：CORE用I线，MOBILE用原max(I,该次CP候选)，不换宽/紧合同。信号价`p_ref=raw_C·(1+s_buy)`，OPEN价`p_open=raw_O·(1+s_buy)`；slip/费用沿原协议。令

```text
h_stress = h · exp(−2·s63_signal)
R_order(q,p) = max(0, q·[p − h_stress·(1−s_sell)])
               + F_buy(q,p) + F_sell(q,h_stress·(1−s_sell))，R_order(0)=0
```

q为raw股，p/h为元/股，R/fee为元；**h_stress只用于风险估值，实际h及退出动作不放宽；2只是波动缓冲示例先验，不是95%/尾界/法定跌幅**。价差不替代T+1、停牌/跌停和流动性尾部。费用用原dated FeeSchedule/逻辑订单累计最低额；不按层/partial回调反复收最低佣金。

**三个待检额度，仅并发。** 新CORE和MOBILE都核 `R_order≤.0025·NAV_signal`（沿原CORE）；同股全部当前层/结构的并发参考责任 `R_stock≤.005·NAV_prefix`（2×原风险单位，**不是只准买两次**）；行业 `R_industry≤.01·NAV_prefix`（沿原sector比例，改为含缓冲/费用口径，须明示接口变化）。NAV_prefix是该OPEN真实资助prefix的当时NAV，不锁origin、不另扣历史D。**风险定量替代MOBILE原每次2%gross单笔额度**，保原stock10%剩余额度与其它capital/pool/现金留存/quantity最终门及native分母；不套旧MOBILE source cap来伪称已有风险改量。不恢复No60已移除的confirmed60或账户3%。

**旧仓、待单同量纲。** 旧live用剩余实际all-in paidbasis K（gross+分摊已付买费）、当前已知mark M、当前同源s63与真实h：

```text
X_l = min(M_l,h_l)·exp(−2s63)·(1−s_sell)
ρ_l = max(0, max(K_allin_remaining,l, Q_l·M_l) − Q_l·X_l + allocated_futureSellFee_l)
```

ρ取**本金到压力退出与当前mark到压力退出的较大者**，不把两种风险相加；含浮盈回吐，也保留已知本金浮亏。fresh fill将 `K=qp+实际F_buy` 一次转入live，保买入slip；仅在K≥QM、h≤M且同价域/费组时，`R_new=qp−qX+F_buy+F_sell = ρ_afterfill`。native mark可不同于raw OPEN；OPEN共账必须按预计fill后的原native mark和实际fee域重算旧ρ+新ρ，不能强改mark或无条件用R代替新ρ。不另用D重复计费。卖费每个真实/拟逻辑退出order组只计一次再按股数分摊；partial sell按真实parts移走对应all-in basis。

```text
R_stock / R_industry = 对相应股票 / 行业全部当前责任求和：
Σlive_nonexit ρ_live + Σbuy_open/cancelpending R_remaining + Σaffected_exit R_exit_lock
```

待买R_remaining按原冻结价/线/s63及**未付**buy/sell增量费；actual fill将gross+真实买费一次转K、数量转live，移除对应pending项。live与affected_exit互斥、不双计；取消ACK前保留余量。同股不同CP/epoch/结构仍汇入同一stock并发帽，不能每层各领.5%。已实现盈亏照原NAV/审计保留，**不新增累计D硬门**；释放仓位可重新入场，连亏可能反复消耗本金，累计损失不由并发帽封顶，原ACT仍在。累计试错预算若要采用，须另立假说，不能夹入本次最小修订。

**CLOSE→OPEN。** CLOSE在原退出/保护更新后，两个来源都用上式和原stock10%剩余重算局部最大合法q_cap；不先套旧CORE/MOBILE冻结量，**MOBILE原2%单笔gross被风险预算替代**。CLOSE只冻结局部上界，不预支明日卖款。nextOPEN先真实退出/结算，再按原PVR一次顺序，使用冻结h/s63和已知raw OPEN重核单笔、`旧仓+新仓+未ACK单`的stock/行业并发共账及原资金门；**保原raw OPEN≤真实h即拒单**，不因h_stress更低救单。只能缩量/拒绝，不超过signal cap，不读取当天未来CLOSE/HLV。取全约束下最大dated BUY格点；不足最小手为0，不向上凑股。不额外禁止重入，不要求保本/追回旧高；每次仍需原合法新信号及当时并发余量。

**超限/未成交。** 旧仓已超stock/industry并发额度，只拒新增，不强平健康赢家。EXIT_PENDING是受影响层集合，替换其live项：`R_exit_lock=max(请求时冻结ρ按真实余股折算,当前重算ρ)`，不因mark≤floor归0。实际partial/ACK才释放完成部分；同股待退时保原禁新。停牌、跌停、T+1无成交仍占库存/资本/责任，不把压力线当保证卖价。这里是同股/行业**并发参考责任之和**，不是同sid不同h的同步共同市场情景；共同跳空可超过2sigma并击穿预算，不能省略这项风险说明。未知源线/factor/波动/单位/费用/source或structure identity则不发新grant；旧退出和责任继续。

**必须保留的反例。** 统一.25%风险及波动缓冲可能把原可买的宽线/STAR最小手赢家减成0；原local-high用I线缩量曾静态伤强窗约52.50万元，本卡保MOBILE自己的CP线，不能直接套用旧金额，也不能宣称已消除代价。提线不等于能卖或趋势真成功，盈新提线后仍失败；marked风险释放也不等于本金释放。缓冲会在波动抬升时收紧新增、在波动下降时释放名义额度，可能追到加速末端；原单固定层损益差不是新组合收益。案例数值补充只读单点核算，**本轮不新account/回测/参数扫描**。

实现差分须同步：J255取消MOBILE2%预算截断；CORE/MOBILE共用新signal sizing及OPEN preview（不再只kind=core核R）；route/request按ρ和stock/industry并发帽重核；actual fill/partial/cancel ACK一次更新all-in basis/责任。不是只改报表字段。去2%也可能放大窄线低波动MOBILE，非单向缩量，尾部/集中代价待核。

来源：`joint_v3.py:218–257,302–324`；原`lot-risk-allocation/code/study.py:16,19–31,42–66`；CP `model.py:22–24`；No60 `native_adapter.py:11–22` / `component.py:17–34`。这些是本次拟修订的源接口，不声称当前代码已统一MOBILE风险预算。
