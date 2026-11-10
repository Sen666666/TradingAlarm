# 现行No60资金状态、失败记忆与最小执行位置

仅静态源码和已存原账摘录；不导入策略模块、不重放账户、不跑回测、不修改策略。`confirmed`指行业授权/预算状态，`pool`指持仓或订单的占用归属；两者不能互相替代。

原文入口：[状态机完整源码](state_code/EVIDENCE.md)、[风险/损耗独立源码复核](risk_memory_review/EVIDENCE.md)、[盈新逐笔原字段](yingxin/READOUT.md)。

## 1. 行业如何确认、迁池，和同股盈利有何关系

[budget_v3/model.py:127](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:127>) 的真实行业升级原文：

```python
        if not s.active:
            s.active, s.level, s.started = True, 0, token.confirmed_time
            s.attempt = f'{s.episode}:{token.event_id}'
            s.status = 'probe'
        else:
            s.level = min(2, s.level + 1)
        for order in self.orders.values():
            if s.level > 0 and order.sector == token.sector and order.attempt == s.attempt and order.pool == 'probe' and order.qty > 0:
                self.cancel(order.oid)
        self.migrate(token.sector)
```

首次合格行业CP启动level0；后续严格新于历史进展的行业CP提升到1、2。不是每只股票先试仓并证明盈利后才升。`migrate`要求active、level>0且同attempt没有probe待单/cancel_pending；随后将**同sector、同attempt的probe持仓**改为confirmed，status为confirmed或expanded，断言现金、NAV、总资源、累计损耗不变。已有CORE也可能迁池，不能说confirmed持仓只含MOBILE。当前No60已删去原迁池60%资本门，待单责任仍保留。

初始化也可能直接继承START前行业level1/2，而当时个股账户仍空仓，见 [J:181](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:181>)。

新申请选择池的原文（without-account模板；此段在No60未改）：

```python
  routes=['probe']
  if role=='mobile' and b.expand and s.level>0:
   if b.migrate(sector):a.pools_from_model();routes.append('confirmed')
  ...
  q,pool=max(results,key=lambda z:(z[0],z[1]=='probe'))
```

见 [route_without_account_check.py:8](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/route_without_account_check.py:8>)。CORE新单仅probe；MOBILE有新个股CP、continuing Q、行业active时，才可能再比较confirmed。取可给最大合法股数的池，平手选probe。代码不要求该股原仓盈利、曾达某浮盈、原MOBILE没有亏损或已经持有CORE。实际库存/价格/保护线会通过资金占用、NAV、个股10%和行业门影响数量，不能说完全没有持仓联系。

## 2. 失败记忆实际记什么、何时重置

| 记忆/状态 | 原执行语义与重置 |
|---|---|
| `failed_bar` | `invalidate`令active=False/status=invalidated，更新max(failed_bar,bar)，撤销该episode待单。新episode也继承旧failed_bar。它来自行业E0无效或行业end_attempt，不由某股止损/盈亏直接触发。 |
| 新行业证据 | end和confirmed_time须严格晚于failed_bar，并严格新于上次消费的bar/end/confirmed_time；确认必须就是本次bar。没有要求formation_start晚于失败，也没有检验重夺失败前高点。 |
| 新attempt | inactive后新的合法行业CP启动，level重回0、started改确认bar、新attempt ID；旧持仓/旧待单继续占资源，旧池不因invalidate自动降级。 |
| 新episode | `start`同episode不动；换episode先invalidate旧episode，再建立awaiting_first_cp1新Sector，重置level/进展字段、保failed_bar。旧lot/order保原episode/attempt。 |
| `consumed` | 原行业/个股规范凭证ID去重；不因换attempt/episode、卖出而清空。新个股CP可重新申请，不等于旧CP反复复用。 |
| `stock_requests` | oid在request一开始加入，失败申请也不静默重试同oid。新日/新role对应不同oid；它不是同股累计亏损门。 |
| CORE epoch | 同股CORE实际fill后锁当时epoch；同一I授权段内不能反复首买CORE。MOBILE仍可凭新CP申请。 |
| `losses[(sector,原episode)]` | 累计负价差和费用；不是每股盈亏、不是净收益；正收益不抵减。只在新预算对象初始化时清空，换行业episode/attempt、ACT恢复、月/季度checkpoint均不清零。 |

