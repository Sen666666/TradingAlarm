# 现行 No60：建仓、加仓、仓位、预算和执行源码

只摘录当前源文件与实际覆盖关系。无新设计、参数、模型/账户运行。本次没有import策略模块、没有exec/compile模型；effective文本仅按原P组件的三处字符串替换静态还原。它是供阅读的源码，不是新实现。

## 最先读这三处

- J218–257：原I事件/continuing资格、CORE/mobile角色、每次mobile金额和CORE resize。
- LR42–66：CORE .25%NAV参考风险及次OPEN复核。
- A11–22＋P17–34：真正生效的No60预算/route；不能拿J272原route里的3%/60%当现行规则。

## 1. 实际调用链和覆盖

`E.inputs`导入A；A经S取得N/J/L。A.Runner继承N.Runner，保N.planning、J.opening；route明确覆盖为P.ROUTES[True]。实际budget对象是NoConfirmed60Budget，request/migrate来自P静态改写的MOD，其余resources/loss等沿J.Budget/V继承。

[load_inputs.py:6–10](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/load_inputs.py:6)

```python
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sys.path.insert(0,str(B/'pvr_pool_feasibility'))
import native_adapter as A
N,J,L,IO=A.N,A.J,A.L,A.IO
```

[execution_support.py:1–5](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/execution_support.py:1)

```python
"""Frozen original input loaders and file/initialization safety only."""
from pathlib import Path
import sys
import native_rank as N
J, L, IO, O, W = N.J, N.L, N.IO, N.O, N.W
```

[native_rank.py:12–20](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:12)

```python
O = Path(__file__).resolve().parent
W = O.parent
sys.path.insert(0, str(W/'account-risk-ablation-20261031'))
import adapter as BASE
J, L = BASE.J, BASE.L
sys.path.insert(0, str(W/'_shared'))
import research_output_io as IO

POLICY = 'PVR_SLOT1_original_singlepass_coupled'
```

[adapter.py:5–19](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/adapter.py:5)

```python
sys.path.insert(0,str(O.parent/'case-stage-ledger-20261031/v3'))
import launch_v3 as L
J=L.J
N=J.W.load('single_factor_budget_no_account',O/'model_without_account_check.py')
class NoAccountBudget(J.Budget):
 request=N.Contract.request
def enable(account):
 # Same initialized market attempt/consumption/resources; no reseeding or cash.
 account.budget.__class__=NoAccountBudget
env=dict(J.__dict__);exec((O/'route_without_account_check.py').read_text(),env)
class Runner(L.PreparedRunner):
 route=env['route']
 def __init__(self,*args,**kwargs):
  super().__init__(*args,policies=('B',),**kwargs)
  for a in self.accounts.values():enable(a)
```

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

P读取的without_account_check模板已经没有全账户3%拒单项；P再删除confirmed迁池60%、request confirmed60%、route confirmed60%三处。保probe资本10%。以下第4节给**静态还原的实际字符串**，不是把原V/J中已覆盖的条件误当生效。

## 2. CLOSE：资格、保护/退出优先级、建仓和加仓意图

state前：真实positions/layers、上期epoch、pending orders、I/CP原事实。state后：先原退出目标/保护更新，后pending买入意图；intent不等于reserve或fill。

