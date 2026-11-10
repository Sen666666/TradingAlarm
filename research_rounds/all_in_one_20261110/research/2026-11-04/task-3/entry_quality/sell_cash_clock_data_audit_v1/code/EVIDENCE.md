# 当日卖出日线代理 → 同OPEN回款 → 买入资助：源码证据

**结论：这条反馈通道在现No60代码中成立。不是把未成交卖单直接当现金，而是先按当日H/L/V卖出代理生成fill receipt和due-at同OPEN的settlement；settle_due把净款写入原账available，再同步Budget.cash供新买route使用。** 同时，当日最终high/low/总volume在真实OPEN尚不可知，源行没有它们的独立公布/接收时间。买自身的H/L/V确实在全部funding之后查询，卖的H/L/V却在funding之前；两者不能混说。

本件仅只读真实代码/原book audit、现有cash bridge及一行已存raw bar，不调用window、不重放策略、不计算取消卖款后的反事实资金/q/收益；0模型、0账户、0回测、0新测试。

## 1. 严格调用顺序：J.opening

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

`304–306`旧退出先查sell window并fill → `307`settle_due+sync → `313–318`买preview/route/reserve → `319–322`全部买资金已预留后才查buy window/fill。这些调用传同一个OPEN at；不是新建更晚的收款/资助事件。

## 2. 卖window读执行日完整H/L/V；source_available不检逐字段收报时钟

实际继承链由 common.py 导入IX的multi_runner.FrozenMarket：

[common.py:6–11](/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/common.py:6)

```python
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
OLD=ROOT/'research_rounds/rs-h1-execution-20261025';IX=ROOT/'research_rounds/ix-a-share-entry-20261025';PREV=ROOT/'research_rounds/unlimited-capital-20261026'
for p in [OLD/'code',IX/'code',PREV/'code']:sys.path.append(str(p))
import multi_runner as native
import sector_account as ledger
import sector_stock_admission as admission
```

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

[multi_runner.py:145–152](/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/code/multi_runner.py:145)

```python
    def source_available(self, sid, at):
        record = self.bundle.series[sid].record
        day = at.astimezone(TZ).date().isoformat()
        if record.get('unavailable_from') and day >= record['unavailable_from']:
            raise RuleUnavailable('Declared source unavailable from '+record['unavailable_from']+': '+sid)
        parts = record.get('segments', ())
        if any(left['end'] < day < right['start'] for left, right in zip(parts, parts[1:])):
            raise RuleUnavailable('Declared source discontinuity: '+sid)
```

53用当日完整volume有效性，59用当日high/low决定buy/sell_allowed，60用当日完整volume截容量；side='sell'也经过这些代码。62以当日OPEN−slip定卖价。source_available只查来源不可用日期/来源段断裂，不核H/L/V各字段何时在该OPEN前被收到。

## 3. sell fill先生成应收，未直接增加正净款available

[sector_account.py:746–797](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:746)

```python
    def fill_exit(self, sid, window: FillWindow) -> FillReceipt | None:
        order = self.exits.get(sid)
        if order is None or not self._eligible_event(order, window, 'sell'):
            return None
        pos = self.positions[sid]
        available = sum(lot.shares for lot in pos.lots if lot.sellable_at <= window.at)
        target = pos.shares if order.remaining_target is None else order.remaining_target
        available = min(available, target)
        additional_available = max(0, available-order.submitted_remaining)
        additional_order = window.quantity.sell_floor(additional_available,
                                                       pos.shares-order.submitted_remaining)
        submitted = order.submitted_remaining+additional_order
        count = min(submitted, available, window.capacity_shares)//window.quantity.fill_step*window.quantity.fill_step
        if not count:
            return None
        price, fx = dec(window.execution_price), window.fx.read(window.at)
        local = count*price
        components = self._fee(order, window.fees, 'sell', local, shares=count, par_value=window.par_value)
        fee = sum(components.values(), ZERO)*fx
        net = local*fx-fee
        if net < 0 and self.available < -net:
            return None
        if not self._consume_event(order, window):
            return None
        order.submitted_remaining = submitted-count
        if order.remaining_target is not None:
            order.remaining_target -= count
        remaining = count
        for lot in pos.lots:
            if lot.sellable_at <= window.at:
                sold = min(remaining, lot.shares); lot.shares -= sold; remaining -= sold
        pos.lots[:] = [lot for lot in pos.lots if lot.shares]
        self._remember_fees(order, window.fees, 'sell', local, components,
                           shares=count, par_value=window.par_value)
        settlement_id = self._id('sale', sid)
        if net < 0:
            self.available += net  # Lock only the excess fee; no borrowed cash.
        self.settlements[settlement_id] = Settlement(settlement_id, abs(net), net < 0,
                        window.cash_due_at, abs(local-sum(components.values(), ZERO)), fx, window.fx.source_id)
        receipt = FillReceipt(self._id('fill', sid), sid, 'sell', count, local*fx, fee,
                               window.at, settlement_id, window.execution_basis)
        self.fills.append(receipt); self.fees_cny += fee
        self.audit_log.append(dict(kind='fill', receipt=receipt, order_id=order.event_id,
                                  raw_open=window.raw_open, price=price, fx_rate=fx,
                                  fx_source=window.fx.source_id, source=window.source_id,
                                  fee_schedule=window.fees.schedule_id, fee_components=components))
        if not pos.shares:
            del self.positions[sid]; del self.exits[sid]
            self.completed.append(admission.ExitCompletion(sid, order.event_id, window.at))
        elif order.remaining_target == 0:
            del self.exits[sid]
        return receipt
```

