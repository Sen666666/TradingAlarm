# 当前No60的ACT源码证据

范围：只亲读当前文件、摘取行号、核静态调用链和已有BASELINE元数据的文件身份；没有import策略模块、调用advance/step/compute_recovery、模型、数据重算、账户、测试或回测。v4设计与故障理论追加已停止。以下描述代码状态，不提出新规则。

## 1. 当前runner确实调用ACT20_BREAK

已完成BASELINE入口选`A.Runner`；A继承N.Runner，声明planning为N的planning、opening为J的opening。N.planning先完整调用J.planning，再应用PVR优先级。J在收盘planning内明确给step传`ACT20_BREAK`，不是依赖engine的默认RISK_MODE。

[run_account.py:14](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/run_account.py:14)

```python
14:   shared,receipts,cp,states,ir,identity=V.inputs(window)
15:   sources=A.source_freeze();sources.update({str(p):sha(p) for p in [Path(__file__),O/'load_inputs.py',O/'PROTOCOL.txt',O/'STATE_MACHINE_FREEZE.json']})
16:   if arm=='BASELINE':cls=A.Runner;tool_manifest=None
17:   else:
18:    from indicator_provider import IndicatorProvider
19:    from native_adapter.early_adapter import build_runner_class
20:    provider=IndicatorProvider();cls=build_runner_class(A,provider,arm);tool_manifest=provider.manifest_sha256
21:    for p in [O/'indicator_provider.py',O/'native_adapter/early_adapter.py',O/'indicators/MANIFEST.json']:sources[str(p)]=sha(p)
22:   r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=sources
23:   a=r.accounts['B'];assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits
24:   save(out/'RUN_METADATA.json',dict(arm=arm,window=window,start=J.START,end=J.END,fresh_cash=1000000,no_checkpoint_import=True,yearly_reset=False,source_freeze=sources,input_identity=identity,tool_manifest_sha256=tool_manifest,load_seconds=time.monotonic()-started,authorization='parent delegated explicit local complete-account tests; all frozen arms reported; no live trading'))
25:   print('NATIVE_ACCOUNT_STARTED',arm,window,'load',round(time.monotonic()-started,2),flush=True)
26:   with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,seconds,end=J.END)
```

[native_adapter.py:16](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:16)

```python
16: class Runner(N.Runner):
17:     route=P.ROUTES[True]
18:     def __init__(self,*args,**kwargs):
19:         self._cap_bootstrap=True
20:         super().__init__(*args,**kwargs)
21:         self.remove_confirmed60=True
22:         for a in self.accounts.values():a.budget.__class__=NoConfirmed60Budget
23:         self.integration_policy=POLICY+':'+self.rank_mode
24:         self._cap_bootstrap=False
25:         self.assert_native_wiring()
26: 
27:     def assert_native_wiring(self):
28:         bootstrap=getattr(self,'_cap_bootstrap',False)
29:         assert self.integration_policy==(N.POLICY if bootstrap else POLICY)+':'+self.rank_mode
30:         assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
31:         assert self.opening.__func__ is J.Runner.opening
32:         assert self.planning.__func__ is N.Runner.planning
33:         assert self.route.__func__ is P.ROUTES[True]
34:         for a in self.accounts.values():
35:             assert type(a)is J.Account and type(a.budget)is (N.BASE.NoAccountBudget if bootstrap else NoConfirmed60Budget)
36:             if not bootstrap:
37:                 assert a.budget.request.__func__ is P.MOD.Contract.request
38:                 assert a.budget.migrate.__func__ is NoConfirmed60Budget.migrate
39:             for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
40:                 assert getattr(a,name).__func__ is getattr(J.Account,name)
```

[native_rank.py:115](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:115)

```python
115:     def planning(self, at):
116:         J.Runner.planning(self, at)
117:         if self.rank_mode == 'H1': return
118:         for a in self.accounts.values():
119:             log = apply_priority(a, SCORES.at, str(at.date()))
120:             self.rank_log.extend(dict(account=a.label, **r) for r in log)
```