[joint_v3.py:213–259](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)

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
   for sid in tuple(a.positions):
    row=self.facts.row(sid,at);cp=self.cp[sid].loc[day] if day in self.cp[sid].index else None;quote=self.market.quote(sid,at);assert quote
    if not a.risk_state['on'] or not bool(row.i_target):
     if not bool(row.i_target):
      for x in a.live(sid):
       if x['kind']=='core':a.jmeta[x['id']]['pending_I_exit_reference']=True
     a.sell(sid,clock,quote,[x['id'] for x in a.live(sid)],'ACT_pause' if not a.risk_state['on'] else 'I_structure_exit');continue
    for x in a.live(sid):
     if x['kind']=='core':
      known_floor=self.facts.floor(sid,at,'I')
      if known_floor is not None:a.jmeta[x['id']]['last_core_line']=str(known_floor)
      continue
     if x['kind']!='add' or x['id'] in a.sell_layers.get(sid,set()):continue
     if D(str(row.close))<=x['floor']:a.sell(sid,clock,quote,[x['id']],'CP1_add_protection')
     else:
      floor=self.facts.floor(sid,at,'I')
      if floor is not None:x['floor']=max(x['floor'],floor)
      if cp is not None and bool(cp.receipt):x['floor']=max(x['floor'],D(str(cp.candidate)))
   a.sync(at);self.industry(a,at)
   for rank,sid in enumerate(ordered):
    cpr=self.receipts[sid].get(gidday(at));roles=[];why=[];held=bool(a.quantity(sid));epoch=self.global_watch.get(sid);sector=self.sector_by_sid[sid]
    if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
    if cpr and continuing[sid].q is True:roles.append('mobile')
    if not a.risk_state['on']:why.append('ACT_paused')
    if sid in a.exits:why.append('exit_pending')
    if sid in a.buys:why.append('buy_pending')
    if event[sid].q is not True and not (cpr and continuing[sid].q is True):why.extend(event[sid].reasons or ['no_fresh_signal_or_Q'])
    self.opportunities.append(dict(account=a.label,day=gidday(at),sid=sid,sector=sector,rank=rank,core_Q=event[sid].q,mobile_Q=continuing[sid].q,CP1_id=cpr['receipt_id'] if cpr else None,roles=roles,held=held,barriers=why))
    if why or not roles:continue
    q=self.market.quote(sid,at);floor=self.facts.floor(sid,at,'I')
    if q is None or floor is None:continue
    for role in roles:
     fline=max(floor,D(str(self.cp[sid].loc[day,'candidate']))) if role=='mobile' else floor;budget=min(a.current_nav*D('.02'),max(Z,a.current_nav*D('.1')-a.quantity(sid)*q.raw_price));i=dict(sid=sid,clock=clock,quote=q,budget=budget,cap=q.quantity.buy_floor(int(budget/q.raw_price)),weight=1.,group=0,score=sd[sid].rank.read(clock),kind='add' if role=='mobile' else 'core',role=role,floor=fline,epoch=epoch,reason='fresh_CP1_mobile' if role=='mobile' else 'I_early_core',rank=rank,CP1_id=cpr['receipt_id'] if role=='mobile' else None,CP1_trace=cpr if role=='mobile' else None)
     if role=='core':LR.resize_core(i,a.current_nav,self.facts.factor(sid,at))
     if not i.get('size_reject') and i['cap']>0:a.pending.append(i)
     else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=role,result=i.get('size_reject','no_nominal_gap')))
   a.decisions.append(dict(at=at,nav=a.current_nav,on=a.risk_state['on'],intents=[{k:v for k,v in i.items() if k not in ['quote','clock','CP1_trace']} for i in a.pending]));bal=a.sync(at);a.check();self.daily.append(dict(account=a.label,at=at,**bal,on=a.risk_state['on'],positions={s:p.shares for s,p in a.positions.items()},layers=[dict(x,**a.jmeta[x['id']]) for x in a.layers if x['qty']],pending_sells=tuple(a.exits),pending_intents=len(a.pending),counts=dict(a.counts),pool_probe=a.budget.resources('probe'),pool_confirmed=a.budget.resources('confirmed'),shared_loss=a.budget.shared_loss));self.daily_bridge(a,at,bal)