[pilot.py:74–88](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:74)

```python
 def fill_exit(self,sid,w):
  receipt=super().fill_exit(sid,w)
  if receipt:
   left=receipt.shares;targets=self.sell_layers[sid];parts=[]
   for z in self.live(sid):
    if z['id'] not in targets:continue
    take=min(left,z['qty']);z['qty']-=take;left-=take;cash=(receipt.gross_cny-receipt.fees_cny)*D(take)/receipt.shares;z['cash']+=cash
    if not z['qty']:z['closed']=w.at
    parts.append(dict(layer=z['id'],kind=z['kind'],shares=take,net_cash=cash,reason=z['reason']))
    if not left:break
   assert not left,(sid,receipt,'sale allocation')
   self.trades.append(dict(**asdict(receipt),parts=parts,raw_open=w.raw_open,price=w.execution_price,reason=','.join(sorted({p['reason'] for p in parts}))))
   if sid not in self.exits:self.sell_layers.pop(sid,None)
   if not self.quantity(sid):self.last_buy.pop(sid,None)
   self.counts['sell_fills']+=1
```

[joint_v3.py:130–136](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:130)

```python
 def fill_exit(self,sid,w):
  before={x['id']:dict(x) for x in self.live(sid)};r=super().fill_exit(sid,w)
  if r:
   for part in self.trades[-1]['parts']:
    meta=self.jmeta[part['layer']];fee=float(r.fees_cny)*part['shares']/r.shares;loss=max(0.,meta['unit_cost']-float(r.gross_cny/D(r.shares)))*part['shares']+fee;self.budget.loss(meta['sector'],meta['episode'],loss)
   self.journal.append(dict(kind='real_sell_fill',at=w.at,sid=sid,shares=r.shares,price=r.gross_cny/D(r.shares),fees=r.fees_cny,parts=self.trades[-1]['parts']));self.sync(w.at)
  return r
```

先按真实sellable_at/T+1、卖出数量格点和window.capacity决定count；net=gross−fee。正净款此时形成credit Settlement，stock/策略parts按真实count减少；J.fill_exit末尾sync先将这笔款体现为sale_receivable。只有net<0才立即扣不足费用。不要把这里描述成预记一个未成交卖单或凭退出意图直接加现金。

## 4. settlement lag=0与第二次sync让净款进入可花资金

[adapter.py:65–65](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-I-quarter-2025Q3-20261031/adapter.py:65)

```python
 rules=read(RR/'pvr-act-comparison-20261027/execution-rules-v2.json');m=E.FastMarket(b,rules,[],read(BP.C.OLD/'inputs-v2/economic-protocol.json'))
```

[economic-protocol.json:19–33](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/economic-protocol.json:19)

```python
  "participation_rate": ".01",
  "daily_execution": {
    "A": {
      "price_limit_policy": "conservative_hl_proxy",
      "reject_flat_day": true,
      "slippage_bps": "5",
      "stress_slippage": true
    }
  },
  "sellable_lag_sessions": {
    "A": 1
  },
  "settlement_lag_sessions": {
    "A": 0
  },
```

[fast_market.py:17–21](/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py:17)

```python
 def lag(self,market,at,count):
  if count==0:return at
  j=bisect_right(self.session_days[market],at.date())+count-1
  if j>=len(self.sessions[market]):raise RuleUnavailable('Calendar does not cover settlement')
  return self.sessions[market][j]
```

