# 当前No60：风险门与损耗/失败记忆源码原文

只读取源文本、AST字面字符串和文件SHA；不导入策略、不调用模型、不执行组件中的exec/compile、无新测试/账户/回测。

**方法归属：** A只把request换成P.MOD.Contract.request，migrate换成P.MOD.Contract.migrate；loss/resources/start/observe/valid等实际沿J.Budget→V.Contract继承。J.Budget.industry在B.expand=True时委托V。MODEL_TEMPLATE的其它fill/sell辅助方法没有作为当前ledger成交回调使用，实际回调见J104–135。

**派生文本行号：** EFFECTIVE_NO60_*是本目录对P原字符串替换的只读静态还原；不能把它们的行号冒充原磁盘文件行号。原模板与P行号同时保留。

## 当前No60预算/route真正覆盖；未重建预算对象

来源：[native_adapter.py:11](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:11)；原文范围11–40。

```python
  11 class NoConfirmed60Budget(N.BASE.NoAccountBudget):
  12     request=P.MOD.Contract.request
  13     def migrate(self,sector):
  14         return P.MOD.Contract.migrate(self,sector) if self.expand else False
  15 
  16 class Runner(N.Runner):
  17     route=P.ROUTES[True]
  18     def __init__(self,*args,**kwargs):
  19         self._cap_bootstrap=True
  20         super().__init__(*args,**kwargs)
  21         self.remove_confirmed60=True
  22         for a in self.accounts.values():a.budget.__class__=NoConfirmed60Budget
  23         self.integration_policy=POLICY+':'+self.rank_mode
  24         self._cap_bootstrap=False
  25         self.assert_native_wiring()
  26 
  27     def assert_native_wiring(self):
  28         bootstrap=getattr(self,'_cap_bootstrap',False)
  29         assert self.integration_policy==(N.POLICY if bootstrap else POLICY)+':'+self.rank_mode
  30         assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
  31         assert self.opening.__func__ is J.Runner.opening
  32         assert self.planning.__func__ is N.Runner.planning
  33         assert self.route.__func__ is P.ROUTES[True]
  34         for a in self.accounts.values():
  35             assert type(a)is J.Account and type(a.budget)is (N.BASE.NoAccountBudget if bootstrap else NoConfirmed60Budget)
  36             if not bootstrap:
  37                 assert a.budget.request.__func__ is P.MOD.Contract.request
  38                 assert a.budget.migrate.__func__ is NoConfirmed60Budget.migrate
  39             for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
  40                 assert getattr(a,name).__func__ is getattr(J.Account,name)
```

## NoAccountBudget继承J.Budget；当前B账户由原构造建立

来源：[adapter.py:5](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/adapter.py:5)；原文范围5–19。

```python
   5 sys.path.insert(0,str(O.parent/'case-stage-ledger-20261031/v3'))
   6 import launch_v3 as L
   7 J=L.J
   8 N=J.W.load('single_factor_budget_no_account',O/'model_without_account_check.py')
   9 class NoAccountBudget(J.Budget):
  10  request=N.Contract.request
  11 def enable(account):
  12  # Same initialized market attempt/consumption/resources; no reseeding or cash.
  13  account.budget.__class__=NoAccountBudget
  14 env=dict(J.__dict__);exec((O/'route_without_account_check.py').read_text(),env)
  15 class Runner(L.PreparedRunner):
  16  route=env['route']
  17  def __init__(self,*args,**kwargs):
  18   super().__init__(*args,policies=('B',),**kwargs)
  19   for a in self.accounts.values():enable(a)
```

## 实际初始化20000/record_only；其余方法沿V继承

来源：[joint_v3.py:15](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:15)；原文范围15–31。

```python
  15 class Budget(V.Contract):
  16  def __init__(self,expand):self.expand=expand;self.receivable_equity=0.;super().__init__(nav=1e6,cash=1e6,shared_loss_budget=20000,exhausted_policy='record_only')
  17  @property
  18  def nav(self):return super().nav+self.receivable_equity
  19  def migrate(self,sector):return super().migrate(sector) if self.expand else False
  20  def industry(self,token,bar):
  21   if self.expand or not self.sectors[token.sector].active:return super().industry(token,bar)
  22   # Probe-only control inherits the same market attempt, but never raises its
  23   # financial level, migrates a pool, or cancels for promotion.
  24   s=self.sectors[token.sector]
  25   if not self.valid(token,'industry_cp1',bar) or token.event_id in self.consumed:return 'rejected'
  26   if token.confirmed_time<=s.failed_bar or token.end<=s.failed_bar or bar<=s.last_bar or token.end<=s.last_end or token.confirmed_time<=s.last_evidence_time:return 'not_new_progress'
  27   if token.confirmed_time!=bar:return 'late_evidence_audit_only'
  28   self.consumed.add(token.event_id);s.last_bar=bar;s.last_end=token.end;s.last_evidence_time=token.confirmed_time;self.audit.append(('probe_only_new_industry_evidence',token.event_id));return 'probe'
  29 class Account(C.Account):
  30  def __init__(self,name,market,facts,expand,sector_by_sid):
  31   super().__init__(name,market,facts,False,1,0);self.budget=Budget(expand);self.sector_by_sid=sector_by_sid;self.jmeta={};self.order_bridge={};self.journal=[];self.sync_rows=[];self.budget_at=None
```

## B账户expand=True与单一sector_by_sid映射

来源：[joint_v3.py:166](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:166)；原文范围166–175。

```python
 166 class Runner(W.Harness):
 167  def __init__(self,shared,receipts,policies=('A','B'),*,stock_cp=None,industry_states=None,industry_receipts=None):
 168   if stock_cp is None:super().__init__(shared,False)
 169   else:
 170    # Same original harness initialization, with already-verified cache views
 171    # supplied instead of the old hard-coded77 filenames. No policy override.
 172    M.Pilot.__init__(self,policies=('L0',),shared=shared);self.gate_enabled=False
 173    self.cp=stock_cp;self.pv={sid:pd.Series(dtype=float,index=pd.DatetimeIndex([])) for sid in self.market.lines}
 174    assert set(self.cp)==set(self.market.lines)
 175   self.sector_by_sid={l.security_id:l.sector_id for l in self.bundle.lines};self.accounts={p:Account(p,self.market,self.facts,p=='B',self.sector_by_sid) for p in policies};self.receipts=receipts;self.opportunities=[];self.stage_events=[];self.funding=[];self.balance_audit=[]
```

## 对照：原全账户3%保护距离门，当前已被删

来源：[model.py:239](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:239)；原文范围239–255。