```

原文直接可见：CORE需event Q、flat、epoch未用；mobile需fresh receipt和continuing Q，不要求已有CORE。mobile先用min(2%NAV,10%NAV−原股市值)，CORE在下一行被resize覆盖。ACT/I退出先于mobile逐层检查；mobile先检旧floor再max更新新I/CP线。

### CORE的I价格退出上游

CORE不是没有价格出口：I生成器active时先检查旧floor，令target=False后由J225–229全股提交退出；未触发才ratchet。这里保留代码原先后顺序。

[cache.py:25–34](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/native-I-cache-interface-20261031/cache.py:25)

```python
 for c in ['volume_ratio','high_effort','declined']:e[c]=state[c]
 e['decline_candidate']=False;e['candidate_lower']=np.nan;e['candidate_reclaim']=np.nan
 base,_=e0_policy(e);assert not base.pending.fillna(0).any()
 g=x[['grade','strength_ready','fresh_up','acute_down']].rename(columns={'strength_ready':'ready'});out=project(e,base,g,'G1_I')
 keep=x[['close','segment_id']].copy()
 for mode,frame in [('e0',base),('i',out)]:
  for c in ['target','floor']:keep[mode+'_'+c]=frame[c]
 keep['i_buy']=out.buy_event
 for c in ['grade','fresh_up','acute_down','ready']:keep['g_'+c]=g[c]
 keep['e0_ready']=base.ready;keep['factor']=signal.adjustment_factor.reindex(keep.index);keep['raw_close']=signal.raw_close.reindex(keep.index);keep=keep[COLS]
```

[policies_g1.py:16–35](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:16)

```python
        shadow=bool(b.target);ready=bool(a.ready);entered=exited=0;reason='';entry_kind=''
        fresh=bool(a.fresh_up) if ready else False
        warm=ready and a.grade>=2
        cold=ready and (a.grade<=-2 or bool(a.acute_down))
        if active:
            if not shadow or float(r.close)<=floor:reason='E0_structure_boundary'
            elif use_x and cold:reason='G1_cold_or_acute'
            if reason:active=False;exited=1
            elif np.isfinite(b.floor):floor=max(floor,float(b.floor))
        # Entry-only is a new-evidence gate and restoration channel, while
        # exit-only preserves E0's new-cycle entry stream. An exit-only entry
        # is first checked by the extra exit rule on the next observation,
        # matching the original sensitive-policy ordering.
        opportunity=shadow and warm and (bool(b.entered) or fresh) if use_i else bool(b.entered)
        if not active and not exited and opportunity:
            active=True;entered=1;floor=float(b.floor)
            entry_kind='G1_fresh_warm_evidence' if use_i else str(b.entry_kind)
        buy=bool(active and opportunity) if use_i else bool(active)
        rows.append(dict(date=dt,target=int(active),entered=entered,exited=exited,floor=floor if active or exited else np.nan,exit_line=floor if active or exited else np.nan,buy_event=buy,entry_kind=entry_kind,exit_reason=reason,grade=a.grade))
    return pd.DataFrame(rows).set_index('date')
```

## 3. CORE定量与nextOPEN preview：原公式

CORE风险预算是参考线/slip/费用假设的单笔上限，不是保证实际亏损；mobile不会进入kind==core这一项risk_budget复核。

[study.py:16–31](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:16)

```python
RISK=D('.0025');SLIP=D('.0005')
CASES=['601869.SH','300502.SZ','300308.SZ','688498.SH','688048.SH','688256.SH','002987.SZ','002439.SZ','688041.SH']

def fees(qty,price,schedule,side,par=None):
 return sum(schedule.incremental(side,D(qty)*price,{}, {},ONE,shares=qty,par_value=par).values(),ZERO) if qty else ZERO
def protection_risk(qty,price,floor,schedule,par=None):
 return max(ZERO,D(qty)*(price-floor*(ONE-SLIP))+fees(qty,price,schedule,'buy',par)+fees(qty,floor*(ONE-SLIP),schedule,'sell',par))
def maximum_quantity(rule,cap,allowed):
 """Largest legal original order, never fabricate a sub-minimum order."""
 if cap<rule.buy_minimum or not allowed(rule.buy_minimum):return 0
 lo,hi=0,(cap-rule.buy_minimum)//rule.buy_step
 while lo<hi:
  mid=(lo+hi+1)//2
  if allowed(rule.buy_minimum+mid*rule.buy_step):lo=mid
  else:hi=mid-1
 return rule.buy_minimum+lo*rule.buy_step