关键原码见 [model.py:95](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:95>)、[119](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:119>)、[166](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:166>)、[J行业调用195](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:195>)。无股级失败导致行业降档的直接调用。

## 3. 2万元record_only原码与实际入口

[J:16](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:16>)：

```python
def __init__(self,expand):self.expand=expand;self.receivable_equity=0.;super().__init__(nav=1e6,cash=1e6,shared_loss_budget=20000,exhausted_policy='record_only')
```

[model.py:87](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:87>)：

```python
    def loss(self, sector, episode, amount):
        key = (sector, episode)
        self.losses[key] = self.losses.get(key, 0.) + amount
        if self.exhausted_policy != 'record_only' and self.shared_loss >= self.loss_budget:
            for order in self.orders.values():
                if order.pool == 'probe' or self.exhausted_policy == 'all_new_risk':
                    self.cancel(order.oid)  # Never release reservation without ack.
```

request中也有同样政策开关：

```python
        if self.exhausted_policy != 'record_only' and self.shared_loss >= self.loss_budget and (pool == 'probe' or self.exhausted_policy == 'all_new_risk'):
            if pool == 'confirmed': s.status = 'confirmed_unfunded'
            return 'shared_loss_exhausted'
```

因此当前只记账，不因2万元耗尽而主动撤单/拒新。2万元是初始化给定的固定人民币金额（相当于初始100万元的2%），不是随当前NAV变化的比例分母。实际回调不是调用合成`Contract.fill/sell`重复记账：J111记录真实研究账买费；J134逐卖出part记 `max(0,原unit_cost−本次实际模拟卖价)×卖股数+分摊卖费`。行业episode换了也仍按原lot的episode归账。支付/分红不作为该累计损耗的盈利抵扣。

跨episode/attempt、checkpoint保留是指同一连续账户；2022—24长账和strong窗口是各自从100万元新建的独立账户，不跨两账继承losses。

## 4. 实际金额上限、分母与No60删掉的门

`resources(pool=None,sector=None)`对选中lots+open/cancel_pending订单相加：

```python
capital = sum(x.qty*self.prices[x.stock] for x in lots) + sum(x.qty*x.limit for x in orders)
risk = sum(x.qty*max(0., self.prices[x.stock]-x.floor) for x in lots)
risk += sum(x.qty*max(0., x.limit-x.floor) for x in orders)
reserve = sum(x.qty*(x.limit+x.fee_per_share) for x in orders)
```

单位都是元；risk为名义到线金额，不是跳空/未成交责任或损失保证。sector筛选包含该行业所有池、旧新attempt/episode占用；没有跨行业协方差或共同跳空压力项。probe风险.5%是跨行业probe池总和。行业1%门不是全账户1%。

route的额度分母为 `nav=b.nav-pending_fees-fee`，request为同量纲的 `budget_nav=self.nav-pending_fees-qty*fee_per_share`。b.nav由当前sync的原账mark、现金/预留、应收组成；不等于初始100万元，不保证每股都有当日OPEN mark。**现金10%留存和个股10%却使用a.current_nav，即上个CLOSE的NAV**；J222更新它，OPEN无重估赋值。

| 门 | 现行实际条件 |
|---|---|
| 现金/原留存 | `cap+fee <= min(a.available-.1*a.current_nav, b.cash-reserve)` |
| probe资本 | `pc+cap <= .10*nav` |
| probe风险 | `pr+risk <= .005*nav` |
| 行业资本 | `sc+cap <= frac*nav`；probe申请frac=.02，confirmed随level取.10/.20；sc包括该行业全池和旧attempt |
| 行业风险 | `sr+risk <= .01*nav` |
| 个股资本 | `held_at_open+cap <= .10*a.current_nav`，其中held_at_open=实际股数×known_open |
| 原全账户风险门 | 原J292：`if ar+risk>.03*nav+1e-9:fails.append('account_risk')`；原request254同样`.03*budget_nav`；without-account模板已删这两处 |
| 原confirmed资本门 | 原迁池`.60*(self.nav-pending_fees)`，原request/route池资本`.60*budget_nav/nav`；component再删这三处，保留probe10% |
| ACT | 独立NAV回撤暂停与恢复状态机，仍保留；不是上述额度分母，也不是相关性模型 |