```python
 239         cap, risk = qty*limit, qty*(limit-floor)
 240         pc, pr, _ = self.resources(pool)
 241         sc, sr, _ = self.resources(sector=sector)
 242         _, ar, reserve = self.resources()
 243         pending_fees = sum(o.qty*o.fee_per_share for o in self.orders.values()
 244                            if o.status in ('open', 'cancel_pending'))
 245         # Known execution fees cannot make an at-cap reservation violate its own cap on fill.
 246         budget_nav = self.nav - pending_fees - qty*fee_per_share
 247         failures = []
 248         if reserve + qty*(limit+fee_per_share) > self.cash + 1e-9: failures.append('cash')
 249         if pc+cap > (0.10 if pool == 'probe' else 0.60)*budget_nav + 1e-9: failures.append('pool_capital')
 250         if pool == 'probe' and pr+risk > .005*budget_nav + 1e-9: failures.append('probe_risk')
 251         sector_fraction = .02 if probe_request else (0.02, 0.10, 0.20)[s.level]
 252         if sc+cap > sector_fraction*budget_nav + 1e-9: failures.append('sector_capital')
 253         if sr+risk > .01*budget_nav + 1e-9: failures.append('sector_risk')
 254         if ar+risk > .03*budget_nav + 1e-9: failures.append('account_risk')
 255         if failures:
```

## account-check移除后的request模板；损耗拒绝仍需非record_only

来源：[model_without_account_check.py:236](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py:236)；原文范围236–256。

```python
 236         if self.exhausted_policy != 'record_only' and self.shared_loss >= self.loss_budget and (pool == 'probe' or self.exhausted_policy == 'all_new_risk'):
 237             if pool == 'confirmed': s.status = 'confirmed_unfunded'
 238             return 'shared_loss_exhausted'
 239         cap, risk = qty*limit, qty*(limit-floor)
 240         pc, pr, _ = self.resources(pool)
 241         sc, sr, _ = self.resources(sector=sector)
 242         _, ar, reserve = self.resources()
 243         pending_fees = sum(o.qty*o.fee_per_share for o in self.orders.values()
 244                            if o.status in ('open', 'cancel_pending'))
 245         # Known execution fees cannot make an at-cap reservation violate its own cap on fill.
 246         budget_nav = self.nav - pending_fees - qty*fee_per_share
 247         failures = []
 248         if reserve + qty*(limit+fee_per_share) > self.cash + 1e-9: failures.append('cash')
 249         if pc+cap > (0.10 if pool == 'probe' else 0.60)*budget_nav + 1e-9: failures.append('pool_capital')
 250         if pool == 'probe' and pr+risk > .005*budget_nav + 1e-9: failures.append('probe_risk')
 251         sector_fraction = .02 if probe_request else (0.02, 0.10, 0.20)[s.level]
 252         if sc+cap > sector_fraction*budget_nav + 1e-9: failures.append('sector_capital')
 253         if sr+risk > .01*budget_nav + 1e-9: failures.append('sector_risk')
 254         if failures:
 255             if pool == 'confirmed': s.status = 'confirmed_unfunded'
 256             return ','.join(failures)
```

## 当前再移除confirmed60的三处字符串改写；本审未exec或compile

来源：[component.py:17](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py:17)；原文范围17–34。

```python
  17 MODEL=(W/'account-risk-ablation-20261031/model_without_account_check.py').read_text()
  18 ROUTE=(W/'account-risk-ablation-20261031/route_without_account_check.py').read_text()
  19 assert inspect.getsource(N.Contract.migrate)==inspect.getsource(J.V.Contract.migrate)
  20 MG="        if self.resources('confirmed')[0] + moved > .60*(self.nav-pending_fees) + 1e-9:\n            s.status = 'confirmed_unfunded'\n            return False\n"
  21 PG="        if pc+cap > (0.10 if pool == 'probe' else 0.60)*budget_nav + 1e-9: failures.append('pool_capital')"
  22 PN="        if pool == 'probe' and pc+cap > 0.10*budget_nav + 1e-9: failures.append('pool_capital')"
  23 RG="    if pc+cap>(.10 if pool=='probe' else .60)*nav+1e-9:fails.append('pool_capital')"
  24 RN="    if pool=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')"
  25 assert MODEL.count(MG)==MODEL.count(PG)==ROUTE.count(RG)==1
  26 NEW_MODEL=MODEL.replace(MG,'').replace(PG,PN)
  27 NEW_ROUTE=ROUTE.replace(RG,RN)
  28 assert NEW_MODEL.replace(PN,PG).replace('        before = (self.cash, self.nav, self.resources(), self.shared_loss)',MG+'        before = (self.cash, self.nav, self.resources(), self.shared_loss)')==MODEL
  29 assert NEW_ROUTE.replace(RN,RG)==ROUTE
  30 MOD=ModuleType('pvr_private_no_confirmed60_model');sys.modules[MOD.__name__]=MOD
  31 exec(compile(NEW_MODEL,str(O/'derived_model_no_confirmed60.py'),'exec'),MOD.__dict__)
  32 ROUTES={}
  33 for flag,source in [(False,ROUTE),(True,NEW_ROUTE)]:
  34     env=dict(J.__dict__);exec(compile(source,str(O/('derived_route_on.py' if flag else 'derived_route_off.py')),'exec'),env);ROUTES[flag]=env['route']
```

## 静态还原的当前route全文；原模板经P替换，仅去confirmed60

来源：[EFFECTIVE_NO60_ROUTE.txt:1](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/funding_state_memory_audit_v1/risk_memory_review/EFFECTIVE_NO60_ROUTE.txt:1)；原文范围1–29。

