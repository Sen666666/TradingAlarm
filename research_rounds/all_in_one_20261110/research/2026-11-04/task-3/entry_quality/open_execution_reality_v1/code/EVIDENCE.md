# 现 No60：读 OPEN、定量、预留与同 OPEN 成交的真实顺序

**结论：代码确实先读取当日日线记录的raw OPEN，才确定最终可预留q/拒单；成功后在同一次opening(at)调用内，以同一at的OPEN±slip FillWindow尝试成交。没有另建一个更晚的报单/外部ACK/撮合时间。** 这是已知OPEN后同OPEN价格的零反应时间日线代理；本件不推测券商实现，不声称代码已证明真实可如此成交。

前CLOSE的信号与冻结上界仍保留；需要区分“信号decision_at”与“OPEN最后定量/预留”。代码分别存了前者和reserve的OPEN at，但没有另存定量计算结束、client send、venue received或broker ACK的细时间戳。当前No60的delay_events=0；代码虽有额外eligible-event等待计数器，其不是本路径上启用的毫秒/报单延迟模型。

本件只读源码/静态文本还原，无import策略、exec/compile模型、回测或新测试。所审是原现行No60，不是尚未接线的单位风险修订。

## 1. 最关键片段：先读本日OPEN，再定q，再在同at调用成交

[joint_v3.py:302–324](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:302)

```python
 def opening(self,a,at):
  C.activate(a)
  for sid in sorted(a.exits):
   win=self.market.window(sid,at,'sell',1)
   if win:a.fill_exit(sid,win)
  a.settle_due(at);a.sync(at);funded=[];done=set()
  for i in sorted([i for i in a.pending if i['clock'].earliest_execution_at==at],key=lambda x:(x['rank'],x['role']!='core')):
   sid=i['sid']
   if sid in done or sid in a.buys or sid in a.exits:continue
   raw=self.market.raw[sid];day=pd.Timestamp(at.date())
   if day not in raw.index or not np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='missing_open'));continue
   x,why=LR.preview(i,D(str(raw.loc[day].open)),self.facts.factor(sid,at),self.market.quantity(sid,at),self.market.fees(sid,at))
   if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
   x['known_open']=D(str(raw.loc[day].open))
   route,why=self.route(a,i,x,at)
   if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
   q,pool=route;a.reserve_quantity(i,q,x['price'],x['schedule'],at);a.sync(at);done.add(sid);funded.append((sid,i,x,q));self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='reserved',pool=pool,shares=q,price=x['price'],CP1_id=i.get('CP1_id')))
  # Execution proxies are consulted only after all H1-ranked funding decisions.
  for sid,i,x,q in funded:
   win=self.market.window(sid,at,'buy',1)
   if win:assert win.execution_price==x['price'];a.fill_buy(sid,win)
   else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='no_execution_window_after_reservation'))
  a.settle_due(at);a.sync(at);a.minimum_available=min(a.minimum_available,a.available);a.check()
```

[study.py:56–66](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:56)

```python
def preview(i,op,factor,rule,schedule):
 p=op*(ONE+SLIP);floor=i['floor']/factor;cap=i['cap'];budget=i['budget'];par=i['quote'].par_value
 if op<=floor:return None,'open_at_or_below_protection'
 def allowed(q):return D(q)*p<=budget and (i['kind']!='core' or protection_risk(q,p,floor,schedule,par)<=i['risk_budget'])
 maxq=maximum_quantity(rule,min(cap,int(budget/p)),allowed)
 if not maxq:return None,'open_minimum_exceeds_frozen_contract'
 cache={}
 def cost(q):
  if q not in cache:cache[q]=D(q)*p+fees(q,p,schedule,'buy',par)
  return cache[q]
 return dict(sid=i['sid'],i=i,price=p,floor=floor,rule=rule,schedule=schedule,maxq=maxq,minq=rule.buy_minimum,cost=cost,weight=D(str(i['weight'])),qty=0),None
```

严格顺序：旧卖单尝试→settle/sync→按冻结股票rank/角色顺序→读raw.open→preview→实际No60 route搜q→真实reserve→全部funding完成→才查各buy window→fill_buy。preview/route返回why时continue，尚未创建这笔新BuyOrder；不是已经下单后撤销。route内部可能迁池，不能把route失败说成完全无状态变化。

## 2. 确认实际route覆盖，避免误读J原3%/60%版本

[native_adapter.py:11–40](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:11)

```python
class NoConfirmed60Budget(N.BASE.NoAccountBudget):
    request=P.MOD.Contract.request
    def migrate(self,sector):
        return P.MOD.Contract.migrate(self,sector) if self.expand else False

class Runner(N.Runner):
    route=P.ROUTES[True]
    def __init__(self,*args,**kwargs):
        self._cap_bootstrap=True
        super().__init__(*args,**kwargs)
        self.remove_confirmed60=True
        for a in self.accounts.values():a.budget.__class__=NoConfirmed60Budget
        self.integration_policy=POLICY+':'+self.rank_mode
        self._cap_bootstrap=False
        self.assert_native_wiring()

    def assert_native_wiring(self):
        bootstrap=getattr(self,'_cap_bootstrap',False)
        assert self.integration_policy==(N.POLICY if bootstrap else POLICY)+':'+self.rank_mode
        assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
        assert self.opening.__func__ is J.Runner.opening
        assert self.planning.__func__ is N.Runner.planning
        assert self.route.__func__ is P.ROUTES[True]
        for a in self.accounts.values():
            assert type(a)is J.Account and type(a.budget)is (N.BASE.NoAccountBudget if bootstrap else NoConfirmed60Budget)
            if not bootstrap:
                assert a.budget.request.__func__ is P.MOD.Contract.request
                assert a.budget.migrate.__func__ is NoConfirmed60Budget.migrate
            for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                assert getattr(a,name).__func__ is getattr(J.Account,name)
```