```

[study.py:42–66](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:42)

```python
def resize_core(i,nav,factor):
 q=i['quote'];floor=i['floor']/factor;ref=q.raw_price*(ONE+SLIP);risk=nav*RISK;grosscap=nav*D('.1')
 i.update(risk_budget=risk,frozen_floor_raw=floor,signal_price=q.raw_price,reference_price=ref)
 if floor<=0 or floor>=q.raw_price:i.update(budget=ZERO,cap=0,size_reject='invalid_protection');return
 cap=maximum_quantity(q.quantity,int(grosscap/ref),lambda n:protection_risk(n,ref,floor,q.fees,q.par_value)<=risk)
 if not cap:i.update(budget=ZERO,cap=0,size_reject='minimum_unit_exceeds_risk_or_nominal_cap');return
 # Maximum gross reservation at the frozen share cap, without an arbitrary gap buffer.
 stop=D(cap)*floor*(ONE-SLIP);sellfee=fees(cap,floor*(ONE-SLIP),q.fees,'sell',q.par_value);lo=int(D(cap)*ref*100);hi=int(grosscap*100)
 while lo<hi:
  mid=(lo+hi+1)//2;b=D(mid)/100
  if b+fees(cap,b/D(cap),q.fees,'buy',q.par_value)-stop+sellfee<=risk:lo=mid
  else:hi=mid-1
 i.update(budget=D(lo)/100,cap=cap,size_reject=None)

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

## 4. 实际No60 route/request/migrate（静态还原，未执行）

对应P17–34。下列txt保存的是P会在内存compile/exec的完整字符串，但本次仅read/replace/write，没有执行。原路径中的derived_model_no_confirmed60.py/derived_route_on.py是compile标签，不能据此假定已有物理文件。

[EFFECTIVE_NO60_ROUTE_SOURCE.txt:1–29](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/current_strategy_source_dossier_v1/position_execution/EFFECTIVE_NO60_ROUTE_SOURCE.txt:1)

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

[EFFECTIVE_NO60_MODEL_SOURCE.txt:188–206](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/current_strategy_source_dossier_v1/position_execution/EFFECTIVE_NO60_MODEL_SOURCE.txt:188)

```python
    def migrate(self, sector):
        s = self.sectors[sector]
        if s.level == 0 or not s.active:
            return False
        if any(o.sector == sector and o.attempt == s.attempt and o.pool == 'probe' and o.qty > 0
               and o.status in ('open', 'cancel_pending') for o in self.orders.values()):
            s.status = 'confirmed_unfunded'
            return False
        moved = sum(x.qty*self.prices[x.stock] for x in self.lots if x.sector == sector and x.attempt == s.attempt and x.pool == 'probe')
        pending_fees = sum(o.qty*o.fee_per_share for o in self.orders.values()
                           if o.status in ('open', 'cancel_pending'))
        before = (self.cash, self.nav, self.resources(), self.shared_loss)
        for x in self.lots:
            if x.sector == sector and x.attempt == s.attempt and x.pool == 'probe':
                x.pool = 'confirmed'
        s.status = 'confirmed' if s.level == 1 else 'expanded'
        assert before == (self.cash, self.nav, self.resources(), self.shared_loss)
        return True
```

[EFFECTIVE_NO60_MODEL_SOURCE.txt:207–260](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/current_strategy_source_dossier_v1/position_execution/EFFECTIVE_NO60_MODEL_SOURCE.txt:207)

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
        pc, pr, _ = self.resources(pool)
        sc, sr, _ = self.resources(sector=sector)
        _, ar, reserve = self.resources()
        pending_fees = sum(o.qty*o.fee_per_share for o in self.orders.values()
                           if o.status in ('open', 'cancel_pending'))
        # Known execution fees cannot make an at-cap reservation violate its own cap on fill.
        budget_nav = self.nav - pending_fees - qty*fee_per_share
        failures = []
        if reserve + qty*(limit+fee_per_share) > self.cash + 1e-9: failures.append('cash')
        if pool == 'probe' and pc+cap > 0.10*budget_nav + 1e-9: failures.append('pool_capital')
        if pool == 'probe' and pr+risk > .005*budget_nav + 1e-9: failures.append('probe_risk')
        sector_fraction = .02 if probe_request else (0.02, 0.10, 0.20)[s.level]
        if sc+cap > sector_fraction*budget_nav + 1e-9: failures.append('sector_capital')
        if sr+risk > .01*budget_nav + 1e-9: failures.append('sector_risk')
        if failures:
            if pool == 'confirmed': s.status = 'confirmed_unfunded'
            return ','.join(failures)
        self.prices.setdefault(stock, limit)
        self.orders[oid] = Order(oid, stock, sector, s.episode, pool, qty, limit, floor, fee_per_share)
        self.orders[oid].role = role
        self.orders[oid].created_bar, self.orders[oid].expiry_bar = bar, order_expiry_bar
        self.orders[oid].attempt = s.attempt
        return 'reserved'
