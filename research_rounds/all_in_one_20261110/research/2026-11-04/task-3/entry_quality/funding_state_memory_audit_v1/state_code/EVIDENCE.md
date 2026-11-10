# 现 No60：probe / confirmed 状态与资金记忆源码

仅静态源码摘录、调用/继承关系与原字符串替换；无策略import/exec/模型、账户重放、回测或策略修改。所有引用都是绝对路径:行号。`EFFECTIVE_NO60_*.txt`是按现P原文静态还原的内存源码，不是新模型实现。

## 先读核心原文

行业升档不以同股已有持仓/盈利为前提：首次合法行业CP激活level0/probe，继续合法新行业CP才level1/2；原持仓与盈亏在资源/NAV/待单等环节间接影响可获资量。confirmed/expanded与真正有现金、无待单阻塞不是同一件事。

[model.py:127–152](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:127)

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
        return s.status
```

**现No60的migrate，不含原60%门：**

[EFFECTIVE_NO60_MODEL.txt:188–206](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/funding_state_memory_audit_v1/state_code/EFFECTIVE_NO60_MODEL.txt:188)

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

level>0且active，并且同attempt的probe open/cancel_pending已解除，才迁移该行业/attempt的probe lots。循环不限制role，所以已有CORE lot也能迁池；它只改pool，不改股数/成本/floor/cash/NAV/全局resources/shared_loss。新CORE订单只走probe，是另一个route规则，不能与已持CORE迁池混为一谈。

## 1. 真实No60覆盖链（模板与有效代码分开）

`E → A → N.BASE.NoAccountBudget/J.Budget → V`；A把实际对象class换NoConfirmed60Budget，只覆盖request/migrate；industry仍由J.Budget.industry调用V，valid/resources/loss等仍按原继承。BASE仅启用policies=('B',)，J给B设置expand=True，因此实际会执行行业升档与迁池；probe-only A对照不当作现No60行为。

[load_inputs.py:6–10](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/load_inputs.py:6)

```python
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sys.path.insert(0,str(B/'pvr_pool_feasibility'))
import native_adapter as A
N,J,L,IO=A.N,A.J,A.L,A.IO
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

[joint_v3.py:15–28](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:15)

```python
class Budget(V.Contract):
 def __init__(self,expand):self.expand=expand;self.receivable_equity=0.;super().__init__(nav=1e6,cash=1e6,shared_loss_budget=20000,exhausted_policy='record_only')
 @property
 def nav(self):return super().nav+self.receivable_equity
 def migrate(self,sector):return super().migrate(sector) if self.expand else False
 def industry(self,token,bar):
  if self.expand or not self.sectors[token.sector].active:return super().industry(token,bar)
  # Probe-only control inherits the same market attempt, but never raises its
  # financial level, migrates a pool, or cancels for promotion.
  s=self.sectors[token.sector]
  if not self.valid(token,'industry_cp1',bar) or token.event_id in self.consumed:return 'rejected'
  if token.confirmed_time<=s.failed_bar or token.end<=s.failed_bar or bar<=s.last_bar or token.end<=s.last_end or token.confirmed_time<=s.last_evidence_time:return 'not_new_progress'
  if token.confirmed_time!=bar:return 'late_evidence_audit_only'
  self.consumed.add(token.event_id);s.last_bar=bar;s.last_end=token.end;s.last_evidence_time=token.confirmed_time;self.audit.append(('probe_only_new_industry_evidence',token.event_id));return 'probe'
```

[joint_v3.py:166–175](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:166)

```python
class Runner(W.Harness):
 def __init__(self,shared,receipts,policies=('A','B'),*,stock_cp=None,industry_states=None,industry_receipts=None):
  if stock_cp is None:super().__init__(shared,False)
  else:
   # Same original harness initialization, with already-verified cache views
   # supplied instead of the old hard-coded77 filenames. No policy override.
   M.Pilot.__init__(self,policies=('L0',),shared=shared);self.gate_enabled=False
   self.cp=stock_cp;self.pv={sid:pd.Series(dtype=float,index=pd.DatetimeIndex([])) for sid in self.market.lines}
   assert set(self.cp)==set(self.market.lines)
  self.sector_by_sid={l.security_id:l.sector_id for l in self.bundle.lines};self.accounts={p:Account(p,self.market,self.facts,p=='B',self.sector_by_sid) for p in policies};self.receipts=receipts;self.opportunities=[];self.stage_events=[];self.funding=[];self.balance_audit=[]
```