[component.py:17–34](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py:17)

```python
MODEL=(W/'account-risk-ablation-20261031/model_without_account_check.py').read_text()
ROUTE=(W/'account-risk-ablation-20261031/route_without_account_check.py').read_text()
assert inspect.getsource(N.Contract.migrate)==inspect.getsource(J.V.Contract.migrate)
MG="        if self.resources('confirmed')[0] + moved > .60*(self.nav-pending_fees) + 1e-9:\n            s.status = 'confirmed_unfunded'\n            return False\n"
PG="        if pc+cap > (0.10 if pool == 'probe' else 0.60)*budget_nav + 1e-9: failures.append('pool_capital')"
PN="        if pool == 'probe' and pc+cap > 0.10*budget_nav + 1e-9: failures.append('pool_capital')"
RG="    if pc+cap>(.10 if pool=='probe' else .60)*nav+1e-9:fails.append('pool_capital')"
RN="    if pool=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')"
assert MODEL.count(MG)==MODEL.count(PG)==ROUTE.count(RG)==1
NEW_MODEL=MODEL.replace(MG,'').replace(PG,PN)
NEW_ROUTE=ROUTE.replace(RG,RN)
assert NEW_MODEL.replace(PN,PG).replace('        before = (self.cash, self.nav, self.resources(), self.shared_loss)',MG+'        before = (self.cash, self.nav, self.resources(), self.shared_loss)')==MODEL
assert NEW_ROUTE.replace(RN,RG)==ROUTE
MOD=ModuleType('pvr_private_no_confirmed60_model');sys.modules[MOD.__name__]=MOD
exec(compile(NEW_MODEL,str(O/'derived_model_no_confirmed60.py'),'exec'),MOD.__dict__)
ROUTES={}
for flag,source in [(False,ROUTE),(True,NEW_ROUTE)]:
    env=dict(J.__dict__);exec(compile(source,str(O/('derived_route_on.py' if flag else 'derived_route_off.py')),'exec'),env);ROUTES[flag]=env['route']
```

A.route=P.ROUTES[True]；P读取without_account_check模板（已去account3%）并移除route confirmed60%。以下是按原唯一replace静态还原的实际route字符串；本次未执行它。

[EFFECTIVE_NO60_ROUTE.txt:1–29](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/open_execution_reality_v1/code/EFFECTIVE_NO60_ROUTE.txt:1)

```python
def route(self,a,i,x,at):
  b=a.budget;sid=i['sid'];sector=self.sector_by_sid[sid];s=b.sectors.get(sector);bar=ordinal(i['clock'].decision_at.date());role=i['role'];p=float(x['price']);floor=float(x['floor']);rule=x['rule'];maxq=x['maxq'];rid=i.get('CP1_id');token=None
  if not s or not s.active:return None,'industry_invalidated'
  if role=='mobile':
   cp=i['CP1_trace'];token=V.Evidence(rid,sector,'stock_cp1','21',ordinal(cp['formation_start_exclusive']),bar,bar,s.episode,sid,s.attempt)
   if not b.valid(token,'stock_cp1',bar) or rid in b.consumed:return None,'no_fresh_stock_CP1'
  assert not getattr(a,'_budget_sync_pending',False),'cannot admit during unacknowledged ledger callback'
  routes=['probe']
  if role=='mobile' and b.expand and s.level>0:
   if b.migrate(sector):a.pools_from_model();routes.append('confirmed')
  results=[];reasons={}
  for pool in routes:
   pc,pr,_=b.resources(pool);sc,sr,_=b.resources(sector=sector);_,ar,reserve=b.resources();pending_fees=sum(o.qty*o.fee_per_share for o in b.orders.values() if o.status in ['open','cancel_pending']);frac=.02 if pool=='probe' else (.02,.1,.2)[s.level]
   def allowed(q,detail=False):
    fee=float(LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value));nav=b.nav-pending_fees-fee;cap=q*p;risk=q*max(0.,p-floor);fails=[]
    if cap+fee>min(float(a.available-a.current_nav*D('.1')),b.cash-reserve)+1e-9:fails.append('cash_or_original_reserve')
    if pool=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')
    if pool=='probe' and pr+risk>.005*nav+1e-9:fails.append('probe_risk')
    if sc+cap>frac*nav+1e-9:fails.append('sector_capital')
    if sr+risk>.01*nav+1e-9:fails.append('sector_risk')
    known_open=x.get('known_open',x['price']/(D(1)+LR.SLIP));held_at_open=float(a.quantity(sid))*float(known_open)
    if held_at_open+cap>.10*float(a.current_nav)+1e-9:fails.append('stock_capital')
    return fails if detail else not fails
   q=LR.maximum_quantity(rule,maxq,allowed);results.append((q,pool));reasons[pool]=allowed(rule.buy_minimum,True)
  # Maximum legal quantity, probe wins a tie. No split order or speculative consume.
  q,pool=max(results,key=lambda z:(z[0],z[1]=='probe'))
  if not q:return None,','.join(sorted(set(sum(reasons.values(),[])))) or 'minimum_unit_not_funded'
  bid=f"{a.label}|{i['clock'].decision_at.isoformat()}|{sid}|{role}";fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value);result=b.request(bid,sid,sector,q,p,floor,token,bar,float(fee/D(q)),probe_request=pool=='probe',role=role,order_expiry_bar=ordinal(at.date()),core_epoch_locked=role=='core' and a.core_epoch.get(sid)==i['epoch']);assert result=='reserved',(bid,result,reasons)
  i.update(budget_order=bid,pool=pool);return(q,pool),None
```