```python
   1 def route(self,a,i,x,at):
   2   b=a.budget;sid=i['sid'];sector=self.sector_by_sid[sid];s=b.sectors.get(sector);bar=ordinal(i['clock'].decision_at.date());role=i['role'];p=float(x['price']);floor=float(x['floor']);rule=x['rule'];maxq=x['maxq'];rid=i.get('CP1_id');token=None
   3   if not s or not s.active:return None,'industry_invalidated'
   4   if role=='mobile':
   5    cp=i['CP1_trace'];token=V.Evidence(rid,sector,'stock_cp1','21',ordinal(cp['formation_start_exclusive']),bar,bar,s.episode,sid,s.attempt)
   6    if not b.valid(token,'stock_cp1',bar) or rid in b.consumed:return None,'no_fresh_stock_CP1'
   7   assert not getattr(a,'_budget_sync_pending',False),'cannot admit during unacknowledged ledger callback'
   8   routes=['probe']
   9   if role=='mobile' and b.expand and s.level>0:
  10    if b.migrate(sector):a.pools_from_model();routes.append('confirmed')
  11   results=[];reasons={}
  12   for pool in routes:
  13    pc,pr,_=b.resources(pool);sc,sr,_=b.resources(sector=sector);_,ar,reserve=b.resources();pending_fees=sum(o.qty*o.fee_per_share for o in b.orders.values() if o.status in ['open','cancel_pending']);frac=.02 if pool=='probe' else (.02,.1,.2)[s.level]
  14    def allowed(q,detail=False):
  15     fee=float(LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value));nav=b.nav-pending_fees-fee;cap=q*p;risk=q*max(0.,p-floor);fails=[]
  16     if cap+fee>min(float(a.available-a.current_nav*D('.1')),b.cash-reserve)+1e-9:fails.append('cash_or_original_reserve')
  17     if pool=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')
  18     if pool=='probe' and pr+risk>.005*nav+1e-9:fails.append('probe_risk')
  19     if sc+cap>frac*nav+1e-9:fails.append('sector_capital')
  20     if sr+risk>.01*nav+1e-9:fails.append('sector_risk')
  21     known_open=x.get('known_open',x['price']/(D(1)+LR.SLIP));held_at_open=float(a.quantity(sid))*float(known_open)
  22     if held_at_open+cap>.10*float(a.current_nav)+1e-9:fails.append('stock_capital')
  23     return fails if detail else not fails
  24    q=LR.maximum_quantity(rule,maxq,allowed);results.append((q,pool));reasons[pool]=allowed(rule.buy_minimum,True)
  25   # Maximum legal quantity, probe wins a tie. No split order or speculative consume.
  26   q,pool=max(results,key=lambda z:(z[0],z[1]=='probe'))
  27   if not q:return None,','.join(sorted(set(sum(reasons.values(),[])))) or 'minimum_unit_not_funded'
  28   bid=f"{a.label}|{i['clock'].decision_at.isoformat()}|{sid}|{role}";fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value);result=b.request(bid,sid,sector,q,p,floor,token,bar,float(fee/D(q)),probe_request=pool=='probe',role=role,order_expiry_bar=ordinal(at.date()),core_epoch_locked=role=='core' and a.core_epoch.get(sid)==i['epoch']);assert result=='reserved',(bid,result,reasons)
  29   i.update(budget_order=bid,pool=pool);return(q,pool),None
```

## CORE单笔保护风险及整手最大量函数

来源：[study.py:16](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:16)；原文范围16–31。

```python
  16 RISK=D('.0025');SLIP=D('.0005')
  17 CASES=['601869.SH','300502.SZ','300308.SZ','688498.SH','688048.SH','688256.SH','002987.SZ','002439.SZ','688041.SH']
  18 
  19 def fees(qty,price,schedule,side,par=None):
  20  return sum(schedule.incremental(side,D(qty)*price,{}, {},ONE,shares=qty,par_value=par).values(),ZERO) if qty else ZERO
  21 def protection_risk(qty,price,floor,schedule,par=None):
  22  return max(ZERO,D(qty)*(price-floor*(ONE-SLIP))+fees(qty,price,schedule,'buy',par)+fees(qty,floor*(ONE-SLIP),schedule,'sell',par))
  23 def maximum_quantity(rule,cap,allowed):
  24  """Largest legal original order, never fabricate a sub-minimum order."""
  25  if cap<rule.buy_minimum or not allowed(rule.buy_minimum):return 0
  26  lo,hi=0,(cap-rule.buy_minimum)//rule.buy_step
  27  while lo<hi:
  28   mid=(lo+hi+1)//2
  29   if allowed(rule.buy_minimum+mid*rule.buy_step):lo=mid
  30   else:hi=mid-1
  31  return rule.buy_minimum+lo*rule.buy_step
```

## CORE信号.25%风险和OPEN复核

来源：[study.py:42](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:42)；原文范围42–66。

```python
  42 def resize_core(i,nav,factor):
  43  q=i['quote'];floor=i['floor']/factor;ref=q.raw_price*(ONE+SLIP);risk=nav*RISK;grosscap=nav*D('.1')
  44  i.update(risk_budget=risk,frozen_floor_raw=floor,signal_price=q.raw_price,reference_price=ref)
  45  if floor<=0 or floor>=q.raw_price:i.update(budget=ZERO,cap=0,size_reject='invalid_protection');return
  46  cap=maximum_quantity(q.quantity,int(grosscap/ref),lambda n:protection_risk(n,ref,floor,q.fees,q.par_value)<=risk)
  47  if not cap:i.update(budget=ZERO,cap=0,size_reject='minimum_unit_exceeds_risk_or_nominal_cap');return
  48  # Maximum gross reservation at the frozen share cap, without an arbitrary gap buffer.
  49  stop=D(cap)*floor*(ONE-SLIP);sellfee=fees(cap,floor*(ONE-SLIP),q.fees,'sell',q.par_value);lo=int(D(cap)*ref*100);hi=int(grosscap*100)
  50  while lo<hi:
  51   mid=(lo+hi+1)//2;b=D(mid)/100
  52   if b+fees(cap,b/D(cap),q.fees,'buy',q.par_value)-stop+sellfee<=risk:lo=mid
  53   else:hi=mid-1
  54  i.update(budget=D(lo)/100,cap=cap,size_reject=None)
  55 
  56 def preview(i,op,factor,rule,schedule):
  57  p=op*(ONE+SLIP);floor=i['floor']/factor;cap=i['cap'];budget=i['budget'];par=i['quote'].par_value
  58  if op<=floor:return None,'open_at_or_below_protection'
  59  def allowed(q):return D(q)*p<=budget and (i['kind']!='core' or protection_risk(q,p,floor,schedule,par)<=i['risk_budget'])
  60  maxq=maximum_quantity(rule,min(cap,int(budget/p)),allowed)
  61  if not maxq:return None,'open_minimum_exceeds_frozen_contract'
  62  cache={}
  63  def cost(q):
  64   if q not in cache:cache[q]=D(q)*p+fees(q,p,schedule,'buy',par)
  65   return cache[q]
  66  return dict(sid=i['sid'],i=i,price=p,floor=floor,rule=rule,schedule=schedule,maxq=maxq,minq=rule.buy_minimum,cost=cost,weight=D(str(i['weight'])),qty=0),None
```

## MOBILE原2%gross与CORE resize、真实pending/daily输出

来源：[joint_v3.py:243](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:243)；原文范围243–259。