静态继承：A.Runner → native_rank.Runner → account-risk-ablation.adapter.Runner → launch_v3.PreparedRunner → J.Runner。BASE只替换route/预算类别；A只替换No60 route/预算类别，未替换ACT函数。
[adapter.py:5](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/adapter.py:5)

```python
5: sys.path.insert(0,str(O.parent/'case-stage-ledger-20261031/v3'))
6: import launch_v3 as L
7: J=L.J
8: N=J.W.load('single_factor_budget_no_account',O/'model_without_account_check.py')
9: class NoAccountBudget(J.Budget):
10:  request=N.Contract.request
11: def enable(account):
12:  # Same initialized market attempt/consumption/resources; no reseeding or cash.
13:  account.budget.__class__=NoAccountBudget
14: env=dict(J.__dict__);exec((O/'route_without_account_check.py').read_text(),env)
15: class Runner(L.PreparedRunner):
16:  route=env['route']
17:  def __init__(self,*args,**kwargs):
18:   super().__init__(*args,policies=('B',),**kwargs)
19:   for a in self.accounts.values():enable(a)
```

## 2. peak、drawdown、pause、resume的原始代码

[risk_policy.py:8](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py:8)

```python
8: def advance(state,nav,flat,fast,breakout,mode):
9:  s=dict(state);s['peak']=max(s['peak'],nav) if s['on'] else s['peak'];dd=1-nav/s['peak'];event=None;threshold=D('.1') if mode=='ACT10_BREAK' else D('.2')
10:  if s['on']:
11:   if dd>=threshold:
12:    s.update(on=False,saw_off=not fast);event='pause'
13:  else:
14:   s['saw_off']=s['saw_off'] or not fast
15:   recover=(s['saw_off'] and fast and not s['previous_fast']) if mode=='ACT20_FAST' else breakout
16:   if flat and recover:
17:    s.update(on=True,peak=nav,episode=s['episode']+1,saw_off=False);event='resume'
18:  s['previous_fast']=fast
19:  return s,dd,event
```

代码读取：on时先把peak更新为max(peak,nav)，再计算`1-nav/peak`；当前模式ACT20_BREAK走阈值`.2`。达到或超过阈值把on置False。off时只有flat且恢复条件为True才把on置True，并把peak重设为当时nav、episode加1。当前模式恢复变量取breakout；ACT20_FAST的fast切换分支是代码中的另一mode，J当前没有传它。

初始化是首次缺risk_state时建立on=True、peak=1000000、episode=0；每次调用不重新初始化已有risk_state。

[risk_policy.py:21](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py:21)

```python
21: def step(a,at,mode):
22:  if mode=='CONTROL':return
23:  if not hasattr(a,'risk_state'):a.risk_state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0)
24:  day=pd.Timestamp(at.date());i=RECOVERY.index.searchsorted(day,side='right')-1
25:  if i<0:fast=False;br=False
26:  else:r=RECOVERY.iloc[i];fast=bool(r.fast_on);br=bool(r.breakout) if RECOVERY.index[i]==day else False
27:  flat=not any(p.shares for p in a.positions.values()) and not a.exits and not a.buys
28:  a.risk_state,dd,event=advance(a.risk_state,a.current_nav,flat,fast,br,mode)
29:  a.log('risk_checkpoint',at,policy=mode,nav=a.current_nav,episode_drawdown=dd,flat=flat,fast=fast,breakout=br,event=event,**a.risk_state)
```

flat严格定义为没有任何正实股、没有退出单、没有实际买单。代码不以没有planned intent、当前现金比例或共享loss余额代替flat。RECOVERY只查不晚于当日的最近一行；breakout仅在该行日期恰好等于当天才可为True，缺当日行不沿用旧breakout。