route最终q确定后才b.request；reserved后再走a.reserve_quantity。预算request中的bar来自前CLOSE decision日期，不是OPEN报单时刻。预算Order与真实BuyOrder是两个表示，不能把budget created_bar当实际submission time。以下模板片段没有被No60三处replace改动：

[model_without_account_check.py:210–239](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py:210)

```python
    def request(self, oid, stock, sector, qty, limit, floor, stock_token=None,
                bar=0, fee_per_share=0., *, probe_request=False, role='core',
                order_expiry_bar=None,
                core_epoch_locked=False):
        assert qty > 0 and limit > 0 and 0 <= floor <= limit and fee_per_share >= 0
        assert role in ('core', 'mobile')
        if order_expiry_bar is None: order_expiry_bar = bar
        assert order_expiry_bar >= bar
        if oid in self.orders or oid in self.stock_requests:
            return 'duplicate_request'
        self.stock_requests.add(oid)  # Failed request is not silently replayed every day.
        s = self.sectors[sector]
        if not s.active: return 'industry_invalidated'
        if probe_request and role == 'core' and core_epoch_locked: return 'core_epoch_locked'
        pool = 'probe' if probe_request else 'confirmed'
        if not probe_request and s.level == 0: return 'explicit_probe_request_required'
        if not probe_request and role != 'mobile': return 'mobile_role_required'
        if role == 'mobile':
            if stock_token is None:
                return 'no_fresh_stock_signal'
            if not self.valid(stock_token, 'stock_cp1', bar) or stock_token.confirmed_time != bar or stock_token.sector != sector or stock_token.stock != stock or stock_token.event_id in self.consumed:
                return 'no_fresh_stock_signal'
            self.consumed.add(stock_token.event_id)
        if pool == 'confirmed':
            if not self.migrate(sector):
                return 'confirmed_unfunded'
        if self.exhausted_policy != 'record_only' and self.shared_loss >= self.loss_budget and (pool == 'probe' or self.exhausted_policy == 'all_new_risk'):
            if pool == 'confirmed': s.status = 'confirmed_unfunded'
            return 'shared_loss_exhausted'
        cap, risk = qty*limit, qty*(limit-floor)
```

[model_without_account_check.py:257–262](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py:257)

```python
        self.prices.setdefault(stock, limit)
        self.orders[oid] = Order(oid, stock, sector, s.episode, pool, qty, limit, floor, fee_per_share)
        self.orders[oid].role = role
        self.orders[oid].created_bar, self.orders[oid].expiry_bar = bar, order_expiry_bar
        self.orders[oid].attempt = s.attempt
        return 'reserved'
```

## 3. 同一at建订单与锁现金，但created_at写的是前CLOSE

[study.py:94–103](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:94)

```python
 def reserve_quantity(self,i,q,p,schedule,at):
  """Lock known-open cash under a past frozen contract; execution stays in old ledger."""
  sid=i['sid'];clock=i['clock'];quote=i['quote'];gross=D(q)*p;fee=fees(q,p,schedule,'buy',quote.par_value);quote.read_price(clock.decision_at);self._time(at)
  assert clock.decision_at<at and clock.earliest_execution_at==at
  assert 0<q<=i['cap'] and gross<=i['budget'] and gross+fee<=self.available
  assert sid not in self.buys and sid not in self.exits
  oid=self._id('buy',sid);order=L.BuyOrder(oid,quote,clock.decision_at,clock.earliest_execution_at,i['budget'],gross,fee,q,q,0,'annual_rebalance');order.candidate_id='LR1:'+i['reason'];self.buys[sid]=order;self.available-=gross+fee;self.order_meta[oid]=i
  self.audit_log.append(dict(kind='reserve',at=at,decision_at=clock.decision_at,sid=sid,order_id=oid,gross_budget_cny=gross,fee_reserved_cny=fee,target_shares=q,purpose='annual_rebalance',candidate_id=order.candidate_id,quote_source=quote.source_id,fee_schedule=schedule.schedule_id,frozen_max_shares=i['cap'],frozen_max_gross=i['budget'],known_open_funding=True))
  self.log('lot_risk_funded',at,sid=sid,order_id=oid,layer_kind=i['kind'],signal_at=clock.decision_at,shares=q,gross=gross,fees=fee,risk_budget=i.get('risk_budget'),floor=i['floor'])
  return oid
```