```python
 243     cpr=self.receipts[sid].get(gidday(at));roles=[];why=[];held=bool(a.quantity(sid));epoch=self.global_watch.get(sid);sector=self.sector_by_sid[sid]
 244     if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
 245     if cpr and continuing[sid].q is True:roles.append('mobile')
 246     if not a.risk_state['on']:why.append('ACT_paused')
 247     if sid in a.exits:why.append('exit_pending')
 248     if sid in a.buys:why.append('buy_pending')
 249     if event[sid].q is not True and not (cpr and continuing[sid].q is True):why.extend(event[sid].reasons or ['no_fresh_signal_or_Q'])
 250     self.opportunities.append(dict(account=a.label,day=gidday(at),sid=sid,sector=sector,rank=rank,core_Q=event[sid].q,mobile_Q=continuing[sid].q,CP1_id=cpr['receipt_id'] if cpr else None,roles=roles,held=held,barriers=why))
 251     if why or not roles:continue
 252     q=self.market.quote(sid,at);floor=self.facts.floor(sid,at,'I')
 253     if q is None or floor is None:continue
 254     for role in roles:
 255      fline=max(floor,D(str(self.cp[sid].loc[day,'candidate']))) if role=='mobile' else floor;budget=min(a.current_nav*D('.02'),max(Z,a.current_nav*D('.1')-a.quantity(sid)*q.raw_price));i=dict(sid=sid,clock=clock,quote=q,budget=budget,cap=q.quantity.buy_floor(int(budget/q.raw_price)),weight=1.,group=0,score=sd[sid].rank.read(clock),kind='add' if role=='mobile' else 'core',role=role,floor=fline,epoch=epoch,reason='fresh_CP1_mobile' if role=='mobile' else 'I_early_core',rank=rank,CP1_id=cpr['receipt_id'] if role=='mobile' else None,CP1_trace=cpr if role=='mobile' else None)
 256      if role=='core':LR.resize_core(i,a.current_nav,self.facts.factor(sid,at))
 257      if not i.get('size_reject') and i['cap']>0:a.pending.append(i)
 258      else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=role,result=i.get('size_reject','no_nominal_gap')))
 259    a.decisions.append(dict(at=at,nav=a.current_nav,on=a.risk_state['on'],intents=[{k:v for k,v in i.items() if k not in ['quote','clock','CP1_trace']} for i in a.pending]));bal=a.sync(at);a.check();self.daily.append(dict(account=a.label,at=at,**bal,on=a.risk_state['on'],positions={s:p.shares for s,p in a.positions.items()},layers=[dict(x,**a.jmeta[x['id']]) for x in a.layers if x['qty']],pending_sells=tuple(a.exits),pending_intents=len(a.pending),counts=dict(a.counts),pool_probe=a.budget.resources('probe'),pool_confirmed=a.budget.resources('confirmed'),shared_loss=a.budget.shared_loss));self.daily_bridge(a,at,bal)
```

## 继承生效：losses初始化、累计损耗、record_only与新episode

来源：[model.py:62](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:62)；原文范围62–104。

```python
  62 class Contract:
  63     def __init__(self, nav=1000., cash=1000., prices=None, lots=None,
  64                  shared_loss_budget=20., exhausted_policy='record_only'):
  65         assert exhausted_policy in ('record_only', 'probe_only', 'all_new_risk')
  66         self.cash = cash
  67         self.prices = dict(prices or {})
  68         self.lots = list(lots or [])
  69         self.orders = {}
  70         self.sectors = {}
  71         self.consumed = set()
  72         self.stock_requests = set()
  73         self.losses = {}  # (sector, original episode) -> gross negative realized PnL + fees
  74         self.loss_budget = shared_loss_budget
  75         self.exhausted_policy = exhausted_policy
  76         self.audit = []
  77         assert isclose(nav, self.nav), 'NAV must reconcile to supplied cash + marked lots'
  78 
  79     @property
  80     def nav(self):
  81         return self.cash + sum(x.qty*self.prices[x.stock] for x in self.lots)
  82 
  83     @property
  84     def shared_loss(self):
  85         return sum(self.losses.values())
  86 
  87     def loss(self, sector, episode, amount):
  88         key = (sector, episode)
  89         self.losses[key] = self.losses.get(key, 0.) + amount
  90         if self.exhausted_policy != 'record_only' and self.shared_loss >= self.loss_budget:
  91             for order in self.orders.values():
  92                 if order.pool == 'probe' or self.exhausted_policy == 'all_new_risk':
  93                     self.cancel(order.oid)  # Never release reservation without ack.
  94 
  95     def start(self, sector, episode, bar):
  96         old = self.sectors.get(sector)
  97         if old and old.episode == episode:
  98             return
  99         if old:
 100             self.invalidate(sector, old.episode, bar=bar)
 101         # Old positions/orders continue to consume resources and preserve original episode.
 102         self.sectors[sector] = Sector(episode, bar, status='awaiting_first_cp1',
 103                                       failed_bar=old.failed_bar if old else -1, episode_started=bar)
 104         self.audit.append(('episode', sector, episode))
```

## 继承生效：资源仅pool/sector分组相加；凭证epoch/attempt范围

来源：[model.py:106](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:106)；原文范围106–125。

```python
 106     def resources(self, pool=None, sector=None):
 107         lots = [x for x in self.lots if (pool is None or x.pool == pool)
 108                 and (sector is None or x.sector == sector)]
 109         orders = [x for x in self.orders.values() if x.qty > 0 and
 110                   x.status in ('open', 'cancel_pending') and
 111                   (pool is None or x.pool == pool) and
 112                   (sector is None or x.sector == sector)]
 113         capital = sum(x.qty*self.prices[x.stock] for x in lots) + sum(x.qty*x.limit for x in orders)
 114         risk = sum(x.qty*max(0., self.prices[x.stock]-x.floor) for x in lots)
 115         risk += sum(x.qty*max(0., x.limit-x.floor) for x in orders)
 116         reserve = sum(x.qty*(x.limit+x.fee_per_share) for x in orders)
 117         return capital, risk, reserve
 118 
 119     def valid(self, token, source, bar):
 120         s = self.sectors.get(token.sector)
 121         return bool(s and (source == 'industry_cp1' or s.active) and token.source == source and token.scale == '21' and
 122                     token.epoch == s.episode and
 123                     token.end >= s.episode_started and token.confirmed_time >= s.episode_started and
 124                     (source == 'industry_cp1' or (token.attempt == s.attempt and token.end >= s.started)) and
 125                     token.start <= token.end <= token.confirmed_time <= bar)
```

## sync只同步真实余股、旧线、已知mark、现金与应收；不清损耗

来源：[joint_v3.py:36](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:36)；原文范围36–63。

```python
  36  def sync(self,at,*,pending_ack=False):
  37   # Only native callbacks may change actual inventory. The mirror's existing
  38   # lot units must not be silently repaired by rebuilding it from the ledger.
  39   # Pool migration is intentionally excluded: it changes ownership of capacity,
  40   # not shares/cost/protection units.
  41   old_units=[(x.batch,x.stock,x.qty,x.cost,x.floor) for x in self.budget.lots]
  42   if hasattr(self,'_mirror_lot_units'):assert old_units==self._mirror_lot_units,'mirror lot mutation outside native sync'
  43   self.pools_from_model();b=self.budget;marks=self.market.marks(at,self.positions);bal=self.balance(at,marks);lots=[]
  44   for x in self.layers:
  45    if not x['qty']:continue
  46    # Only the last decision-known core line is available at the next open.
  47    # facts.row(at) contains that date's close and must not update this at open.
  48    meta=self.jmeta[x['id']];sid=x['sid'];factor=self.facts.factor(sid,at);floor=D(str(meta['last_core_line'])) if x['kind']=='core' else x['floor']
  49    if floor is None:raise ValueError('unknown actual protection floor '+sid)
  50    b.prices[sid]=float(marks[sid].cny_price(at));lots.append(V.Lot(str(x['id']),sid,meta['sector'],meta['episode'],meta['pool'],x['qty'],meta['unit_cost'],float(floor/factor),meta['role'],meta['attempt']))
  51   b.lots=lots
  52   for sid,o in self.buys.items():
  53    bid=self.order_bridge[o.order_id];bo=b.orders[bid];assert bo.qty==o.remaining_shares,(sid,'budget/actual pending quantity')
  54    assert abs(bo.qty*bo.limit-float(o.remaining_budget_cny))<1e-6,(sid,'mirror pending gross differs from native')
  55    assert abs(bo.qty*bo.fee_per_share-float(o.fee_reserved_cny))<1e-6,(sid,'mirror pending fee differs from native')
  56    bo.floor=float(self.order_meta[o.order_id]['floor']/self.facts.factor(sid,at))
  57   # This is an authorization view of explicit real-ledger accounts, not a
  58   # second valuation engine and not a residual forced to match NAV.
  59   b.cash=float(bal['available']+bal['order_reserved'])
  60   b.receivable_equity=float(bal['sale_receivable']+bal['dividend_receivable'])
  61   self.budget_at=at;self._budget_sync_pending=pending_ack
  62   self.assert_budget_view(at,bal,pending_ack=pending_ack)
  63   self._mirror_lot_units=[(x.batch,x.stock,x.qty,x.cost,x.floor) for x in b.lots]
```