由这段状态赋值可以直接确认：恢复把peak改成当前nav；它未保持初始1000000作为每个后续episode的比较峰。这里仅陈述状态，不作宏观或绩效评价。

## 3. 当前使用的RECOVERY文件与BREAK63生成源

risk_policy.py第6行有默认CSV加载，但当前PreparedRunner会覆盖同一个`J.M.E.risk_policy.RECOVERY`。wire把M.O指向mainline-absolute-Q4；两份当前BASELINE元数据均绑定同一文件：`/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/recovery.csv`，SHA256=`76599d9013946bc5fc501a57b046f36a2868ad61f147ef1a6c73c9575b35906a`。因此不能只读risk_policy所在目录的默认recovery.csv就声称它是本No60的实际外部时钟。

[wire.py:9](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/wire.py:9)

```python
9: M=load('case_stage_original_full_domain',W/'mainline-I-quarter-2025Q3-20261031/adapter.py');C=M.C;BP=M.BP;LR=C.LR;D=C.D;Z=D(0)
10: START='2025-07-01';END='2026-03-31';CACHE=W/'case-stock-cp1-warmup-20261031';M.O=W/'mainline-absolute-Q4-20261031';M.END=END
```

[launch_v3.py:82](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/launch_v3.py:82)

```python
82:  def run_prepared(self,out,max_seconds,resume_after=None,end=None):
83:   # Original M.Pilot.run event construction/order. The only clock difference
84:   # is a strict skip of already completed checkpoint events on explicit resume.
85:   from datetime import datetime,time as dt
86:   end=end or J.END
87:   start=J.M.N.iso(J.START+'T15:10:00+08:00');finish=J.M.N.iso(end+'T15:10:00+08:00')
88:   cutoffs={x for x in self.market.cutoffs if start<=x<=finish};opens={x for x in self.market.sessions['A'] if start<=x<=finish}
89:   acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ) for d in self.actions_by_date}
90:   events=sorted(cutoffs|opens|{x for x in acts if start<=x<=finish});assert finish in cutoffs
91:   J.M.E.risk_policy.RECOVERY=pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:end]
92:   t=time.monotonic();last=resume_after
93:   for at in events:
94:    if resume_after is not None and at<=resume_after:continue
95:    if time.monotonic()-t>max_seconds:
96:     if last is not None:self.checkpoint(out,last)
97:     self.dump_joint(Path(out)/'partial');return False
98:    for a in self.accounts.values():a.settle_due(at)
99:    self._actions(at)
100:    for a in self.accounts.values():self._payments(a,at)
101:    if at in opens:
102:     for a in self.accounts.values():self.opening(a,at)
103:    if at in cutoffs:self.planning(at)
```

该CSV的生成脚本从原固定股票signal与原sector映射构roster，直接调用TradingAlarm.desk.refresh.compute_recovery，并另置fast_on=breadth>.6。

[experiment.py:19](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/experiment.py:19)

```python
19:  sys.path.insert(0,str(M.ROOT));from TradingAlarm.desk.refresh import compute_recovery
20:  src=M.RR/'a-share-selection-e0-20261024/prepared-v2';rec={r['series_id']:r for r in M.read(src/'manifest.json')['series']};meta=M.read(M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');signals={};absent=[]
21:  for sid in M.read(M.IC/'FREEZE.json')['stocks']:
22:   p=src/rec[sid]['files']['signal']['path'];assert M.sha(p)==rec[sid]['files']['signal']['sha256'];f=pd.read_parquet(p,columns=['close','amount','price_eligible','observed_bar','synthetic_event_bar','segment_id']).loc[:'2026-06-30']
23:   if (f.price_eligible&f.observed_bar&~f.synthetic_event_bar).any():signals[sid]=f
24:   else:absent.append(sid)
25:  roster=pd.DataFrame([dict(symbol=sid,sector_id=meta[sid]['sector_id']) for sid in signals]);z=compute_recovery(signals,roster);z['fast_on']=z.breadth.gt(.6);previous=pd.read_csv(OLD/'recovery.csv',index_col=0,parse_dates=True)
26:  differences={}
27:  for c in previous:
28:   old=previous[c];new=z.loc[previous.index,c]
29:   if c in ['breakout','fast_on']:np.testing.assert_array_equal(new,old);differences[c]=0
30:   else:
31:    np.testing.assert_allclose(new,old,rtol=1e-12,atol=1e-12,equal_nan=True);differences[c]=float(np.nanmax(np.abs(new.astype(float)-old.astype(float))))
32:  z.to_csv(O/'recovery.csv');assert time.monotonic()-t<120
```