[joint_v3.py:101–103](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:101)

```python
 def reserve_quantity(self,i,q,p,schedule,at):
  bid=i['budget_order'];assert self.budget.orders[bid].qty==q
  oid=super().reserve_quantity(i,q,p,schedule,at);self.order_bridge[oid]=bid;self.journal.append(dict(kind='real_reserve',at=at,sid=i['sid'],order=oid,budget_order=bid,receipt=i.get('CP1_id'),pool=i['pool'],role=i['role'],shares=q,price=p));return oid
```

[sector_account.py:226–245](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:226)

```python
@dataclass
class BuyOrder:
    order_id: str
    quote: DecisionQuote
    created_at: datetime
    earliest_at: datetime
    budget_cny: Decimal
    remaining_budget_cny: Decimal
    fee_reserved_cny: Decimal
    target_shares: int
    remaining_shares: int
    delay_remaining: int
    purpose: str
    candidate_id: str = ''
    filled_shares: int = 0
    local_notional: Decimal = ZERO
    fees_local: dict[str, Decimal] = field(default_factory=dict)
    fee_accrued_local: dict[str, Decimal] = field(default_factory=dict)
    paused: bool = False
    submitted_remaining: int = 0
```

| 字段 | 实际写入 | 能说明什么 |
|---|---|---|
| BuyOrder.created_at | clock.decision_at（前CLOSE） | 信号来源时间；对象在OPEN函数中才创建，不能据此说前CLOSE已外部提交 |
| BuyOrder.earliest_at | clock.earliest_execution_at（本次OPEN at） | 最早允许成交时钟 |
| audit reserve.at / journal real_reserve.at | 传入的OPEN at | 真实资金预留/定量结果在该OPEN记录 |
| audit reserve.decision_at / lot_risk_funded.signal_at | 前CLOSE | 保留信号与预留时间的区别 |
| known_open_funding | True | 原日志明确标识用了已知OPEN资助 |
| target_shares / shares / gross / fee | OPEN最终q与金额 | 不是仅照抄前CLOSE上界 |
| FillReceipt.at | window.at | 若本次成交，就是同一OPEN at |
| submitted_remaining | fill_buy内生成/扣减的数量 | 无submitted_at/ack_at细时钟，不是外部ACK记录 |

## 4. 同OPEN的FillWindow价格和事后日线可成交代理

[fast_market.py:45–66](/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py:45)

```python
 def window(self,sid,at,side,cost_multiplier):
  self._cache(at);key=(sid,side,cost_multiplier)
  if key in self.wc:return self.wc[key]
  self.wc[key]=None;market=self.lines[sid].market
  if at not in self.sessions_set[market]:return None
  try:self.source_available(sid,at)
  except RuleUnavailable:return None
  a=self.arr[sid];day=pd.Timestamp(at.date()).value//86400000000000;p=np.searchsorted(a['days'],day)
  if p>=len(a['days']) or a['days'][p]!=day or not a['valid'][p] or not np.isfinite(a['volume'][p]) or a['volume'][p]<=0:return None
  j=np.searchsorted(a['positive'],p)
  if j<20:return None
  try:
   market_identity_on(self.rules,sid,at.date(),self.protocol['approved_proxy_ids']);availability=self._version('availability_versions',sid,at);buy,sell=availability.get('buy_allowed'),availability.get('sell_allowed');policy=self.protocol['daily_execution'][market]
   assert policy['price_limit_policy']=='conservative_hl_proxy'
   if policy['reject_flat_day'] and a['high'][p]<=a['low'][p]:buy=sell=False
   prior=a['volume'][a['positive'][j-20:j]];capacity=int(min(prior.mean()*float(self.protocol['participation_rate']),a['volume'][p]));slip=D(policy['slippage_bps'])/10000
   if cost_multiplier==2 and policy['stress_slippage']:slip*=2
   op=D(str(a['open'][p]));price=op*(1+slip if side=='buy' else 1-slip)
   w=ledger.FillWindow(f'{sid}:{at.isoformat()}:{side}',sid,at,op,price,self.rate('CNY',at),self.quantity(sid,at),self.fees(sid,at),capacity,True,buy,sell,self.lag(market,at,self.protocol['sellable_lag_sessions'][market]),self.lag(market,at,self.protocol['settlement_lag_sessions'][market]),self.bundle.series[sid].record['raw']['sha256'],'explicit_daily_bar_proxy_past20_capacity_same_day_hlv_postcheck',self.rules.get('security_metadata',{}).get(sid,{}).get('par_value'))
  except RuleUnavailable:return None
  if key not in self.window_verified:
   assert w==super().window(sid,at,side,cost_multiplier),(sid,at,'window identity');self.window_identity_checks+=1;self.window_verified.add(key)
```

[sector_account.py:196–223](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:196)