P读取的model_without_account_check与route_without_account_check已经没有原全账户3%检查；P又删除confirmed迁池60%、request confirmed60%、route confirmed60%三项，probe10%仍在。原V188–208里的60%是**被覆盖模板**，不是现行migrate；精确diff另存 [NO60_TRANSFORM.diff](NO60_TRANSFORM.diff)，有效全文是 [EFFECTIVE_NO60_MODEL.txt](EFFECTIVE_NO60_MODEL.txt) / [EFFECTIVE_NO60_ROUTE.txt](EFFECTIVE_NO60_ROUTE.txt)。本次未执行其中任何策略代码。

## 2. 状态对象、episode与attempt到底记什么

[model.py:5–60](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:5)

```python
@dataclass(frozen=True)
class Evidence:
    event_id: str  # Canonical UNDERLYING evidence ID, not a per-symbol alias.
    sector: str
    source: str
    scale: str
    start: int
    end: int
    confirmed_time: int
    epoch: str
    stock: str = None
    attempt: str = None

@dataclass
class Sector:
    episode: str
    started: int
    level: int = 0
    last_bar: int = -1
    last_end: int = -1
    last_evidence_time: int = -1
    status: str = 'probe'
    active: bool = False
    attempt: str = None
    failed_bar: int = -1
    episode_started: int = 0

@dataclass
class Lot:
    batch: str
    stock: str
    sector: str
    episode: str
    pool: str
    qty: float
    cost: float
    floor: float
    role: str = 'core'
    attempt: str = None

@dataclass
class Order:
    oid: str
    stock: str
    sector: str
    episode: str
    pool: str
    qty: float  # Unfilled quantity, including cancel-pending quantity.
    limit: float
    floor: float
    fee_per_share: float = 0
    status: str = 'open'
    role: str = 'core'
    created_bar: int = 0
    expiry_bar: int = 0
    attempt: str = None
```

[model.py:95–125](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:95)

```python
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

    def valid(self, token, source, bar):
        s = self.sectors.get(token.sector)
        return bool(s and (source == 'industry_cp1' or s.active) and token.source == source and token.scale == '21' and
                    token.epoch == s.episode and
                    token.end >= s.episode_started and token.confirmed_time >= s.episode_started and
                    (source == 'industry_cp1' or (token.attempt == s.attempt and token.end >= s.started)) and
                    token.start <= token.end <= token.confirmed_time <= bar)
```

| 字段/事件 | 原码语义 |
|---|---|
| sector.episode | 原行业E0 episode；start同episode直接return，不每天重置 |
| active=False, awaiting_first_cp1 | 新episode已建，但还没第一次合法行业CP |
| active=True, level0, probe | 第一次合法行业CP开启attempt；attempt=episode:该CP event_id |
| active时继续合法新行业CP | level=min(2,level+1)，不是依据账户是否赚钱 |
| level1 / level2 | 金融容量级别；status在migrate成功后为confirmed / expanded |
| confirmed_unfunded | level可已升，但迁池/资金请求未能完成；不自动把level降回0 |
| original lot/order episode/attempt | 保存在每条真实资源上，新sector状态不会把旧资源改名或删除 |

**failure memory的精确强弱：** valid要求end/confirmed_time≥episode_started，stock还须active、token.attempt匹配且end≥该attempt.started。industry额外要求end和confirmed_time严格>failed_bar、bar/end/确认均新于已消费记录；formation_start只需≤end，并不要求formation_start_exclusive>failed_bar。预算控制器不检查重夺失败前全局高点，也不检查任何该股盈亏。CP上游有自己的市场计算，不能把此预算验证解释成从失败后才开始形成的完全独立新结构。

## 3. failure / reset / ACK：保留与清除哪些记忆

[model.py:154–186](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:154)