No60实际覆盖链是 `native_adapter.NoConfirmed60Budget`的request/migrate来自`component.MOD`，route为`P.ROUTES[True]`。不能把J272原route中已覆盖的3%/60%当现行门；详见 [component.py:17](</Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py:17>)、[native_adapter.py:11](</Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:11>)。

## 5. 盈新1月10—25：为什么可以在失败后继续confirmed

原六笔：68 CORE：1/10→1/11，probe100股；69 MOBILE：1/11→12 confirmed6300股；75：1/12→13 confirmed5700；78：1/13→14 confirmed4200；113：1/21→24 confirmed5100；122：1/24→25 confirmed4700。前四笔、后两笔是同一个budget episode/attempt；六笔信号前最后行业金融事件均为2022-01-07 `URFI881153/result=confirmed/financial_level=1`。

CORE即使在行业level1仍只走probe。五次MOBILE各有不同原CP ID和continuing Q，允许比较两池，实际funding明确保存`pool=confirmed/result=reserved`。由最大合法股数/平手probe规则可推知被选confirmed提供更多数量；**未保存两池候选最大q及逐股数失败门，不能断定具体是哪道probe门导致数量差**。

1/20卖掉69/75/78后还剩100股CORE；1/21新CP触发的113、1/24新CP触发的122仍在同一行业attempt获confirmed。没有“该股MOBILE止损后必须回probe”的规则。这里是MOBILE退出后再加层，不能称全股清仓重入。

原daily全账户shared_loss：1/19为28811.87150252008元、1/20为37365.253523610576元、1/21为43231.31570911908元。超过2万元仍允许后两笔，与record_only一致。此数不是盈新单股损耗/净亏，不以期末losses回填逐日行业或同股账。

1/10 CLOSE还同时保存MOBILE cap7200、预算19913.762962110280090元；次OPEN先CORE成功，`done.add(sid)`使该股MOBILE被continue跳过，没有拒单记录。1/20→21另一个MOBILE原拒`cash_or_original_reserve,sector_capital`；1/25早上先成交122，晚间行业才因`end_attempt/mobile_line`变invalidated，原level仍为1，1/25晚保存的MOBILE cap4200到1/26才被`industry_invalidated`拒绝。active与level不能互相代替。

原逐笔对象、CP/现金/行业凭证字段以及缺失说明见 [盈新原字段表](yingxin/READOUT.md)；原始六层原件见 [ORIGINAL_SIX_LAYER_CHAIN.json](../current_strategy_source_dossier_v1/yingxin_chain/ORIGINAL_SIX_LAYER_CHAIN.json)。上游`signal_industry_attempt`哈希与budget的`episode:首行业receipt`是两个命名空间，不能当同一ID。原日志没有逐reserve完整行业status/level快照、两池最大q、每道门的通过向量或当时同股/同attempt损耗桶；不以期末快照回填。

## 6. 应修改的最小执行位置：只定位，不作策略决定

- 若目标是把累计损耗变成主动新风险条件，执行政策入口在J16，损耗累计在J111/134和Contract.loss87；实际拒新在Contract.request236。**route.allowed先定量、request后断言reserved**，所以只给request加一道拒绝会使当前route末尾assert失败，必须让route预检与request执行同一判据。当前损耗为账户生命周期内的负价差和费用总和，不用盈利抵减、也无恢复；直接启用固定2万元会永久耗尽，因此还必须明确所需记忆的经济语义与恢复机制。不能只改一个字符串就宣称机制完成。
- 若目标是“同股验证后才扩张”，行业level和迁池的共同状态不足以表达它。个股MOBILE申请的最小分支在实际route8–10及request227–235；须先定义个股状态和合法新证据，再明确它如何影响pool可选性，不能把行业confirmed改名冒充股级成功验证。行业共同升级本身在industry141–150/migrate188–208。
- 若目标是改变名义风险或相关并发约束，旧仓聚合在resources106–117，新单在route.allowed15及request239，拒新在相应行业/账户门；只改旧仓risk而不改新单risk会混量纲。跨行业共同压力目前没有独立执行点，不能把已有sector1%称为该功能。

上述是代码接口定位和当前规则的具体缺口，不是新参数建议或有效性结论。本轮未修改这些位置。