```python
@dataclass(frozen=True)
class FillWindow:
    event_id: str
    security_id: str
    at: datetime
    raw_open: Decimal
    execution_price: Decimal  # Explicit protocol slippage already applied.
    fx: FXQuote
    quantity: QuantityRule
    fees: FeeSchedule
    capacity_shares: int
    market_open: bool | None
    buy_allowed: bool | None
    sell_allowed: bool | None
    sellable_at: datetime
    cash_due_at: datetime
    source_id: str
    execution_basis: str  # e.g. observed_open or explicit_daily_bar_proxy.
    par_value: Decimal | None = None

    def validate(self):
        for t in (self.at, self.sellable_at, self.cash_due_at):
            aware(t)
        if (not self.event_id or not self.source_id or not self.execution_basis
                or type(self.capacity_shares) is not int or self.capacity_shares < 0
                or self.sellable_at < self.at or self.cash_due_at < self.at):
            raise ValueError('Invalid execution event/availability/settlement facts')
        positive(self.raw_open); positive(self.execution_price); self.fx.read(self.at)
```

FastMarket的price=raw_open*(1±slip)，window.at就是调用的at；J322断言它与preview价格完全相同。容量=min(过去20正量均值×参与率,执行日完整volume)，同日high<=low可禁买卖。因此后半段使用执行日H/L/V postcheck；这些不是OPEN前已知字段，但当前模型将这一日线成交可行性代理写到OPEN事件。它们在funding之后调用，不改变之前q，却影响是否/多少fill。不能把这个代理称为交易所实际逐笔成交或已建模的下单队列。

## 5. ledger为什么允许刚reserve就在同at fill

[sector_account.py:666–744](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:666)

```python
    def _eligible_event(self, order, window: FillWindow, side):
        window.validate(); self._time(window.at)
        earliest = order.earliest_at
        if window.security_id != order.quote.security_id:
            raise ValueError('Order and execution security mismatch')
        if order.quote.currency == 'CNY' and dec(window.fx.cny_per_local) != ONE:
            raise ValueError('CNY execution FX must equal one')
        if window.at < earliest or window.market_open is not True:
            return False
        return (window.buy_allowed if side == 'buy' else window.sell_allowed) is True

    def _consume_event(self, order, window):
        identity = order.order_id if isinstance(order, BuyOrder) else order.event_id
        key = identity, window.event_id
        if key in self.used_events:
            return False
        self.used_events.add(key)
        if order.delay_remaining:
            order.delay_remaining -= 1
            return False
        return True

    def fill_buy(self, sid, window: FillWindow) -> FillReceipt | None:
        order = self.buys.get(sid)
        if order is None or order.paused or not self._eligible_event(order, window, 'buy'):
            return None
        price, fx = dec(window.execution_price), window.fx.read(window.at)
        cap = min(order.remaining_shares, int(order.remaining_budget_cny/(price*fx)))
        # The original order satisfied buy_minimum. Its continuing partial fills
        # obey explicit matching granularity, not a fresh minimum on every fill.
        step = window.quantity.fill_step
        low, high = 0, cap//step
        while low < high:
            mid = (low+high+1)//2
            costs = self._fee(order, window.fees, 'buy', mid*step*price,
                              shares=mid*step, par_value=window.par_value)
            if sum(costs.values(), ZERO)*fx <= order.fee_reserved_cny+self.available:
                low = mid
            else:
                high = mid-1
        affordable = low*step
        # First actual submission must still satisfy today's order minimum after
        # a gap. A committed partial remainder then uses fill granularity only.
        submitted = (order.submitted_remaining if order.submitted_remaining
                     else window.quantity.buy_floor(affordable))
        count = min(submitted, affordable, window.capacity_shares)//step*step
        if not count or not self._consume_event(order, window):
            return None
        local = count*price
        components = self._fee(order, window.fees, 'buy', local, shares=count, par_value=window.par_value)
        fee = sum(components.values(), ZERO)*fx
        gross = local*fx
        topup = max(ZERO, fee-order.fee_reserved_cny)
        self.available -= topup
        order.fee_reserved_cny += topup-fee
        order.remaining_budget_cny -= gross
        order.remaining_shares -= count
        order.submitted_remaining = submitted-count
        order.filled_shares += count
        self._remember_fees(order, window.fees, 'buy', local, components,
                           shares=count, par_value=window.par_value)
        pos = self.positions.setdefault(sid, Position(sid, order.quote.issuer_id,
                              order.quote.sector_id, order.quote.currency))
        pos.lots.append(InventoryLot(count, window.sellable_at))
        settlement_id = self._id('pay', sid)
        self.settlements[settlement_id] = Settlement(settlement_id, gross+fee, True,
                        window.cash_due_at, local+sum(components.values(), ZERO), fx, window.fx.source_id)
        receipt = FillReceipt(self._id('fill', sid), sid, 'buy', count, gross, fee, window.at,
                               settlement_id, window.execution_basis)
        self.fills.append(receipt); self.fees_cny += fee
        self.audit_log.append(dict(kind='fill', receipt=receipt, order_id=order.order_id,
                                  raw_open=window.raw_open, price=price, fx_rate=fx,
                                  fx_source=window.fx.source_id, source=window.source_id,
                                  fee_schedule=window.fees.schedule_id, fee_components=components,
                                  gross_budget_remaining=order.remaining_budget_cny,
                                  share_cap_remaining=order.remaining_shares))
        if not order.remaining_shares or not order.remaining_budget_cny:
            self.cancel_buy(sid)
        return receipt
```