[refresh.py:27](/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/desk/refresh.py:27)

```python
27: def compute_recovery(signals, roster):
28:     """Exact frozen market price clock and independently valid amount breadth."""
29:     returns={};mom={}
30:     for sid in roster.symbol:
31:         f=signals[sid];valid=(f.price_eligible&f.observed_bar&~f.synthetic_event_bar)
32:         raw=f.loc[valid];rs=[];ms=[]
33:         for _,g in raw.groupby('segment_id',sort=False):
34:             r=np.log(g.close).diff();q=g.amount/g.amount.shift().rolling(21,min_periods=21).median();u=r*np.minimum(1,np.sqrt(q));m=u.ewm(span=21,adjust=False).mean();ready=np.arange(len(g))>=64
35:             rs.append(r.where(ready));m.iloc[:64]=np.nan;ms.append(m)
36:         returns[sid]=pd.concat(rs).sort_index();mom[sid]=pd.concat(ms).sort_index()
37:     sector_r=[];sector_b=[]
38:     for sector,group in roster.groupby('sector_id'):
39:         sector_r.append(pd.concat({s:returns[s] for s in group.symbol},axis=1).mean(axis=1))
40:         f=pd.concat({s:mom[s] for s in group.symbol},axis=1);n=f.notna().sum(axis=1);sector_b.append((f.gt(0).sum(axis=1)/n).where(n>=5))
41:     r=pd.concat(sector_r,axis=1).mean(axis=1);price=np.exp(r.fillna(0)).cumprod()
42:     b=pd.concat(sector_b,axis=1);breadth=b.mean(axis=1).where(b.notna().sum(axis=1)>=8)
43:     z=pd.DataFrame(dict(market=price,prior_high63=price.shift().rolling(63,min_periods=63).max(),breadth=breadth));z['breakout']=(z.market>z.prior_high63)&(z.market.diff()>0)&(z.breadth>.6)
44:     return z
```

BREAK63准确条件见43行：market严格大于**排当前**的前63观察最高值，market当日差分为正，并且breadth>.6。不是读取官方指数的63日高点。该函数逐stock/segment生成log return与经金额调制的21-span平滑量，前64观察置warmup；行业内均值后行业等权合成market。breadth按行业内至少5个已知股票的正平滑量比例，再要求至少8个已知行业。这里没有重新运行生成器或逐行验证现存CSV。

## 4. 暂停状态在J中的实际限制和先后顺序

[joint_v3.py:213](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)