## 实际native买卖回调loss：买费、毛负损益、卖费

来源：[joint_v3.py:104](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:104)；原文范围104–135。

```python
 104  def fill_buy(self,sid,w):
 105   real=self.buys.get(sid);i=self.order_meta[real.order_id] if real else None;bid=self.order_bridge.get(real.order_id) if real else None;self._buy_filling=sid;self._deferred_buy_cancels=[]
 106   try:r=super().fill_buy(sid,w)
 107   finally:self._buy_filling=None
 108   if r:
 109    bo=self.budget.orders[bid];price=float(r.gross_cny/D(r.shares));floor=float(i['floor']/self.facts.factor(sid,w.at));assert price<=bo.limit+1e-8
 110    x=self.layers[-1];self.jmeta[x['id']]=dict(sector=bo.sector,episode=bo.episode,pool=bo.pool,role=bo.role,attempt=bo.attempt,unit_cost=price,last_core_line=str(i['floor']),stock_structure=getattr(self.facts,'structure_lookup',{}).get(sid,{}).get(i['clock'].decision_at.date()),budget_order=bid)
 111    self.budget.loss(bo.sector,bo.episode,float(r.fees_cny))
 112    bo.qty-=r.shares
 113    if not bo.qty:bo.status='filled'
 114    elif sid in self.buys:
 115     # The real partial fill has consumed principal and incremental fee once.
 116     # Update only this actual order callback; generic sync asserts the bridge.
 117     remaining=self.buys[sid]
 118     assert bo.qty==remaining.remaining_shares
 119     bo.limit=float(remaining.remaining_budget_cny/D(bo.qty))
 120     bo.fee_per_share=float(remaining.fee_reserved_cny/D(bo.qty))
 121    self.journal.append(dict(kind='real_buy_fill',at=w.at,sid=sid,layer=x['id'],budget_order=bid,shares=r.shares,price=r.gross_cny/D(r.shares),fees=r.fees_cny,pool=bo.pool,role=bo.role,attempt=bo.attempt,signal_at=i['clock'].decision_at,CP1_id=i.get('CP1_id')))
 122   if r:self.sync(w.at,pending_ack=bool(self._deferred_buy_cancels))  # Actual lot/NAV first; no admission until ack.
 123   # Native full fills call cancel_buy internally to return residual reserve.
 124   # Mirror the actual fill first, then acknowledge only the actual remainder.
 125   for cancelled in self._deferred_buy_cancels:
 126    if self.budget.orders[cancelled].qty:self.budget.cancel(cancelled)
 127    self.budget.cancel_ack(cancelled);self.pools_from_model()
 128   self.sync(w.at)
 129   return r
 130  def fill_exit(self,sid,w):
 131   before={x['id']:dict(x) for x in self.live(sid)};r=super().fill_exit(sid,w)
 132   if r:
 133    for part in self.trades[-1]['parts']:
 134     meta=self.jmeta[part['layer']];fee=float(r.fees_cny)*part['shares']/r.shares;loss=max(0.,meta['unit_cost']-float(r.gross_cny/D(r.shares)))*part['shares']+fee;self.budget.loss(meta['sector'],meta['episode'],loss)
 135    self.journal.append(dict(kind='real_sell_fill',at=w.at,sid=sid,shares=r.shares,price=r.gross_cny/D(r.shares),fees=r.fees_cny,parts=self.trades[-1]['parts']));self.sync(w.at)
```

## 行业初始化/observe调用：新episode、失败或行业CP推进

来源：[joint_v3.py:177](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:177)；原文范围177–212。

```python
 177   for sector in sorted(set(self.sector_by_sid.values())):
 178    rows=industry_states[sector] if industry_states is not None else T.read(BASE.parent/'industry-mobile-stage-20261031'/f'{sector}_STATE.json');self.industry_rows[sector]={r['day']:r for r in rows}
 179    for r in rows:
 180     if r['E0_valid']:self.episode_starts.setdefault(r['E0_episode'],ordinal(r['day']))
 181    past=[r for r in rows if r['day']<START];last=past[-1];ep=last['E0_episode']
 182    if ep is None:ep=next((r['E0_episode'] for r in reversed(past) if r['E0_episode']),None)
 183    for a in self.accounts.values():
 184     b=a.budget
 185     if ep is None:continue
 186     b.start(sector,ep,self.episode_starts[ep]);s=b.sectors[sector];s.failed_bar=max((ordinal(r['day']) for r in past if r['action']=='end_attempt'),default=-1)
 187     if last['attempt_id'] is not None:
 188      ar=[r for r in past if r['attempt_id']==last['attempt_id']];first=next(r for r in ar if r['action']=='probe');rc=[r for r in ar if r['receipt'] and r['new_receipt']];s.active=True;s.started=ordinal(first['day']);s.attempt=f"{ep}:{first['receipt_id']}";s.level=last['stage']-1 if b.expand else 0;s.status=['probe','confirmed','expanded'][s.level];s.last_bar=s.last_end=s.last_evidence_time=ordinal(rc[-1]['day'])
 189     b.consumed.update(r['receipt_id'] for r in past if r['receipt_id']);assert not b.lots and not b.orders
 190   for sid,df in self.facts.f.items():
 191    if sid not in self.market.lines:continue
 192    on=df.e0_target.fillna(False).astype(bool);opening=on&~on.groupby(df.segment_id).shift(fill_value=False);z=pd.Series(None,index=df.index,dtype=object)
 193    for d in df.index[opening]:z.loc[d]=f'{sid}|{int(df.loc[d,"segment_id"])}|{d.date()}'
 194    self.facts.structure_lookup[sid]={d.date():v for d,v in z.groupby(df.segment_id).ffill().where(on,None).items()}
 195  def industry(self,a,at):
 196   day=gidday(at);bar=ordinal(day);b=a.budget
 197   for sector,rows in self.industry_rows.items():
 198    r=rows[day];ep=r['E0_episode'];current=b.sectors.get(sector)
 199    if r['E0_valid'] and (not current or current.episode!=ep):b.start(sector,ep,self.episode_starts[ep])
 200    if sector not in b.sectors:continue
 201    if not r['E0_valid'] or r['action']=='end_attempt':
 202     b.observe(sector,bar,failure=True);result='invalidated'
 203    elif r['receipt']:
 204     cp=self.industry_cp[sector+'|'+day];tok=V.Evidence(cp['receipt_id'],sector,'industry_cp1','21',ordinal(cp['formation_start_exclusive']),bar,bar,b.sectors[sector].episode)
 205     result=b.observe(sector,bar,token=tok)
 206    else:result='unchanged'
 207    a.pools_from_model()
 208    for sid,real in tuple(a.buys.items()):
 209     bid=a.order_bridge[real.order_id]
 210     if b.orders[bid].status=='cancel_pending':a.cancel_buy(sid)
 211    a.sync(at)
 212    if result!='unchanged':self.stage_events.append(dict(account=a.label,day=day,sector=sector,market_stage=r['stage_name'],result=result,episode=b.sectors[sector].episode,attempt=b.sectors[sector].attempt,financial_level=b.sectors[sector].level))
```