[sector_account.py:408–412](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:408)

```python
    def _time(self, at):
        aware(at)
        if self.as_of is not None and at < self.as_of:
            raise ValueError('Account events cannot run backwards')
        self.as_of = at
```

_eligible_event只拒window.at<order.earliest_at，等号允许；_time只拒倒退，也允许同at连续状态改变。submitted数量在fill_buy中计算，接着按capacity取count、扣预算、建库存/receipt；没有在这两步之间安排新的事件。实际count可能小于reserve q或为0，不意味着每单一定成交。

## 6. 当前No60确实delay=0；可选计数器不是网络/撮合延迟

[joint_v3.py:29–31](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:29)

```python
class Account(C.Account):
 def __init__(self,name,market,facts,expand,sector_by_sid):
  super().__init__(name,market,facts,False,1,0);self.budget=Budget(expand);self.sector_by_sid=sector_by_sid;self.jmeta={};self.order_bridge={};self.journal=[];self.sync_rows=[];self.budget_at=None
```

[adapter.py:37–40](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/lr1-cp1-add-preflight-20261031/adapter.py:37)

```python
class Account(LR.Account):
 def __init__(self,name,market,facts,add_enabled=False,cost=1,delay=0):
  super().__init__('P0',market,facts);self.label=name;self.mode='ACT';self.add_enabled=add_enabled
  self.cost_multiplier=cost;self.delay_events=delay;self.cp_used=set();self.add_credits={};self.waited_orders=set();self.layer_structures={};self.risk_rows=[];self.ops=[];self.verify_index=False;self.group_layers=collections.defaultdict(list);self.structure_risk={}
```

[adapter.py:72–80](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/lr1-cp1-add-preflight-20261031/adapter.py:72)

```python
 def reserve_quantity(self,i,q,p,schedule,at):
  activate(self);oid=super().reserve_quantity(i,q,p,schedule,at);order=self.buys[i['sid']]
  order.delay_remaining=self.delay_events
  if i['kind']=='core' and i['sid'] in self.daily_delay_credit:order.delay_remaining=0
  if i['kind']=='add':
   c=self.add_credits.get(i['sid']);k=self.cp_key(i['sid'],i['clock'].decision_at,i['epoch'])
   if c and c['at']==i['clock'].decision_at and c['key']==self.credit_key(i['sid'],i['epoch']) and k in self.cp_used:
    order.delay_remaining=0;self.add_credits.pop(i['sid'],None)
    self.ops.append(dict(kind='ADD_credit_consumed',at=at,sid=i['sid'],from_order=c['order'],to_order=oid,signal_at=i['clock'].decision_at))
```

J.Account向C.Account传入False,1,0；最后0对应delay。C.reserve将order.delay_remaining设为self.delay_events，故当前为0。ledger _consume_event虽然能跳过若干eligible event，但当前不启用等待；没有模拟读到最终OPEN后计算/发送/接收/确认所需的正时间。

## 7. 拒绝、零成交和真正取消分别发生在哪里

| 情况 | 是否已有本次真实BuyOrder | 原代码动作 |
|---|---|---|
| 缺raw OPEN / preview floor或最小手失败 | 否 | J312/314记why并continue；不是cancel |
| route无法fund/资格不符 | 否（本次） | J317记why；可能已有预算迁池状态变化，但不reserve新BuyOrder |
| reserve成功但buy window=None | 是 | J323只记no_execution_window_after_reservation；不在此处立即撤单/释放给后排 |
| 有window但ledger count=0或不可买 | 是 | fill_buy返回None，持有预留直至原expiry/cancel路径 |
| pilot.fill_buy再次发现OPEN≤保护 | 是 | 明确调用cancel_buy；这是已预留后的撤单分支，勿混为preview拒绝 |
| 完整fill后残余reserve | 已成交、可能有余款 | 原cancel_buy及J deferred ACK桥处理，不删除真实lot |
| 当日CLOSE one-session expiry | 尚有订单/partial余量 | expire_day_buys→cancel_buy，释放仅真实剩余，partial已买保持 |

[pilot.py:59–73](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:59)

```python
 def fill_buy(self,sid,w):
  order=self.buys.get(sid)
  if order is None:return
  meta=self.order_meta[order.order_id];f=self.facts.factor(sid,w.at)
  if w.raw_open*f<=meta['floor']:
   self.counts['open_at_or_below_protection']+=1;self.log('pilot_buy_rejected',w.at,sid=sid,reason='open_at_or_below_protection',intent=meta);self.cancel_buy(sid);return
  receipt=super().fill_buy(sid,w)
  if receipt:
   self.layer_seq+=1
   z=dict(id=self.layer_seq,sid=sid,kind=meta['kind'],qty=receipt.shares,initial_qty=receipt.shares,opened=w.at,signal_at=meta['clock'].decision_at,epoch=meta['epoch'],floor=meta['floor'],cash=-receipt.gross_cny-receipt.fees_cny,dividend=ZERO,closed=None,reason=None)
   self.layers.append(z);self.last_buy[sid]=w.execution_price*f
   if z['kind']=='core':self.core_epoch[sid]=meta['epoch']
   self.trades.append(dict(**asdict(receipt),layer=z['id'],kind=z['kind'],signal_at=z['signal_at'],raw_open=w.raw_open,price=w.execution_price,floor=meta['floor'],pvr=meta['score'],reason=meta['reason'],epoch=meta['epoch']))
   self.counts['buy_fills']+=1
  self.check();return receipt
```