```

state前后须按原文读：route先检查/搜最大合法q；q=0不调用request。request进入后先写stock_requests，mobile凭证在资源检查前加入consumed；reserved才产生预算Order。CORE只走probe；mobile可在行业level>0时尝试confirmed，取最大合法量、相同数量probe优先。原cash/stock/sector/probe限制仍在；本生效route/request没有account_risk3%或confirmed60%。

### 继承资源、已损和行业stage

[joint_v3.py:15–19](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:15)

```python
class Budget(V.Contract):
 def __init__(self,expand):self.expand=expand;self.receivable_equity=0.;super().__init__(nav=1e6,cash=1e6,shared_loss_budget=20000,exhausted_policy='record_only')
 @property
 def nav(self):return super().nav+self.receivable_equity
 def migrate(self,sector):return super().migrate(sector) if self.expand else False
```

[model.py:83–117](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:83)

```python
    @property
    def shared_loss(self):
        return sum(self.losses.values())

    def loss(self, sector, episode, amount):
        key = (sector, episode)
        self.losses[key] = self.losses.get(key, 0.) + amount
        if self.exhausted_policy != 'record_only' and self.shared_loss >= self.loss_budget:
            for order in self.orders.values():
                if order.pool == 'probe' or self.exhausted_policy == 'all_new_risk':
                    self.cancel(order.oid)  # Never release reservation without ack.

    def start(self, sector, episode, bar):
        old = self.sectors.get(sector)
        if old and old.episode == episode:
            return
        if old:
            self.invalidate(sector, old.episode, bar=bar)
        # Old positions/orders continue to consume resources and preserve original episode.
        self.sectors[sector] = Sector(episode, bar, status='awaiting_first_cp1',
                                      failed_bar=old.failed_bar if old else -1, episode_started=bar)
        self.audit.append(('episode', sector, episode))

    def resources(self, pool=None, sector=None):
        lots = [x for x in self.lots if (pool is None or x.pool == pool)
                and (sector is None or x.sector == sector)]
        orders = [x for x in self.orders.values() if x.qty > 0 and
                  x.status in ('open', 'cancel_pending') and
                  (pool is None or x.pool == pool) and
                  (sector is None or x.sector == sector)]
        capital = sum(x.qty*self.prices[x.stock] for x in lots) + sum(x.qty*x.limit for x in orders)
        risk = sum(x.qty*max(0., self.prices[x.stock]-x.floor) for x in lots)
        risk += sum(x.qty*max(0., x.limit-x.floor) for x in orders)
        reserve = sum(x.qty*(x.limit+x.fee_per_share) for x in orders)
        return capital, risk, reserve
```

[model.py:127–151](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:127)

```python
    def industry(self, token, bar):
        if not self.valid(token, 'industry_cp1', bar) or token.event_id in self.consumed:
            return 'rejected'
        s = self.sectors[token.sector]
        if token.confirmed_time <= s.failed_bar or token.end <= s.failed_bar:
            return 'not_new_progress'
        if bar <= s.last_bar or token.end <= s.last_end or token.confirmed_time <= s.last_evidence_time:
            return 'not_new_progress'
        if token.confirmed_time != bar:
            self.audit.append(('late_industry_evidence_audit_only', token.event_id, bar))
            return 'late_evidence_audit_only'
        self.consumed.add(token.event_id)
        s.last_bar, s.last_end = bar, token.end
        s.last_evidence_time = token.confirmed_time
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
        self.audit.append(('industry_confirmation', token.event_id, s.level))
