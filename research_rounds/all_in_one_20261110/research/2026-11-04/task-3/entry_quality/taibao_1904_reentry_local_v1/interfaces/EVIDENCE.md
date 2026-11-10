# 太保1904假设9/9提前退出：原接口的局部重申请边界

**若只在2024-09-09 CLOSE对1904调用原 `a.sell`，卖完该400股目标后，即使1914仍持有，`sid in exits`也会解除；不必全股清仓。最早后续原新CP在9/18 CLOSE，可申请MOBILE，不能称CORE重入。** 本文未调用sell、未造9/10成交、未运行账户/回测或改策略；原现金和获资结果不替代假设退出后的状态。

## 1. 9/9已经拥有两层，卖1904不撤销1914

原No60 journal精确记录：

| 原层／来源 | 实际signal | 实际reserve/fill | 股数／含滑点买价 | pool |
|---|---|---|---|---|
| 1904／MOBILE | 08-30 CLOSE | 09-02 09:30 | 400／29.664825 | confirmed |
| 1914／MOBILE | 09-06 CLOSE | **09-09 09:30** | 400／30.775380 | confirmed |
| 1931／MOBILE | 09-18 CLOSE | 09-19 09:30 | 400／30.41520 | confirmed |

三层原watch epoch均`[0,24]`、同保险attempt。原book整个2022—24没有太保CORE fill，不能把这三笔MOBILE当成已消费CORE epoch。9/9 CLOSE才提出1904更紧退出时，1914早已实际fill；`cancel_buy`取消未成交余量，不能倒销这个真实持仓。1931是后续**原路径事实**，不是假设提前卖后已证明仍会买到的结果。

## 2. 部分目标何时解除exits：实际卖够目标，不等全股flat

绝对源 [pilot.py:104](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:104)：

```python
ids|=self.sell_layers.get(sid,set());self.sell_layers[sid]=ids
shares=sum(z['qty'] for z in self.live(sid) if z['id'] in ids)
if not shares:return
if sid not in self.exits:super().request_reduction(quote,clock,shares)
else:
 ex=self.exits[sid];ex.remaining_target=shares
 if shares==self.quantity(sid):ex.purpose='structure_exit';ex.remaining_target=None
```

在没有旧待退集合的局部前提下，`ids={1904}`只建400股目标，不把1914自动加入。后续其他真实退出可能合并目标，届时应按新集合解释，不能继续假设只卖400。

[sector_account.py:585–595](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:585) 的 `request_reduction` 调 `request_exit`；后者577行先 `self.cancel_buy(sid)`，然后建ExitOrder，再设 `remaining_target=shares`。实际填充受 `_eligible_event`、T+1库存、数量规则、capacity等限制（746–772），**不是信号日就释放持仓/资金**。

[sector_account.py:792–796](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:792)：

```python
if not pos.shares:
    del self.positions[sid]; del self.exits[sid]
    self.completed.append(admission.ExitCompletion(sid, order.event_id, window.at))
elif order.remaining_target == 0:
    del self.exits[sid]
```

所以假设400股目标实际卖够，剩余1914仍在，也会走第二分支删exits；这**不会**产生全股 `ExitCompletion`。只卖一部分而target>0时exits继续存在。随后 [pilot.py:74–87](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:74) 按真实receipt分摊到目标层；sid不再有exits时清 `sell_layers`，全股数量才为0时另清 `last_buy`。J130–135在真实卖fill后记录费用/损耗并sync。

## 3. OPEN清目标不会回补上一CLOSE被跳过的买入意图

[joint_v3.py:302–318](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:302) 顺序是：先尝试实际退出→settle_due→sync→处理上一CLOSE已冻结pending买意图。J247的 `sid in a.exits` 在CLOSE阻止创建该股买意图；次OPEN即使目标刚完成，也不重新跑当日CLOSE信号或补造被挡的旧意图。

因此这里只能条件式说：如果9/10或以后某OPEN实际完成1904目标，后续CLOSE解除这道pending门。没有新的合格CP时仍不能MOBILE申请。若9/18 CLOSE仍未完成目标，该日新CP也会被exit_pending挡掉；之后完成不能在下一个CLOSE复用这张过日凭证，需再等当日新CP及原资格。

## 4. 最早原新信号是9/18，而且不要求新的暖I buy

[joint_v3.py:213–219、243–251](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)：

```python
event[sid]=BP.A.eligibility(s,ss,clock,'S0')
continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
if cpr and continuing[sid].q is True:roles.append('mobile')
if sid in a.exits:why.append('exit_pending')
if sid in a.buys:why.append('buy_pending')
```

9/9—9/13原CP为空。9/18有真正新receipt `e65332baeb77f7dccdd4b63c3f755124d6f568887fc41e5ce08d1d432b0d74ef`，原opportunity的0-based索引1121236：`core_Q=False, mobile_Q=True, roles=['mobile'], barriers=[]`。源facts当日 `I_target=1, g_grade=-3, i_buy=False`。这不是交易所禁买，也不要求再取得暖G1：MOBILE采用continuing资格，替换的是buy_allowed，新I买入事件只用于event/CORE那条门。