[sector_account.py:799–809](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:799)

```python
    def settle_due(self, at) -> tuple[str, ...]:
        self._time(at)
        done = []
        for key, item in list(self.settlements.items()):
            if item.due_at <= at:
                if not item.debit:
                    self.available += item.cny_amount
                # Debit cash was already locked, never available for another buy.
                del self.settlements[key]; done.append(key)
                self.audit_log.append(dict(kind='settle', at=at, settlement=item))
        return tuple(done)
```

[sector_account.py:435–456](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:435)

```python
    def balance(self, at, marks: Mapping[str, Mark], currency_fx: Mapping[str, FXQuote] | None = None):
        self._time(at)
        for sid, pos in self.positions.items():
            if pos.currency == 'CNY' and marks[sid].fx.read(at) != ONE:
                raise ValueError('CNY inventory valuation FX must equal one')
        stock = sum((p.shares * marks[sid].cny_price(at) for sid, p in self.positions.items()), ZERO)
        reserved = sum((o.remaining_budget_cny+o.fee_reserved_cny for o in self.buys.values()), ZERO)
        locked = sum((s.cny_amount for s in self.settlements.values() if s.debit), ZERO)
        receivable = sum((s.cny_amount for s in self.settlements.values() if not s.debit), ZERO)
        dividend = ZERO
        for d in self.dividends.values():
            if d.currency == 'CNY':
                rate = ONE
            else:
                if currency_fx is None or d.currency not in currency_fx:
                    raise ValueError('Outstanding foreign dividend needs a known valuation FX')
                rate = currency_fx[d.currency].read(at)
            dividend += d.net_local * rate
        nav = self.available + reserved + locked + receivable - locked + stock + dividend
        result = dict(available=self.available, order_reserved=reserved, settlement_locked=locked,
                      payable=locked, sale_receivable=receivable, dividend_receivable=dividend,
                      inventory=stock, nav=nav, fees_cny=self.fees_cny)
```

[joint_v3.py:43–62](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:43)

```python
  self.pools_from_model();b=self.budget;marks=self.market.marks(at,self.positions);bal=self.balance(at,marks);lots=[]
  for x in self.layers:
   if not x['qty']:continue
   # Only the last decision-known core line is available at the next open.
   # facts.row(at) contains that date's close and must not update this at open.
   meta=self.jmeta[x['id']];sid=x['sid'];factor=self.facts.factor(sid,at);floor=D(str(meta['last_core_line'])) if x['kind']=='core' else x['floor']
   if floor is None:raise ValueError('unknown actual protection floor '+sid)
   b.prices[sid]=float(marks[sid].cny_price(at));lots.append(V.Lot(str(x['id']),sid,meta['sector'],meta['episode'],meta['pool'],x['qty'],meta['unit_cost'],float(floor/factor),meta['role'],meta['attempt']))
  b.lots=lots
  for sid,o in self.buys.items():
   bid=self.order_bridge[o.order_id];bo=b.orders[bid];assert bo.qty==o.remaining_shares,(sid,'budget/actual pending quantity')
   assert abs(bo.qty*bo.limit-float(o.remaining_budget_cny))<1e-6,(sid,'mirror pending gross differs from native')
   assert abs(bo.qty*bo.fee_per_share-float(o.fee_reserved_cny))<1e-6,(sid,'mirror pending fee differs from native')
   bo.floor=float(self.order_meta[o.order_id]['floor']/self.facts.factor(sid,at))
  # This is an authorization view of explicit real-ledger accounts, not a
  # second valuation engine and not a residual forced to match NAV.
  b.cash=float(bal['available']+bal['order_reserved'])
  b.receivable_equity=float(bal['sale_receivable']+bal['dividend_receivable'])
  self.budget_at=at;self._budget_sync_pending=pending_ack
  self.assert_budget_view(at,bal,pending_ack=pending_ack)
```

实际context给FastMarket的protocol含A settlement_lag_sessions=0，lag(...,0)直接返回at。window.cash_due_at=at，J307的settle_due当场将credit加入available并删应收；再sync令Budget.cash=available+order_reserved，receivable_equity只留尚未结算应收。不是把same-day settlement等同于broker已经建模：这是原冻结研究协议和原内部账事件。

## 5. 实际No60买route/预留确实读到该available

[native_adapter.py:11–22](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:11)

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

[EFFECTIVE_NO60_ROUTE.txt:1–29](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/sell_cash_clock_data_audit_v1/code/EFFECTIVE_NO60_ROUTE.txt:1)

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