```python
213:  def planning(self,at):
214:   clock,stocks,sectors=self.facts.packet(at,'I');sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};buyable=self.market.market_buyable(at);day=pd.Timestamp(at.date());event={};continuing={}
215:   for sid,s in sd.items():
216:    row=self.facts.row(sid,at);key=(bool(row.i_target),int(row.segment_id)) if row is not None else (False,-1)
217:    if self.last_epoch.get(sid)!=key:self.epoch[sid]+=1;self.global_watch.pop(sid,None);self.last_epoch[sid]=key
218:    ep=(key[1],self.epoch[sid]);event[sid]=BP.A.eligibility(s,ss,clock,'S0');continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
219:    if event[sid].q is True:self.global_watch[sid]=ep
220:   ordered=sorted(sd,key=lambda sid:(-(sd[sid].rank.read(clock) if sd[sid].rank and sd[sid].rank.read(clock) is not None else -1),sid))
221:   for a in self.accounts.values():
222:    C.activate(a);a.expire_day_buys(at);a.current_nav=a.balance(at,self.market.marks(at,a.positions))['nav'];M.E.risk_policy.step(a,at,'ACT20_BREAK');a.pending=[]
223:    for sid in tuple(a.positions):
224:     row=self.facts.row(sid,at);cp=self.cp[sid].loc[day] if day in self.cp[sid].index else None;quote=self.market.quote(sid,at);assert quote
225:     if not a.risk_state['on'] or not bool(row.i_target):
226:      if not bool(row.i_target):
227:       for x in a.live(sid):
228:        if x['kind']=='core':a.jmeta[x['id']]['pending_I_exit_reference']=True
229:      a.sell(sid,clock,quote,[x['id'] for x in a.live(sid)],'ACT_pause' if not a.risk_state['on'] else 'I_structure_exit');continue
```

[joint_v3.py:241](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:241)

```python
241:    a.sync(at);self.industry(a,at)
242:    for rank,sid in enumerate(ordered):
243:     cpr=self.receipts[sid].get(gidday(at));roles=[];why=[];held=bool(a.quantity(sid));epoch=self.global_watch.get(sid);sector=self.sector_by_sid[sid]
244:     if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
245:     if cpr and continuing[sid].q is True:roles.append('mobile')
246:     if not a.risk_state['on']:why.append('ACT_paused')
247:     if sid in a.exits:why.append('exit_pending')
248:     if sid in a.buys:why.append('buy_pending')
249:     if event[sid].q is not True and not (cpr and continuing[sid].q is True):why.extend(event[sid].reasons or ['no_fresh_signal_or_Q'])
250:     self.opportunities.append(dict(account=a.label,day=gidday(at),sid=sid,sector=sector,rank=rank,core_Q=event[sid].q,mobile_Q=continuing[sid].q,CP1_id=cpr['receipt_id'] if cpr else None,roles=roles,held=held,barriers=why))
251:     if why or not roles:continue
```

收盘顺序：先取I packet/事件与原排序；逐账户expire_day_buys并读真实balance NAV；step(ACT20_BREAK)；清本次pending；再处理存量。on=False时对该股全部live layer请求ACT_pause退出，continue跳过该股其余持仓处理。随后新意图母体记录ACT_paused barrier，why非空不生成可执行pending。

[joint_v3.py:302](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:302)

```python
302:  def opening(self,a,at):
303:   C.activate(a)
304:   for sid in sorted(a.exits):
305:    win=self.market.window(sid,at,'sell',1)
306:    if win:a.fill_exit(sid,win)
307:   a.settle_due(at);a.sync(at);funded=[];done=set()
308:   for i in sorted([i for i in a.pending if i['clock'].earliest_execution_at==at],key=lambda x:(x['rank'],x['role']!='core')):
309:    sid=i['sid']
310:    if sid in done or sid in a.buys or sid in a.exits:continue
311:    raw=self.market.raw[sid];day=pd.Timestamp(at.date())
312:    if day not in raw.index or not np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='missing_open'));continue
313:    x,why=LR.preview(i,D(str(raw.loc[day].open)),self.facts.factor(sid,at),self.market.quantity(sid,at),self.market.fees(sid,at))
314:    if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
315:    x['known_open']=D(str(raw.loc[day].open))
316:    route,why=self.route(a,i,x,at)
317:    if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
318:    q,pool=route;a.reserve_quantity(i,q,x['price'],x['schedule'],at);a.sync(at);done.add(sid);funded.append((sid,i,x,q));self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='reserved',pool=pool,shares=q,price=x['price'],CP1_id=i.get('CP1_id')))
319:   # Execution proxies are consulted only after all H1-ranked funding decisions.
320:   for sid,i,x,q in funded:
321:    win=self.market.window(sid,at,'buy',1)
322:    if win:assert win.execution_price==x['price'];a.fill_buy(sid,win)
323:    else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='no_execution_window_after_reservation'))
324:   a.settle_due(at);a.sync(at);a.minimum_available=min(a.minimum_available,a.available);a.check()
```