所以若1904目标已在9/18 CLOSE前实际完成、无其他新退出/待买且原市场资格维持，可在**9/18 CLOSE**再次申请MOBILE，最早调度9/19 OPEN；不是9/10无新CP就恢复，也不必等9/24新的暖I买入。原9/19确有1931真实fill只证明原路径当时获资，不能证明假设路径同量获资。

## 5. CORE、watch、行业attempt与CP消费各管什么

| 状态 | 原精确作用 | 对本局部假设 |
|---|---|---|
| `held` | J244：CORE要求全股无持仓；MOBILE不要求flat | 1914仍持有时CORE直接不合格；MOBILE可恢复扩仓 |
| `core_epoch` | pilot70只在CORE真实fill写；卖出不删除它 | 原太保无CORE fill，不能虚称被MOBILE消费。若将来全flat，也还要当日event_Q与epoch不等、probe等全部门 |
| `watch_epoch` | J216–219在`(I_target,segment)`变化时自增、清旧watch；event_Q可更新watch | 部分CP卖出不改变I市场状态或制造新epoch；这段原I/source稳定，原层epoch `[0,24]` |
| industry episode/attempt | 市场行业E0/CP驱动，失败后invalidate；非该股盈利毕业 | 1904部分sell本身不start/invalidate行业，不清行业历史；原同attempt在9/13已expanded。金融迁池结果仍受实际pending等状态约束 |
| stock CP consumed | 正常route先查新token/资源，q>0才request；request将CP消费 | 卖出不返还8/30或9/6已用CP。新9/18是新token，不能重复花旧凭证；q0正常route拒不消费，但不等于明天可追用过期日证据 |
| `exit_pending` | J247挡CLOSE新意图，J310再挡OPEN；partial余量保留 | 必须等目标真实成交清除；触线或新CP不自动解除 |

实际No60覆盖见 [native_adapter.py:11–40](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:11)。资金route/request采用P生成的去global3%／confirmed60版本；本目录SOURCE_EXCERPTS包含已静态还原的有效代码，不把J原模板的3%/60%门写回。confirmed只说明行业层许可；CORE新单仍probe-only，不能借行业expanded冒成CORE可入confirmed。

## 6. cancel_reduction是存在的API，不是当前自动恢复分支

[sector_account.py:597–602](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:597) 只在order.purpose=`annual_rebalance`时删exits；若是`structure_exit`则报不可撤。这里有一个必须如实说明的复用细节：pilot首次部分sell调用request_reduction，因此这个部分目标被标`annual_rebalance`，手动调cancel_reduction从机械上可删掉它。

**当前No60 J/planning/opening/pilot路径没有调用它。** 它也不清pilot的sell_layers/reason；不能将此裸API冒称新CP自动撤旧退出的正常重申请流程。本审查不调用、不增接这个分支，也不新增重入禁令。正常恢复仍按真实目标完成解释。

## 7. 9/24后的原信号与资金拒绝：只能作原路径证据

| 原信号CLOSE | 原事实 | 次原OPEN的真实结果 |
|---|---|---|
| 09-18 | CP新、i_buy=False、mobile_Q=True | 09-19 confirmed400股已买 |
| 09-24 | CP新、i_buy/core_Q/mobile_Q=True；held所以只mobile | 09-25：cash_or_original_reserve,probe_risk,sector_capital,sector_risk |
| 09-26 | CP新、i_buy/core_Q/mobile_Q=True；只mobile | 09-27：cash_or_original_reserve,sector_capital,sector_risk |
| 09-30 | CP新、i_buy/core_Q/mobile_Q=True；只mobile | 10-08：cash_or_original_reserve,probe_risk,sector_capital,sector_risk |
| 10-08 | CP新、i_buy/core_Q/mobile_Q=True；只mobile | 10-09：cash_or_original_reserve,probe_risk,sector_capital |

9/23、9/27虽有原i_buy/core_Q=True，但无新CP且仍held，因此roles为空，不是另一张MOBILE额度。表内资金失败字段是原route对候选池最低单位失败原因的合并集合，不能把它当每个池每项都独立绑定，更不能称是重入禁令。9/24之后还有新信号，未买不是因为策略永久忘记太保。

1904假设卖出后，现金/费用/NAV/ACT、库存mark与单股10%剩额、原2%MOBILE冻结名义量、行业capital/risk、probe容量、其他股票竞争、pending/ACK与金融迁池均可能变化。原拒绝不能直接移植成假设拒绝；原成功也不能移植成假设成功。这里只识别市场证据与接口必要条件，不补数量、卖价、收益或后续持仓路径。

## 交付

[ORIGINAL_TAIBAO_LOG_EXTRACT.json](ORIGINAL_TAIBAO_LOG_EXTRACT.json) 保存原层、metadata、实际fills/journal及opportunity/funding/industry原行索引；SOURCE_EXCERPTS保存逐行原码，SOURCE_SHA256/DELIVERABLE_SHA256保存绑定。补充原链见同根目录original_chain，未修改其他owner文件。候选9/10成交与完整账户经济效果均未验证。