## 行业失败之后的凭证/时间推进要求；同观察失败优先

来源：[model.py:127](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:127)；原文范围127–160。

```python
 127     def industry(self, token, bar):
 128         if not self.valid(token, 'industry_cp1', bar) or token.event_id in self.consumed:
 129             return 'rejected'
 130         s = self.sectors[token.sector]
 131         if token.confirmed_time <= s.failed_bar or token.end <= s.failed_bar:
 132             return 'not_new_progress'
 133         if bar <= s.last_bar or token.end <= s.last_end or token.confirmed_time <= s.last_evidence_time:
 134             return 'not_new_progress'
 135         if token.confirmed_time != bar:
 136             self.audit.append(('late_industry_evidence_audit_only', token.event_id, bar))
 137             return 'late_evidence_audit_only'
 138         self.consumed.add(token.event_id)
 139         s.last_bar, s.last_end = bar, token.end
 140         s.last_evidence_time = token.confirmed_time
 141         if not s.active:
 142             s.active, s.level, s.started = True, 0, token.confirmed_time
 143             s.attempt = f'{s.episode}:{token.event_id}'
 144             s.status = 'probe'
 145         else:
 146             s.level = min(2, s.level + 1)
 147         for order in self.orders.values():
 148             if s.level > 0 and order.sector == token.sector and order.attempt == s.attempt and order.pool == 'probe' and order.qty > 0:
 149                 self.cancel(order.oid)
 150         self.migrate(token.sector)
 151         self.audit.append(('industry_confirmation', token.event_id, s.level))
 152         return s.status
 153 
 154     def observe(self, sector, bar, *, failure=False, token=None):
 155         if failure:
 156             self.invalidate(sector, self.sectors[sector].episode, bar=bar)
 157             return 'invalidated'  # Same-observation CP1 never restarts.
 158         if token is None: return self.sectors[sector].status
 159         assert token.sector == sector
 160         return self.industry(token, bar)
```

## invalidate保failed_bar；取消确认前保留余量

来源：[model.py:166](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:166)；原文范围166–186。

```python
 166     def invalidate(self, sector, episode, *, bar):
 167         s = self.sectors[sector]
 168         assert s.episode == episode
 169         s.active, s.status = False, 'invalidated'
 170         s.failed_bar = max(s.failed_bar, bar)
 171         for o in self.orders.values():
 172             if o.sector == sector and o.episode == episode: self.cancel(o.oid)
 173 
 174     def cancel(self, oid):
 175         o = self.orders[oid]
 176         if o.qty > 0 and o.status == 'open':
 177             o.status = 'cancel_pending'
 178 
 179     def cancel_ack(self, oid):
 180         o = self.orders[oid]
 181         if o.status in ('filled', 'cancelled') and o.qty == 0:
 182             self.migrate(o.sector)  # Full fill can win the cancel race; never erase the lot.
 183             return
 184         assert o.status == 'cancel_pending'
 185         o.qty, o.status = 0., 'cancelled'
 186         self.migrate(o.sector)
```

## 静态当前migrate：无60%检查，不更改现金/NAV/风险/损耗

来源：[EFFECTIVE_NO60_MODEL.txt:188](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/funding_state_memory_audit_v1/risk_memory_review/EFFECTIVE_NO60_MODEL.txt:188)；原文范围188–205。

```python
 188     def migrate(self, sector):
 189         s = self.sectors[sector]
 190         if s.level == 0 or not s.active:
 191             return False
 192         if any(o.sector == sector and o.attempt == s.attempt and o.pool == 'probe' and o.qty > 0
 193                and o.status in ('open', 'cancel_pending') for o in self.orders.values()):
 194             s.status = 'confirmed_unfunded'
 195             return False
 196         moved = sum(x.qty*self.prices[x.stock] for x in self.lots if x.sector == sector and x.attempt == s.attempt and x.pool == 'probe')
 197         pending_fees = sum(o.qty*o.fee_per_share for o in self.orders.values()
 198                            if o.status in ('open', 'cancel_pending'))
 199         before = (self.cash, self.nav, self.resources(), self.shared_loss)
 200         for x in self.lots:
 201             if x.sector == sector and x.attempt == s.attempt and x.pool == 'probe':
 202                 x.pool = 'confirmed'
 203         s.status = 'confirmed' if s.level == 1 else 'expanded'
 204         assert before == (self.cash, self.nav, self.resources(), self.shared_loss)
 205         return True
```

## CLOSE更新current_nav，ACT独立step及ACT/I持仓退出

来源：[joint_v3.py:213](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)；原文范围213–240。