```

[model.py:166–186](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:166)

```python
    def invalidate(self, sector, episode, *, bar):
        s = self.sectors[sector]
        assert s.episode == episode
        s.active, s.status = False, 'invalidated'
        s.failed_bar = max(s.failed_bar, bar)
        for o in self.orders.values():
            if o.sector == sector and o.episode == episode: self.cancel(o.oid)

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

resources中的risk为mark到floor正距离；mark<=floor可能是0，但capital/真实持股并未消失。cancel_pending在ACK前仍占用。shared_loss_budget=20000且record_only，因此实际已损记录不等于耗尽后停止新增。

## 5. PVR只改股票slot，不修改数量或保护

[native_rank.py:47–91](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:47)

```python
def priority_plan(intents, score_at, day):
    """Pure planning: preserve unique-stock original slots, not role slots."""
    ordered = sorted(intents, key=lambda i: (i['rank'], i['role'] != 'core'))
    original = []; rank = {}; roles = {}
    for i in ordered:
        sid = i['sid']
        if sid not in rank:
            original.append(sid); rank[sid] = i['rank']; roles[sid] = []
        assert rank[sid] == i['rank'], ('inconsistent same-stock original key', sid)
        assert i['role'] not in roles[sid], ('duplicate native role', sid)
        roles[sid].append(i['role'])
    assert len(set(rank.values())) == len(rank), 'original stock priority keys must be unique'
    values = {s: score_at(s, day) for s in original}
    values = {s: float(v) if v is not None and math.isfinite(v) else None for s, v in values.items()}
    ready = [s for s in original if values[s] is not None]
    oldpos = {s: n for n, s in enumerate(original)}
    ready.sort(key=lambda s: (-round(values[s], 12), oldpos[s]))
    ready_iter = iter(ready)
    final = [s if values[s] is None else next(ready_iter) for s in original]
    assert set(final) == set(original) and len(final) == len(original)
    assert all(final[n] == s for n, s in enumerate(original) if values[s] is None)
    # Retain original numeric slot keys (including full-universe rank gaps).
    slots = [rank[s] for s in original]
    keys = {s: slots[n] for n, s in enumerate(final)}
    finalpos = {s: n for n, s in enumerate(final)}
    return keys, [dict(sid=s, day=day, original_H1_rank=rank[s], priority_rank=keys[s],
                      original_slot=oldpos[s], final_slot=finalpos[s], PVR=values[s],
                      PVR_ready=values[s] is not None, roles=roles[s]) for s in original]

def apply_priority(account, score_at, day):
    """Only rank keys change; original target/price/floor/role/receipt stay exact."""
    keys, log = priority_plan(account.pending, score_at, day)
    before = [{k: v for k, v in i.items() if k != 'rank'} for i in account.pending]
    d = account.decisions[-1]
    assert str(d['at'])[:10] == day
    by = {r['sid']: r for r in log}
    added = {'original_H1_rank', 'priority_rank', 'PVR_score', 'PVR_ready', 'priority_policy'}
    for i in account.pending+d['intents']:
        r = by[i['sid']]
        i.update(original_H1_rank=r['original_H1_rank'], priority_rank=keys[i['sid']],
                 PVR_score=r['PVR'], PVR_ready=r['PVR_ready'], priority_policy=POLICY)
        # Compatibility alias consumed by the UNCHANGED native opening sort.
        # The original H1 key/score and explicit frozen new key remain separate.
        i['rank'] = i['priority_rank']
    assert before == [{k: v for k, v in i.items() if k != 'rank' and k not in added} for i in account.pending]
```

[native_rank.py:115–120](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:115)

```python
    def planning(self, at):
        J.Runner.planning(self, at)
        if self.rank_mode == 'H1': return
        for a in self.accounts.values():
            log = apply_priority(a, SCORES.at, str(at.date()))
            self.rank_log.extend(dict(account=a.label, **r) for r in log)
```

## 6. OPEN真实顺序：先退出/结算，再预留，最后查询成交代理

state前：上CLOSE冻结pending意图、尚未完成退出。OPEN用已知raw OPEN重验冻结cap/budget与日期规则。每只股票成功reserve一次即进done；CORE兼容先序仍在。全部资金预留完成后才查买入window，不能拿当日完整H/L/volume先挑可成交者再重排钱。

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