下一OPEN先遍历已有exits调用原fill_exit，再settle/sync，随后才路由并预留新的买单，所有预留完成后才查买入execution window。此处没有在OPEN重新调用ACT step，也没有把发出卖请求当成已成交。

risk_policy.override函数在31–33行存在，但当前J.planning不调用它；当前暂停的实际路径是上列J225/J246。不能把这个未被J调用的helper当作当前pause唯一实现。

## 5. risk_policy模块对象的上游别名链

J经wire加载mainline adapter；该adapter的E=C.E；C从LR.BP.E取E；LR取probe pilot的E；probe pilot从PVR experiment取E；experiment优先加入ACT/code后import engine；ACT engine第3行import risk_policy。以下为真实文本链，不执行这些import。

[adapter.py:6](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-I-quarter-2025Q3-20261031/adapter.py:6)

```python
6: O=Path(__file__).resolve().parent;W=O.parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds'
7: def load(n,p):
8:  s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
9: C=load('mainline_frozen_L0',W/'lr1-cp1-add-preflight-20261031/adapter.py')
10: BP,LR,N,E,R,D=C.BP,C.LR,C.N,C.E,C.R,C.D
11: save,read,sha=C.save,C.read,C.sha
12: IC=W/'native-I-cache-interface-20261031';P=ROOT/'TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared'
```

[adapter.py:8](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/lr1-cp1-add-preflight-20261031/adapter.py:8)

```python
8: O=Path(__file__).resolve().parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
9: sys.path[:0]=[str(RR/'lot-risk-allocation-20261029/code'),str(RR/'probe-pyramid-pilot-20261029/code')]
10: import study as LR
11: BP=LR.BP;L,A,N,E,R=BP.L,BP.A,BP.N,BP.E,BP.R
```

[study.py:8](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:8)

```python
8: ROOT=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parents[1]
9: BASE=ROOT/'research_rounds/probe-pyramid-pilot-20261029'
10: sys.path.insert(0,str(BASE/'code'))
11: import pilot as BP
12: C,E,R,L,A,N=BP.C,BP.E,BP.R,BP.L,BP.A,BP.N
13: SNAP,CP,PV=BP.SNAP,BP.CP,BP.PV
```

[pilot.py:10](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:10)

```python
10: O=Path(__file__).resolve().parents[1];ROOT=O.parents[1]
11: sys.path.insert(0,str(ROOT/'research_rounds/pvr-act-comparison-20261027/code'))
12: import experiment as P
13: C,E,R=P.C,P.E,P.R
14: L,A,N=C.ledger,C.admission,C.native
```

[experiment.py:4](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/code/experiment.py:4)

```python
4: O=Path(__file__).resolve().parents[1]; ROOT=O.parents[1]
5: BASE=ROOT/'research_rounds/tech-finite-compound-20261026'
6: ACT=ROOT/'research_rounds/actual-risk-recovery-20261027'
7: FORM=ROOT/'research_rounds/pv-rank-q1-20261027/FORMULA.json'
8: sys.path[:0]=[str(ACT/'code'),str(BASE/'code')]
9: import common as C
10: import engine as E
11: import run_v2 as R
```

[engine.py:1](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py:1)

```python
1: """Finite capital replay using the original Decimal share/cash/fee ledger."""
2: from common import *
3: import risk_policy
4: RISK_MODE="CONTROL"
```

## 6. 本件边界

本件只确认ACT源码、当前选择入口与静态/既有元数据lineage。不把旧报告、探索卡、替代arm或尚未接线方法当当前规则；不重算历史恢复事件、收益或持仓覆盖。其它dossier片段到达后另作只读lineage核对，不改变本件源文件。