```python
 213  def planning(self,at):
 214   clock,stocks,sectors=self.facts.packet(at,'I');sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};buyable=self.market.market_buyable(at);day=pd.Timestamp(at.date());event={};continuing={}
 215   for sid,s in sd.items():
 216    row=self.facts.row(sid,at);key=(bool(row.i_target),int(row.segment_id)) if row is not None else (False,-1)
 217    if self.last_epoch.get(sid)!=key:self.epoch[sid]+=1;self.global_watch.pop(sid,None);self.last_epoch[sid]=key
 218    ep=(key[1],self.epoch[sid]);event[sid]=BP.A.eligibility(s,ss,clock,'S0');continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
 219    if event[sid].q is True:self.global_watch[sid]=ep
 220   ordered=sorted(sd,key=lambda sid:(-(sd[sid].rank.read(clock) if sd[sid].rank and sd[sid].rank.read(clock) is not None else -1),sid))
 221   for a in self.accounts.values():
 222    C.activate(a);a.expire_day_buys(at);a.current_nav=a.balance(at,self.market.marks(at,a.positions))['nav'];M.E.risk_policy.step(a,at,'ACT20_BREAK');a.pending=[]
 223    for sid in tuple(a.positions):
 224     row=self.facts.row(sid,at);cp=self.cp[sid].loc[day] if day in self.cp[sid].index else None;quote=self.market.quote(sid,at);assert quote
 225     if not a.risk_state['on'] or not bool(row.i_target):
 226      if not bool(row.i_target):
 227       for x in a.live(sid):
 228        if x['kind']=='core':a.jmeta[x['id']]['pending_I_exit_reference']=True
 229      a.sell(sid,clock,quote,[x['id'] for x in a.live(sid)],'ACT_pause' if not a.risk_state['on'] else 'I_structure_exit');continue
 230     for x in a.live(sid):
 231      if x['kind']=='core':
 232       known_floor=self.facts.floor(sid,at,'I')
 233       if known_floor is not None:a.jmeta[x['id']]['last_core_line']=str(known_floor)
 234       continue
 235      if x['kind']!='add' or x['id'] in a.sell_layers.get(sid,set()):continue
 236      if D(str(row.close))<=x['floor']:a.sell(sid,clock,quote,[x['id']],'CP1_add_protection')
 237      else:
 238       floor=self.facts.floor(sid,at,'I')
 239       if floor is not None:x['floor']=max(x['floor'],floor)
 240       if cp is not None and bool(cp.receipt):x['floor']=max(x['floor'],D(str(cp.candidate)))
```

## ACT_paused、exit/buy pending等新仓障碍

来源：[joint_v3.py:243](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:243)；原文范围243–251。

```python
 243     cpr=self.receipts[sid].get(gidday(at));roles=[];why=[];held=bool(a.quantity(sid));epoch=self.global_watch.get(sid);sector=self.sector_by_sid[sid]
 244     if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
 245     if cpr and continuing[sid].q is True:roles.append('mobile')
 246     if not a.risk_state['on']:why.append('ACT_paused')
 247     if sid in a.exits:why.append('exit_pending')
 248     if sid in a.buys:why.append('buy_pending')
 249     if event[sid].q is not True and not (cpr and continuing[sid].q is True):why.extend(event[sid].reasons or ['no_fresh_signal_or_Q'])
 250     self.opportunities.append(dict(account=a.label,day=gidday(at),sid=sid,sector=sector,rank=rank,core_Q=event[sid].q,mobile_Q=continuing[sid].q,CP1_id=cpr['receipt_id'] if cpr else None,roles=roles,held=held,barriers=why))
 251     if why or not roles:continue
```

## OPEN最终资助使用route；没有给current_nav重赋值

来源：[joint_v3.py:302](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:302)；原文范围302–324。

```python
 302  def opening(self,a,at):
 303   C.activate(a)
 304   for sid in sorted(a.exits):
 305    win=self.market.window(sid,at,'sell',1)
 306    if win:a.fill_exit(sid,win)
 307   a.settle_due(at);a.sync(at);funded=[];done=set()
 308   for i in sorted([i for i in a.pending if i['clock'].earliest_execution_at==at],key=lambda x:(x['rank'],x['role']!='core')):
 309    sid=i['sid']
 310    if sid in done or sid in a.buys or sid in a.exits:continue
 311    raw=self.market.raw[sid];day=pd.Timestamp(at.date())
 312    if day not in raw.index or not np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='missing_open'));continue
 313    x,why=LR.preview(i,D(str(raw.loc[day].open)),self.facts.factor(sid,at),self.market.quantity(sid,at),self.market.fees(sid,at))
 314    if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
 315    x['known_open']=D(str(raw.loc[day].open))
 316    route,why=self.route(a,i,x,at)
 317    if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
 318    q,pool=route;a.reserve_quantity(i,q,x['price'],x['schedule'],at);a.sync(at);done.add(sid);funded.append((sid,i,x,q));self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='reserved',pool=pool,shares=q,price=x['price'],CP1_id=i.get('CP1_id')))
 319   # Execution proxies are consulted only after all H1-ranked funding decisions.
 320   for sid,i,x,q in funded:
 321    win=self.market.window(sid,at,'buy',1)
 322    if win:assert win.execution_price==x['price'];a.fill_buy(sid,win)
 323    else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='no_execution_window_after_reservation'))
 324   a.settle_due(at);a.sync(at);a.minimum_available=min(a.minimum_available,a.available);a.check()
```

## ACT20 episode暂停/flat恢复独立于预算losses

来源：[risk_policy.py:8](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py:8)；原文范围8–29。

```python
   8 def advance(state,nav,flat,fast,breakout,mode):
   9  s=dict(state);s['peak']=max(s['peak'],nav) if s['on'] else s['peak'];dd=1-nav/s['peak'];event=None;threshold=D('.1') if mode=='ACT10_BREAK' else D('.2')
  10  if s['on']:
  11   if dd>=threshold:
  12    s.update(on=False,saw_off=not fast);event='pause'
  13  else:
  14   s['saw_off']=s['saw_off'] or not fast
  15   recover=(s['saw_off'] and fast and not s['previous_fast']) if mode=='ACT20_FAST' else breakout
  16   if flat and recover:
  17    s.update(on=True,peak=nav,episode=s['episode']+1,saw_off=False);event='resume'
  18  s['previous_fast']=fast
  19  return s,dd,event
  20 
  21 def step(a,at,mode):
  22  if mode=='CONTROL':return
  23  if not hasattr(a,'risk_state'):a.risk_state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0)
  24  day=pd.Timestamp(at.date());i=RECOVERY.index.searchsorted(day,side='right')-1
  25  if i<0:fast=False;br=False
  26  else:r=RECOVERY.iloc[i];fast=bool(r.fast_on);br=bool(r.breakout) if RECOVERY.index[i]==day else False
  27  flat=not any(p.shares for p in a.positions.values()) and not a.exits and not a.buys
  28  a.risk_state,dd,event=advance(a.risk_state,a.current_nav,flat,fast,br,mode)
  29  a.log('risk_checkpoint',at,policy=mode,nav=a.current_nav,episode_drawdown=dd,flat=flat,fast=fast,breakout=br,event=event,**a.risk_state)
```

## checkpoint保整个account字段/budget；restore直接还原

来源：[launch_v3.py:59](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/launch_v3.py:59)；原文范围59–81。