[sector_account.py:537–568](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:537)

```python
    def expire_day_buys(self, at):
        """End the one-session order lease, including days without a stock bar.

        Return only zero-fill attempts to re-arm. Partly bought shares stay held.
        Stress delay credit conveys waiting already spent, no capital or priority.
        """
        self._time(at)
        self.daily_delay_credit = set()
        unfilled = []
        for sid, order in tuple(self.buys.items()):
            if at.date() < order.earliest_at.date():
                continue
            if not order.filled_shares and not self.quantity(sid):
                unfilled.append(sid)
                if self.delay_events and not order.delay_remaining:
                    self.daily_delay_credit.add(sid)
            self.audit_log.append(dict(kind='buy_day_expiry', at=at, sid=sid,
                order_id=order.order_id, created_at=order.created_at,
                valid_session=order.earliest_at.date().isoformat(),
                filled_shares=order.filled_shares, rearm=sid in unfilled,
                delay_credit=sid in self.daily_delay_credit))
            self.cancel_buy(sid)
        return set(unfilled)

    def cancel_buy(self, sid):
        order = self.buys.pop(sid, None)
        if order:
            self.available += order.remaining_budget_cny+order.fee_reserved_cny
            self.audit_log.append(dict(kind='release_buy', at=self.as_of, sid=sid,
                                      order_id=order.order_id,
                                      gross_released=order.remaining_budget_cny,
                                      fee_released=order.fee_reserved_cny))
```

[joint_v3.py:213–222](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)

```python
 def planning(self,at):
  clock,stocks,sectors=self.facts.packet(at,'I');sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};buyable=self.market.market_buyable(at);day=pd.Timestamp(at.date());event={};continuing={}
  for sid,s in sd.items():
   row=self.facts.row(sid,at);key=(bool(row.i_target),int(row.segment_id)) if row is not None else (False,-1)
   if self.last_epoch.get(sid)!=key:self.epoch[sid]+=1;self.global_watch.pop(sid,None);self.last_epoch[sid]=key
   ep=(key[1],self.epoch[sid]);event[sid]=BP.A.eligibility(s,ss,clock,'S0');continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
   if event[sid].q is True:self.global_watch[sid]=ep
  ordered=sorted(sd,key=lambda sid:(-(sd[sid].rank.read(clock) if sd[sid].rank and sd[sid].rank.read(clock) is not None else -1),sid))
  for a in self.accounts.values():
   C.activate(a);a.expire_day_buys(at);a.current_nav=a.balance(at,self.market.marks(at,a.positions))['nav'];M.E.risk_policy.step(a,at,'ACT20_BREAK');a.pending=[]
```

[joint_v3.py:92–128](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:92)

```python
 def cancel_buy(self,sid):
  real=self.buys.get(sid);bid=self.order_bridge.get(real.order_id) if real else None
  if getattr(self,'_buy_filling',None)==sid:
   if bid:self._deferred_buy_cancels.append(bid)
   return super().cancel_buy(sid)
  if bid:self.budget.cancel(bid)
  result=super().cancel_buy(sid)
  if bid:self.budget.cancel_ack(bid);self.pools_from_model();self.journal.append(dict(kind='cancel_ack',at=self.as_of,sid=sid,budget_order=bid))
  return result
 def reserve_quantity(self,i,q,p,schedule,at):
  bid=i['budget_order'];assert self.budget.orders[bid].qty==q
  oid=super().reserve_quantity(i,q,p,schedule,at);self.order_bridge[oid]=bid;self.journal.append(dict(kind='real_reserve',at=at,sid=i['sid'],order=oid,budget_order=bid,receipt=i.get('CP1_id'),pool=i['pool'],role=i['role'],shares=q,price=p));return oid
 def fill_buy(self,sid,w):
  real=self.buys.get(sid);i=self.order_meta[real.order_id] if real else None;bid=self.order_bridge.get(real.order_id) if real else None;self._buy_filling=sid;self._deferred_buy_cancels=[]
  try:r=super().fill_buy(sid,w)
  finally:self._buy_filling=None
  if r:
   bo=self.budget.orders[bid];price=float(r.gross_cny/D(r.shares));floor=float(i['floor']/self.facts.factor(sid,w.at));assert price<=bo.limit+1e-8
   x=self.layers[-1];self.jmeta[x['id']]=dict(sector=bo.sector,episode=bo.episode,pool=bo.pool,role=bo.role,attempt=bo.attempt,unit_cost=price,last_core_line=str(i['floor']),stock_structure=getattr(self.facts,'structure_lookup',{}).get(sid,{}).get(i['clock'].decision_at.date()),budget_order=bid)
   self.budget.loss(bo.sector,bo.episode,float(r.fees_cny))
   bo.qty-=r.shares
   if not bo.qty:bo.status='filled'
   elif sid in self.buys:
    # The real partial fill has consumed principal and incremental fee once.
    # Update only this actual order callback; generic sync asserts the bridge.
    remaining=self.buys[sid]
    assert bo.qty==remaining.remaining_shares
    bo.limit=float(remaining.remaining_budget_cny/D(bo.qty))
    bo.fee_per_share=float(remaining.fee_reserved_cny/D(bo.qty))
   self.journal.append(dict(kind='real_buy_fill',at=w.at,sid=sid,layer=x['id'],budget_order=bid,shares=r.shares,price=r.gross_cny/D(r.shares),fees=r.fees_cny,pool=bo.pool,role=bo.role,attempt=bo.attempt,signal_at=i['clock'].decision_at,CP1_id=i.get('CP1_id')))
  if r:self.sync(w.at,pending_ack=bool(self._deferred_buy_cancels))  # Actual lot/NAV first; no admission until ack.
  # Native full fills call cancel_buy internally to return residual reserve.
  # Mirror the actual fill first, then acknowledge only the actual remainder.
  for cancelled in self._deferred_buy_cancels:
   if self.budget.orders[cancelled].qty:self.budget.cancel(cancelled)
   self.budget.cancel_ack(cancelled);self.pools_from_model()
  self.sync(w.at)
```

