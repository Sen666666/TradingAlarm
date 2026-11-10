# 当前连续账户基线：源码原文与调用顺序

范围为已完成BASELINE账户实际使用的PVR_SLOT1_NO_CONFIRMED60_ONLY及其冻结输入，不包含未实施的共享风险方案。所有片段只读取文件，未import/执行策略、模型、回测或新测试。

按模块阅读：

- [E0、事件底层、I_target/i_buy](e0_i/EVIDENCE.md)
- [CP原状态机、PVR公式与实际排序](cp_pvr/EVIDENCE.md)
- [CORE/MOBILE、预算、仓位与真实执行](position_execution/EVIDENCE.md)
- [ACT状态与实际RECOVERY/BREAK63调用](act/EVIDENCE.md)
- [盈新原六层交易链与字段](yingxin_chain/EVIDENCE.md)

## 实际选择BASELINE类

[run_account.py:14](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/run_account.py:14)，原行14—26。BASELINE选择A.Runner；起始资金和空仓断言见原文。

```python
  shared,receipts,cp,states,ir,identity=V.inputs(window)
  sources=A.source_freeze();sources.update({str(p):sha(p) for p in [Path(__file__),O/'load_inputs.py',O/'PROTOCOL.txt',O/'STATE_MACHINE_FREEZE.json']})
  if arm=='BASELINE':cls=A.Runner;tool_manifest=None
  else:
   from indicator_provider import IndicatorProvider
   from native_adapter.early_adapter import build_runner_class
   provider=IndicatorProvider();cls=build_runner_class(A,provider,arm);tool_manifest=provider.manifest_sha256
   for p in [O/'indicator_provider.py',O/'native_adapter/early_adapter.py',O/'indicators/MANIFEST.json']:sources[str(p)]=sha(p)
  r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=sources
  a=r.accounts['B'];assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits
  save(out/'RUN_METADATA.json',dict(arm=arm,window=window,start=J.START,end=J.END,fresh_cash=1000000,no_checkpoint_import=True,yearly_reset=False,source_freeze=sources,input_identity=identity,tool_manifest_sha256=tool_manifest,load_seconds=time.monotonic()-started,authorization='parent delegated explicit local complete-account tests; all frozen arms reported; no live trading'))
  print('NATIVE_ACCOUNT_STARTED',arm,window,'load',round(time.monotonic()-started,2),flush=True)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,seconds,end=J.END)
```

## No60实际绑定

[native_adapter.py:11](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:11)，原行11—40。request/route是覆盖后的函数；不要用J原route冒充实际No60。

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

## 每日事件调用顺序

[launch_v3.py:85](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/launch_v3.py:85)，原行85—104。先settle/actions/payments，OPEN执行opening，cutoff执行planning。

```python
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

## CLOSE中的I状态、epoch和两种资格

[joint_v3.py:213](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)，原行213—219。event使用原I买事件；continuing替换buy_allowed为市场buyable。key来自i_target和segment。

```python
 def planning(self,at):
  clock,stocks,sectors=self.facts.packet(at,'I');sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};buyable=self.market.market_buyable(at);day=pd.Timestamp(at.date());event={};continuing={}
  for sid,s in sd.items():
   row=self.facts.row(sid,at);key=(bool(row.i_target),int(row.segment_id)) if row is not None else (False,-1)
   if self.last_epoch.get(sid)!=key:self.epoch[sid]+=1;self.global_watch.pop(sid,None);self.last_epoch[sid]=key
   ep=(key[1],self.epoch[sid]);event[sid]=BP.A.eligibility(s,ss,clock,'S0');continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
   if event[sid].q is True:self.global_watch[sid]=ep
```

## CLOSE保护、退出、CORE/MOBILE入口及原预算

[joint_v3.py:222](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:222)，原行222—258。row.close和CP/I是本CLOSE已知行；先检查旧保护，再更新；角色和预算逐行见原文。

```python
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
```

## 原CORE风险函数

[study.py:16](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:16)，原行16—31。SLIP、RISK、保护风险及合法整数搜索。

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

## CORE的CLOSE定量与OPEN preview

[study.py:42](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:42)，原行42—66。factor把调整域floor转raw；OPEN以op计算，且只有kind=core重验risk_budget。

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

## PVR在原planning之后改rank

[native_rank.py:115](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:115)，原行115—120。排序细节和原分数生成公式另见cp_pvr/EVIDENCE.md。

```python
    def planning(self, at):
        J.Runner.planning(self, at)
        if self.rank_mode == 'H1': return
        for a in self.accounts.values():
            log = apply_priority(a, SCORES.at, str(at.date()))
            self.rank_log.extend(dict(account=a.label, **r) for r in log)
```

## OPEN中的真实次序

[joint_v3.py:302](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:302)，原行302—324。先卖出/结算；按rank、同股CORE优先预留；全部融资决策结束后才查买入执行窗口。

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

## I_target与i_buy原状态机

[policies_g1.py:6](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:6)，原行6—35。实际缓存调用G1_I；active输出target，buy输出buy_event；G1_I的use_x为False。

```python
def project(e,base,g,kind):
    if kind not in ['G1_I','G1_X','G1_IX']:raise ValueError(kind)
    use_i=kind in ['G1_I','G1_IX'];use_x=kind in ['G1_X','G1_IX']
    active=False;floor=math.nan;segment=None;rows=[]
    for dt,r in e.iterrows():
        b=base.loc[dt];a=g.loc[dt]
        if r.segment_id!=segment:active=False;floor=math.nan;segment=r.segment_id
        valid=bool(r.valid_price_observation)
        if not valid:
            rows.append(dict(date=dt,target=np.nan,entered=0,exited=0,floor=np.nan,exit_line=np.nan,buy_event=False,entry_kind='',exit_reason='',grade=a.grade));continue
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

## ACT原状态与step

[risk_policy.py:8](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py:8)，原行8—29。当前J调用ACT20_BREAK；实际RECOVERY路径覆盖及BREAK63生成原文另见act/EVIDENCE.md。

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