```python
    def observe(self, sector, bar, *, failure=False, token=None):
        if failure:
            self.invalidate(sector, self.sectors[sector].episode, bar=bar)
            return 'invalidated'  # Same-observation CP1 never restarts.
        if token is None: return self.sectors[sector].status
        assert token.sector == sector
        return self.industry(token, bar)

    def expire_orders(self, bar):
        for o in self.orders.values():
            if bar > o.expiry_bar: self.cancel(o.oid)

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

- invalidate只令active=False、status=invalidated、failed_bar取max，并cancel该episode订单；没有卖出lots、没有迁回probe、没有清losses/consumed/stock_requests。
- 同观察failure优先，observe直接return，不能同bar被CP重启。
- 后续更晚合法行业CP在inactive分支重启新attempt，level重新0；新episode则由start创建新Sector（默认level0/activeFalse/attemptNone），但carry failed_bar。
- cancel只是open→cancel_pending；ACK才余量归0。cancel_ack还可再次触发migrate；因此升档时先撤probe单、再等待ACK解除迁池阻塞，不是立刻释放预留。
- 原旧lot保持原episode/attempt/pool并继续占sector/pool资源，新attempt不免费获得整桶空余。

## 4. START之前已确认的行业状态可以继承，账户尚无股票

[joint_v3.py:175–189](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:175)

```python
  self.sector_by_sid={l.security_id:l.sector_id for l in self.bundle.lines};self.accounts={p:Account(p,self.market,self.facts,p=='B',self.sector_by_sid) for p in policies};self.receipts=receipts;self.opportunities=[];self.stage_events=[];self.funding=[];self.balance_audit=[]
  self.industry_rows={};self.industry_cp=industry_receipts if industry_receipts is not None else {r['canonical_series']+'|'+r['confirmed_day']:r for r in T.read(BASE.parent/'cp1-evidence-trace-20261031/RECEIPTS.json') if r['canonical_series'].startswith('URFI')};self.episode_starts={}
  for sector in sorted(set(self.sector_by_sid.values())):
   rows=industry_states[sector] if industry_states is not None else T.read(BASE.parent/'industry-mobile-stage-20261031'/f'{sector}_STATE.json');self.industry_rows[sector]={r['day']:r for r in rows}
   for r in rows:
    if r['E0_valid']:self.episode_starts.setdefault(r['E0_episode'],ordinal(r['day']))
   past=[r for r in rows if r['day']<START];last=past[-1];ep=last['E0_episode']
   if ep is None:ep=next((r['E0_episode'] for r in reversed(past) if r['E0_episode']),None)
   for a in self.accounts.values():
    b=a.budget
    if ep is None:continue
    b.start(sector,ep,self.episode_starts[ep]);s=b.sectors[sector];s.failed_bar=max((ordinal(r['day']) for r in past if r['action']=='end_attempt'),default=-1)
    if last['attempt_id'] is not None:
     ar=[r for r in past if r['attempt_id']==last['attempt_id']];first=next(r for r in ar if r['action']=='probe');rc=[r for r in ar if r['receipt'] and r['new_receipt']];s.active=True;s.started=ordinal(first['day']);s.attempt=f"{ep}:{first['receipt_id']}";s.level=last['stage']-1 if b.expand else 0;s.status=['probe','confirmed','expanded'][s.level];s.last_bar=s.last_end=s.last_evidence_time=ordinal(rc[-1]['day'])
    b.consumed.update(r['receipt_id'] for r in past if r['receipt_id']);assert not b.lots and not b.orders
```

J从窗口前行业历史继承episode/attempt/level和已消费receipt；B.expand=True时level=last.stage−1，并断言初始b.lots/b.orders为空。故行业可能在本账户第一笔个股买入之前已confirmed/expanded。不能把这解释为“本账户先试仓成功后行业成熟”。

## 5. CLOSE如何把原行业事实喂给预算状态

[joint_v3.py:195–212](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:195)

```python
 def industry(self,a,at):
  day=gidday(at);bar=ordinal(day);b=a.budget
  for sector,rows in self.industry_rows.items():
   r=rows[day];ep=r['E0_episode'];current=b.sectors.get(sector)
   if r['E0_valid'] and (not current or current.episode!=ep):b.start(sector,ep,self.episode_starts[ep])
   if sector not in b.sectors:continue
   if not r['E0_valid'] or r['action']=='end_attempt':
    b.observe(sector,bar,failure=True);result='invalidated'
   elif r['receipt']:
    cp=self.industry_cp[sector+'|'+day];tok=V.Evidence(cp['receipt_id'],sector,'industry_cp1','21',ordinal(cp['formation_start_exclusive']),bar,bar,b.sectors[sector].episode)
    result=b.observe(sector,bar,token=tok)
   else:result='unchanged'
   a.pools_from_model()
   for sid,real in tuple(a.buys.items()):
    bid=a.order_bridge[real.order_id]
    if b.orders[bid].status=='cancel_pending':a.cancel_buy(sid)
   a.sync(at)
   if result!='unchanged':self.stage_events.append(dict(account=a.label,day=day,sector=sector,market_stage=r['stage_name'],result=result,episode=b.sectors[sector].episode,attempt=b.sectors[sector].attempt,financial_level=b.sectors[sector].level))