[model_without_account_check.py:174–186](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py:174)

```python
    def cancel(self, oid):
        o = self.orders[oid]
        if o.qty > 0 and o.status == 'open':
            o.status = 'cancel_pending'

    def cancel_ack(self, oid):
        o = self.orders[oid]
        if o.status in ('filled', 'cancelled') and o.qty == 0:
            self.migrate(o.sector)  # Full fill can win the cancel race; never erase the lot.
            return
        assert o.status == 'cancel_pending'
        o.qty, o.status = 0., 'cancelled'
        self.migrate(o.sector)
```

J.cancel_buy里的budget.cancel→native cancel→budget.cancel_ack在同一同步调用中完成；actual fill期间的deferred ACK也在同一w.at回调内完成。_budget_sync_pending是内部镜像/真实账一致性屏障，不是有外部接收/确认时间的broker ACK模型。没有回报时延/撤单排队模型；流动性导致的未成交、T+1和settlement各自保留原含义。

## 8. 前CLOSE与OPEN确是不同离散事件；OPEN内部没有子时钟

[launch_v3.py:82–104](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/launch_v3.py:82)

```python
 def run_prepared(self,out,max_seconds,resume_after=None,end=None):
  # Original M.Pilot.run event construction/order. The only clock difference
  # is a strict skip of already completed checkpoint events on explicit resume.
  from datetime import datetime,time as dt
  end=end or J.END
  start=J.M.N.iso(J.START+'T15:10:00+08:00');finish=J.M.N.iso(end+'T15:10:00+08:00')
  cutoffs={x for x in self.market.cutoffs if start<=x<=finish};opens={x for x in self.market.sessions['A'] if start<=x<=finish}
  acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ) for d in self.actions_by_date}
  events=sorted(cutoffs|opens|{x for x in acts if start<=x<=finish});assert finish in cutoffs
  J.M.E.risk_policy.RECOVERY=pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:end]
  t=time.monotonic();last=resume_after
  for at in events:
   if resume_after is not None and at<=resume_after:continue
   if time.monotonic()-t>max_seconds:
    if last is not None:self.checkpoint(out,last)
    self.dump_joint(Path(out)/'partial');return False
   for a in self.accounts.values():a.settle_due(at)
   self._actions(at)
   for a in self.accounts.values():self._payments(a,at)
   if at in opens:
    for a in self.accounts.values():self.opening(a,at)
   if at in cutoffs:self.planning(at)
   last=at
```

[engine.py:31–36](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py:31)

```python
 def packet(self,at,mode):
  p=policy(mode)
  if self.day!=at:self.day=at;self.cache={}
  if p in self.cache:return self.cache[p]
  clock=admission.Clock(at,self.market.sessions['A'][bisect_right(self.market.sessions['A'],at)],at.date())
  inputs=self.b.at_decision(clock,market_buyable=self.market.market_buyable(at));stocks=[]
```

[sector_stock_admission.py:23–35](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py:23)

```python

@dataclass(frozen=True)
class Clock:
    decision_at: datetime
    earliest_execution_at: datetime
    session_date: date

    def __post_init__(self):
        _aware(self.decision_at)
        _aware(self.earliest_execution_at)
        if self.earliest_execution_at <= self.decision_at:
            raise ValueError('Execution must be strictly after the decision cutoff')
        if self.session_date > self.decision_at.date():
```

run_prepared的事件集合是cutoff/OPEN/公司行动；at在opens则一次调用opening，在cutoffs则planning。Clock要求earliest_execution_at>decision_at，只保证前CLOSE→后OPEN，不保证OPEN看价后再发送的正延迟。这里未发现一条单独submission/ACK事件插在known-open sizing与同OPEN fill之间。

**能得出的结论止于源码：当前回测采用了“前CLOSE出信号、下一OPEN最终看价定量/拒单、同OPEN±固定slip且经日线postcheck成交”的模型。其真实执行影响大小未测，不能从本次只读审查补出券商订单类型、延迟或收益修正。**