有效route为P.ROUTES[True]（without-account模板再去confirmed60）；不误引J原route里已覆盖的3%/60%。`cash_or_original_reserve`核 `cap+fee <= min(a.available−.1*a.current_nav, b.cash−reserve)`。b.cash−reserve与原available镜像一致，故已结算卖款参与q搜索。reserve成功才真实available减gross+fee；买window随后才查。

## 6. 主例：海能达2024-10-22，原sell/settle/reserve序列

原No60 BASELINE/2022_2024，原book `B.json.gz` SHA `5c3206b3dbaac79146a81b11f77f8d76337d2d6c1415326fc10a486074e88f02`。下列金额直接抄原audit/已有cash bridge；不是新反事实。

| 原audit index | 时间 | 原事件与金额（元） |
|---:|---|---|
| 17617 | 09:30 | 卖000656.SZ 300股，gross338.830500，fee5.1911342850500；生成sale:000656.SZ:10836 |
| 17618 | 09:30 | 卖601107.SH 8800股，OPEN5.51、price5.507245，gross48463.756000，fee37.0311559596000；生成sale:601107.SH:10838 |
| 17619 | 09:30 | 前一credit settle，净333.6393657149500、due_at同09:30 |
| 17620 | 09:30 | 后一credit settle，净48426.7248440404000、due_at同09:30 |
| 17621 | 09:30 | 海能达002583.SZ reserve 1000股，gross14007.00000+fee5.897848700000，known_open_funding=True |

已有cash bridge给出：前CLOSE available **99854.4201497192475**，且reserve/settlement/receivable组件为0；上述结算后、该reserve前available **148614.7843594745975**，之前没有其它原reserve。随后同OPEN资金计算使用这个余额。原买意图decision_at是2024-10-21 15:10，而本次reserve是2024-10-22 09:30。

完整原事件（含稍后该买单actual fill）已按原audit index抄至 [EXISTING_ORIGINAL_EVENTS.json](EXISTING_ORIGINAL_EVENTS.json)；现金字段来源 [ORIGINAL_OPEN_SLOT_CASH_BOUNDS.json](../../mobile_unit_risk_revision_v1/hainengda/ORIGINAL_OPEN_SLOT_CASH_BOUNDS.json)。这里**不证明该buy离开这些卖款必定失败或数量必然不同**，也未计算它；只证明净款确实进入了它读到的资助prefix。

## 7. 对应601107卖出bar的原始H/L/V与时间证据缺口

该sell receipt.source为 `b3b7ce60eafc4e9975e8a3909bbe6ad877ddf41566e14fc8e88a692ca5beac64`，与prepared manifest的601107 raw parquet SHA逐字相同。

```text
trade_date=2024-10-22 00:00:00
open=5.51, high=5.74, low=5.40, close=5.61
volume=75611279.0 shares, amount=424098423.0 CNY
source_kind=tushare_raw; observed_at=""
manifest.close_available_time="15:05:00"
```

来源路径/完整字段和manifest记录见 [RAW_601107_20241022.json](RAW_601107_20241022.json)。raw行仅日级trade_date和空observed_at，既没有high/low/volume各自publication time，也没有各自received_at；manifest的close_available_time不能证明H/L/V于09:30已知。FastMarket却在该at索引整根当日日线，用这些最终字段产生sell window。

## 8. 当OPEN真实已知与未获源码证据支持的部分

| 输入/状态 | 源码中的时钟性质 |
|---|---|
| 前CLOSE卖出意图、库存/可卖批次、规则/费用版本 | 在既有事实与原proxy版本下按先前状态传入 |
| 本日raw OPEN | J/FillWindow在OPEN事件直接读取；仍未建模看价后外部发送/ACK延迟 |
| 本日最终H/L/总volume、整日flat-bar判定 | 真实OPEN不能已知最终值；本原源没有对应09:30前逐字段收报证明 |
| 由这些字段决定的sell_allowed/capacity/count | 原回测内部已据后验代理确定，不能当作真实OPEN已确认可卖量 |
| sell receipt、due0 settle、available、Budget.cash | 在该代理假设下内部顺序真实记账；不是未成交意图预支 |
| 实际资金影响的量级/去除此代理后的新q或收益 | 本件没有测试，不从一例推算 |

**审计结论范围：源码和原数值确认了“卖端日线postcheck→同OPEN净成交/结算→买端资助”的反馈路径。不能因此把所有已完成结果简单改成一个新收益，也不能继续宣称所有当日H/L/V都在资金决定之后才被使用。**