```

[joint_v3.py:213–219](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)

```python
 def planning(self,at):
  clock,stocks,sectors=self.facts.packet(at,'I');sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};buyable=self.market.market_buyable(at);day=pd.Timestamp(at.date());event={};continuing={}
  for sid,s in sd.items():
   row=self.facts.row(sid,at);key=(bool(row.i_target),int(row.segment_id)) if row is not None else (False,-1)
   if self.last_epoch.get(sid)!=key:self.epoch[sid]+=1;self.global_watch.pop(sid,None);self.last_epoch[sid]=key
   ep=(key[1],self.epoch[sid]);event[sid]=BP.A.eligibility(s,ss,clock,'S0');continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
   if event[sid].q is True:self.global_watch[sid]=ep
```

[joint_v3.py:241–257](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:241)

```python
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
```

行业r.E0_valid/episode/action/end_attempt与行业canonical CP来自已提供行业事实；J.industry据此start/observe，不读取该股数量或浮盈。它在个股既有退出/保护处理与sync之后、生成新买意图之前运行。预算probe订单被标cancel_pending时，J同步调用真实cancel/ACK再sync。

个股CORE另有flat+core_epoch门，mobile另有fresh stock_CP+continuing_Q门；这与行业level是分开的状态。持仓/未决订单会挡同股新单，但不是行业晋升证据。stock I金融epoch由I_target/segment变化推进，不是sector attempt；CORE actual fill才写core_epoch。

[pilot.py:66–71](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:66)

```python
  if receipt:
   self.layer_seq+=1
   z=dict(id=self.layer_seq,sid=sid,kind=meta['kind'],qty=receipt.shares,initial_qty=receipt.shares,opened=w.at,signal_at=meta['clock'].decision_at,epoch=meta['epoch'],floor=meta['floor'],cash=-receipt.gross_cny-receipt.fees_cny,dividend=ZERO,closed=None,reason=None)
   self.layers.append(z);self.last_buy[sid]=w.execution_price*f
   if z['kind']=='core':self.core_epoch[sid]=meta['epoch']
   self.trades.append(dict(**asdict(receipt),layer=z['id'],kind=z['kind'],signal_at=z['signal_at'],raw_open=w.raw_open,price=w.execution_price,floor=meta['floor'],pvr=meta['score'],reason=meta['reason'],epoch=meta['epoch']))