```python
  59 class PreparedRunner(J.Runner):
  60  """Same decisions; checkpoint only after a whole original event completes."""
  61  def checkpoint(self,out,last_event):
  62   out=Path(out);out.mkdir(parents=True,exist_ok=True)
  63   immutable={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date'}
  64   runner={k:v for k,v in self.__dict__.items() if k not in immutable}
  65   accounts={k:{f:v for f,v in a.__dict__.items() if f not in ('market','facts')} for k,a in self.accounts.items()}
  66   payload=dict(last_completed_event=last_event,runner=runner,accounts=accounts,
  67    source_freeze=self.source_freeze,quarter_or_budget_reset=False)
  68   raw=pickle.dumps(payload,protocol=5);r=pickle.loads(raw)
  69   assert r['last_completed_event']==last_event
  70   for k,a in self.accounts.items():
  71    assert r['accounts'][k]['available']==a.available
  72    assert r['accounts'][k]['budget'].consumed==a.budget.consumed
  73    assert r['accounts'][k]['positions']==a.positions
  74   target=out/'checkpoint.pkl';temp=out/'checkpoint.tmp';temp.write_bytes(raw);temp.replace(target)
  75   save(out/'checkpoint.json',dict(at=last_event,sha256=sha(target),source_freeze=self.source_freeze,
  76    account_initialization_not_repeated=True,roundtrip_only_not_historical_restart_proof=True))
  77  def restore(self,path):
  78   p=pickle.loads(Path(path).read_bytes());assert p['source_freeze']==self.source_freeze,'resume input/code freeze differs'
  79   self.__dict__.update(p['runner'])
  80   for k,state in p['accounts'].items():self.accounts[k].__dict__.update(state)
  81   return p['last_completed_event']
```

## rank wrapper校验/季度复制，不重置预算

来源：[native_rank.py:122](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:122)；原文范围122–136。

```python
 122     def restore(self, path):
 123         p = pickle.loads(Path(path).read_bytes())
 124         assert p['runner']['integration_policy'] == self.integration_policy, 'checkpoint rank policy mode mismatch'
 125         assert p['runner']['rank_scores_manifest_sha256'] == SCORES.manifest_sha256, 'checkpoint PVR source mismatch'
 126         result = super().restore(path)
 127         self.assert_native_wiring()
 128         return result
 129 
 130     def checkpoint(self, out, last_event):
 131         super().checkpoint(out, last_event)
 132         day = str(last_event.date())
 133         if day in {'2022-03-31','2022-06-30','2022-09-30','2022-12-30',
 134                    '2025-09-30','2025-12-31','2026-03-31','2026-06-30'}:
 135             for suffix in ('pkl', 'json'):
 136                 shutil.copyfile(Path(out)/('checkpoint.'+suffix), Path(out)/('checkpoint-'+day+'.'+suffix))
```

## No60 restore只校验身份后调用原restore

来源：[native_adapter.py:42](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:42)；原文范围42–51。

```python
  42     def restore(self,path):
  43         # Original source freeze check still happens in PreparedRunner.restore;
  44         # atomic_runner_outputs adds the original exact engine-provenance gate.
  45         p=pickle.loads(Path(path).read_bytes())
  46         assert p['runner']['integration_policy']==self.integration_policy,'checkpoint cap policy mismatch'
  47         assert p['runner']['rank_scores_manifest_sha256']==N.SCORES.manifest_sha256
  48         assert p['runner']['remove_confirmed60']==self.remove_confirmed60
  49         result=L.PreparedRunner.restore(self,path)
  50         self.assert_native_wiring()
  51         return result
```

## 月末checkpoint；不是年度/预算重置

来源：[launch_v3.py:98](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/launch_v3.py:98)；原文范围98–108。

```python
  98    for a in self.accounts.values():a.settle_due(at)
  99    self._actions(at)
 100    for a in self.accounts.values():self._payments(a,at)
 101    if at in opens:
 102     for a in self.accounts.values():self.opening(a,at)
 103    if at in cutoffs:self.planning(at)
 104    last=at
 105    # Monthly data checkpoint, never a cash/position/ACT reset.
 106    if at in cutoffs and (pd.Timestamp(at.date())+pd.offsets.BDay()).month!=at.month:self.checkpoint(out,last)
 107   self.run_seconds=time.monotonic()-t;self.checkpoint(out,last);self.dump_joint(Path(out)/'pair')
 108   save(Path(out)/'DONE.json',dict(completed=True,run_seconds=self.run_seconds,ending_NAV={k:str(a.current_nav) for k,a in self.accounts.items()}))
```

## 最终原账输出losses与consumed

来源：[joint_v3.py:325](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:325)；原文范围325–332。

```python
 325  def dump_joint(self,path):
 326   path=Path(path);path.mkdir(exist_ok=True)
 327   for name,data in [('daily',self.daily),('opportunities',self.opportunities),('funding',self.funding),('industry',self.stage_events),('balances',self.balance_audit)]:
 328    with gzip.open(path/(name+'.jsonl.gz'),'wt') as f:
 329     for r in data:f.write(json.dumps(M.N.encoded(r),ensure_ascii=False,default=C.encoded)+'\n')
 330   for key,a in self.accounts.items():
 331    b=a.budget;payload=dict(trades=a.trades,layers=a.layers,metadata=a.jmeta,journal=a.journal,orders=a.buys,exits=a.exits,audit=a.audit_log,decisions=a.decisions,budget=dict(sectors=b.sectors,orders=b.orders,losses={str(k):v for k,v in b.losses.items()},consumed=sorted(b.consumed)),ending_cash=a.available,ending_NAV=a.current_nav)
 332    with gzip.open(path/(key+'.json.gz'),'wt') as f:json.dump(M.N.encoded(payload),f,ensure_ascii=False,default=C.encoded)
```

## BASELINE选A.Runner，fresh1m，无年度重置

来源：[run_account.py:14](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/run_account.py:14)；原文范围14–26。

```python
  14   shared,receipts,cp,states,ir,identity=V.inputs(window)
  15   sources=A.source_freeze();sources.update({str(p):sha(p) for p in [Path(__file__),O/'load_inputs.py',O/'PROTOCOL.txt',O/'STATE_MACHINE_FREEZE.json']})
  16   if arm=='BASELINE':cls=A.Runner;tool_manifest=None
  17   else:
  18    from indicator_provider import IndicatorProvider
  19    from native_adapter.early_adapter import build_runner_class
  20    provider=IndicatorProvider();cls=build_runner_class(A,provider,arm);tool_manifest=provider.manifest_sha256
  21    for p in [O/'indicator_provider.py',O/'native_adapter/early_adapter.py',O/'indicators/MANIFEST.json']:sources[str(p)]=sha(p)
  22   r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=sources
  23   a=r.accounts['B'];assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits
  24   save(out/'RUN_METADATA.json',dict(arm=arm,window=window,start=J.START,end=J.END,fresh_cash=1000000,no_checkpoint_import=True,yearly_reset=False,source_freeze=sources,input_identity=identity,tool_manifest_sha256=tool_manifest,load_seconds=time.monotonic()-started,authorization='parent delegated explicit local complete-account tests; all frozen arms reported; no live trading'))
  25   print('NATIVE_ACCOUNT_STARTED',arm,window,'load',round(time.monotonic()-started,2),flush=True)
  26   with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,seconds,end=J.END)
```