### 资金预留原文

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

[joint_v3.py:92–136](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:92)

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
  return r
 def fill_exit(self,sid,w):
  before={x['id']:dict(x) for x in self.live(sid)};r=super().fill_exit(sid,w)
  if r:
   for part in self.trades[-1]['parts']:
    meta=self.jmeta[part['layer']];fee=float(r.fees_cny)*part['shares']/r.shares;loss=max(0.,meta['unit_cost']-float(r.gross_cny/D(r.shares)))*part['shares']+fee;self.budget.loss(meta['sector'],meta['episode'],loss)
   self.journal.append(dict(kind='real_sell_fill',at=w.at,sid=sid,shares=r.shares,price=r.gross_cny/D(r.shares),fees=r.fees_cny,parts=self.trades[-1]['parts']));self.sync(w.at)
  return r
```

### actual fill才建真实层、消费CORE epoch；退出按实际parts归属

[pilot.py:59–88](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:59)

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

[pilot.py:104–115](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:104)

```python
 def sell(self,sid,clock,quote,ids,reason):
  ids=set(ids)
  for z in self.live(sid):
   if z['id'] in ids:z['reason']=reason
  ids|=self.sell_layers.get(sid,set());self.sell_layers[sid]=ids
  shares=sum(z['qty'] for z in self.live(sid) if z['id'] in ids)
  if not shares:return
  if sid not in self.exits:super().request_reduction(quote,clock,shares)
  else:
   ex=self.exits[sid];ex.remaining_target=shares
   if shares==self.quantity(sid):ex.purpose='structure_exit';ex.remaining_target=None
  self.log('pilot_layer_exit',clock.decision_at,sid=sid,layers=sorted(ids),shares=shares,reason=reason)
```

## 7. 原实际成交、容量和结算：不以发单替代成交

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

[sector_account.py:688–809](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:688)

```python
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

卖出可卖量按真实T+1 lot、dated卖出数量规则和window容量取；partial只改变真实成交部分。退出请求不预加现金；settlement到期才释放。FastMarket容量含执行日完整volume及H/L postcheck，仅属于原成交代理，不是OPEN已知授信输入。

## 8. ACT的原状态转换（不是新规则）

[risk_policy.py:8–29](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py:8)

```python
def advance(state,nav,flat,fast,breakout,mode):
 s=dict(state);s['peak']=max(s['peak'],nav) if s['on'] else s['peak'];dd=1-nav/s['peak'];event=None;threshold=D('.1') if mode=='ACT10_BREAK' else D('.2')
 if s['on']:
  if dd>=threshold:
   s.update(on=False,saw_off=not fast);event='pause'
 else:
  s['saw_off']=s['saw_off'] or not fast
  recover=(s['saw_off'] and fast and not s['previous_fast']) if mode=='ACT20_FAST' else breakout
  if flat and recover:
   s.update(on=True,peak=nav,episode=s['episode']+1,saw_off=False);event='resume'
 s['previous_fast']=fast
 return s,dd,event

def step(a,at,mode):
 if mode=='CONTROL':return
 if not hasattr(a,'risk_state'):a.risk_state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0)
 day=pd.Timestamp(at.date());i=RECOVERY.index.searchsorted(day,side='right')-1
 if i<0:fast=False;br=False
 else:r=RECOVERY.iloc[i];fast=bool(r.fast_on);br=bool(r.breakout) if RECOVERY.index[i]==day else False
 flat=not any(p.shares for p in a.positions.values()) and not a.exits and not a.buys
 a.risk_state,dd,event=advance(a.risk_state,a.current_nav,flat,fast,br,mode)
 a.log('risk_checkpoint',at,policy=mode,nav=a.current_nav,episode_drawdown=dd,flat=flat,fast=fast,breakout=br,event=event,**a.risk_state)
```

以上为真实源文本/静态派生关系；本件不提出更改、不产生收益/回测结论。源SHA与摘录范围见SOURCE_SHA256.json；effective文本SHA亦已绑定。