```

## 6. 实际No60路由与request：何时probe/confirmed可申请

[EFFECTIVE_NO60_ROUTE.txt:1–29](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/funding_state_memory_audit_v1/state_code/EFFECTIVE_NO60_ROUTE.txt:1)

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

[EFFECTIVE_NO60_MODEL.txt:207–260](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/funding_state_memory_audit_v1/state_code/EFFECTIVE_NO60_MODEL.txt:207)

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

route总从probe起；只有mobile且expand、level>0才尝试migrate并加入confirmed候选。比较最大合法q，相同q选probe；不是一看confirmed就一定从confirmed买。CORE新单不能直接选confirmed，但以前CORE lot可以随行业migrate。stock CP需当日确认、同sector/stock/episode/attempt并未consume；其成功消费不会提升industry level。

request先写stock_requests，mobile token在资源校验前consume；正常route先纯量检查再request，但不能把request本身当无副作用preview。confirmed request失败可写confirmed_unfunded，不等于行业结构失效；level/active不因此自动下降。

## 7. 额度分母与状态前后（原公式不改写）

| 实际位置 | 原分母/公式 | 门 |
|---|---|---|
| route.allowed | nav=b.nav−pending_fees−本次buyfee(q) | probe资本10%、probe risk0.5%、sector资本2/10/20%、sector risk1% |
| route sector frac | probe时固定.02；confirmed用(.02,.1,.2)[level] | sc是该行业所有pool旧lot+真pending，不只本attempt |
| route cash | cap+fee≤min(a.available−.1*a.current_nav,b.cash−reserve) | a.current_nav是前CLOSE保存值，available/b.cash在OPEN真实sync后 |
| route stock | held_qty×known_OPEN+新cap≤.1*a.current_nav | 原全股，不每层各领10% |
| request | budget_nav=self.nav−全部pending_fee−qty*fee_per_share | 复核同probe/sector门，无confirmed60/无account3% |
| migrate | 无confirmed60资金分母门 | level/active及同attempt probe pending阻塞仍保留 |

J.nav含receivable_equity；资金分母NAV不是全部spendable cash。旧lot、open/cancel_pending均累计占resources；risk是mark到floor正部，非已损累计，也不是可执行最大损失。

[model.py:79–117](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:79)

```python
    @property
    def nav(self):
        return self.cash + sum(x.qty*self.prices[x.stock] for x in self.lots)

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

[joint_v3.py:15–19](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:15)

```python
class Budget(V.Contract):
 def __init__(self,expand):self.expand=expand;self.receivable_equity=0.;super().__init__(nav=1e6,cash=1e6,shared_loss_budget=20000,exhausted_policy='record_only')
 @property
 def nav(self):return super().nav+self.receivable_equity
 def migrate(self,sector):return super().migrate(sector) if self.expand else False
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

[joint_v3.py:221–222](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:221)

```python
  for a in self.accounts.values():
   C.activate(a);a.expire_day_buys(at);a.current_nav=a.balance(at,self.market.marks(at,a.positions))['nav'];M.E.risk_policy.step(a,at,'ACT20_BREAK');a.pending=[]
```

## 8. 与同股持仓/盈利的直接与间接关系

**直接不读：** V.industry/start/observe/valid没有“已有CORE”“该股盈利”“原仓保本”“同股收益≥阈值”分支；行业level由原市场receipt/failure/epoch驱动。stock卖出也不是sector failure输入。

**间接会影响：** 真实持仓/待单影响capital、mark到floor risk、现金/ACK，从而影响q和迁池是否被pending阻塞；价格/收益及结算影响NAV、百分比额度。行业升档可以授较大sector容量，但不会自动造现金。

**已损只记录：** J.Budget为shared_loss_budget=20000且record_only；loss按sector/原episode累计gross负损益+费，stock real buy/sell回调记入。loss不使行业降级/新attempt重置，也不在现行record_only下触发耗尽禁止新单；新episode不会删除旧loss字典。

[model.py:83–93](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py:83)

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
```

[joint_v3.py:104–111](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:104)

```python
 def fill_buy(self,sid,w):
  real=self.buys.get(sid);i=self.order_meta[real.order_id] if real else None;bid=self.order_bridge.get(real.order_id) if real else None;self._buy_filling=sid;self._deferred_buy_cancels=[]
  try:r=super().fill_buy(sid,w)
  finally:self._buy_filling=None
  if r:
   bo=self.budget.orders[bid];price=float(r.gross_cny/D(r.shares));floor=float(i['floor']/self.facts.factor(sid,w.at));assert price<=bo.limit+1e-8
   x=self.layers[-1];self.jmeta[x['id']]=dict(sector=bo.sector,episode=bo.episode,pool=bo.pool,role=bo.role,attempt=bo.attempt,unit_cost=price,last_core_line=str(i['floor']),stock_structure=getattr(self.facts,'structure_lookup',{}).get(sid,{}).get(i['clock'].decision_at.date()),budget_order=bid)
   self.budget.loss(bo.sector,bo.episode,float(r.fees_cny))
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

封口：这里仅陈述现No60代码。模板/静态派生/真实回调已分开，未推演新机制或运行任何策略。源SHA、派生文本SHA与摘录版本见SOURCE_SHA256.json。
