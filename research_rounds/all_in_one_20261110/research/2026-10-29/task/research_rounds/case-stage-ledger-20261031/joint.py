"""Research-only v2 budget mirror over the existing authoritative real ledger."""
import wire as W
from pathlib import Path
import sys,math,time,copy,json,gzip,pickle,collections
from dataclasses import replace,asdict
import numpy as np,pandas as pd
O=W.O;M=W.M;C=W.C;BP=W.BP;LR=W.LR;D=W.D;Z=D(0);END=W.END;START=W.START
V=W.load('case_stage_reviewed_budget_v2',O/'budget_v2/model.py');T=W.load('case_stage_original_CP1_trace',O.parent/'cp1-evidence-trace-20261031/trace.py')
def ordinal(day):return pd.Timestamp(day).date().toordinal()
def gidday(at):return str(at.date())
def save(n,x):W.save(n,x)
class Budget(V.Contract):
 def __init__(self,expand):self.expand=expand;self.nav_adjustment=0.;super().__init__(nav=1e6,cash=1e6,shared_loss_budget=20000,exhausted_policy='record_only')
 @property
 def nav(self):return super().nav+self.nav_adjustment
 def migrate(self,sector):return super().migrate(sector) if self.expand else False
 def industry(self,token,bar,**terms):
  if self.expand or not self.sectors[token.sector].active:return super().industry(token,bar,**terms)
  # Probe-only control inherits the same market attempt, but never raises its
  # financial level, migrates a pool, signs a grant, or cancels for promotion.
  s=self.sectors[token.sector]
  if not self.valid(token,'industry_cp1',bar) or token.event_id in self.consumed:return 'rejected'
  if token.confirmed_time<=s.failed_bar or token.end<=s.failed_bar or bar<=s.last_bar or token.end<=s.last_end or token.confirmed_time<=s.last_evidence_time:return 'not_new_progress'
  if token.confirmed_time!=bar:return 'late_evidence_audit_only'
  self.consumed.add(token.event_id);s.last_bar=bar;s.last_end=token.end;s.last_evidence_time=token.confirmed_time;self.audit.append(('probe_only_new_industry_evidence',token.event_id));return 'probe'
class Account(C.Account):
 def __init__(self,name,market,facts,expand,sector_by_sid):
  super().__init__(name,market,facts,False,1,0);self.budget=Budget(expand);self.sector_by_sid=sector_by_sid;self.jmeta={};self.order_bridge={};self.journal=[];self.sync_rows=[];self.budget_at=None
 def pools_from_model(self):
  for x in self.budget.lots:
   k=int(x.batch)
   if k in self.jmeta:self.jmeta[k]['pool']=x.pool
 def sync(self,at):
  self.pools_from_model();b=self.budget;marks=self.market.marks(at,self.positions);bal=self.balance(at,marks);lots=[]
  for x in self.layers:
   if not x['qty']:continue
   # Only the last decision-known core line is available at the next open.
   # facts.row(at) contains that date's close and must not update this at open.
   meta=self.jmeta[x['id']];sid=x['sid'];factor=self.facts.factor(sid,at);floor=D(str(meta['last_core_line'])) if x['kind']=='core' else x['floor']
   if floor is None:raise ValueError('unknown actual protection floor '+sid)
   b.prices[sid]=float(marks[sid].cny_price(at));lots.append(V.Lot(str(x['id']),sid,meta['sector'],meta['episode'],meta['pool'],x['qty'],meta['unit_cost'],float(floor/factor),meta['role'],meta['grant_id'],meta['attempt']))
  b.lots=lots
  for sid,o in self.buys.items():
   bid=self.order_bridge[o.order_id];bo=b.orders[bid];assert bo.qty==o.remaining_shares,(sid,'budget/actual pending quantity');bo.limit=float(o.remaining_budget_cny/D(o.remaining_shares));bo.fee_per_share=float(o.fee_reserved_cny/D(o.remaining_shares));bo.floor=float(self.order_meta[o.order_id]['floor']/self.facts.factor(sid,at))
  # Contract.cash contains spendable cash plus its own outstanding reserve.
  # Actual receivables/rights and any representation difference enter NAV only.
  reserve=b.resources()[2];b.cash=float(self.available)+reserve;b.nav_adjustment=float(bal['nav'])-(b.cash+sum(x.qty*b.prices[x.stock] for x in b.lots));self.budget_at=at
  assert abs(b.nav-float(bal['nav']))<1e-6 and abs(b.cash-reserve-float(self.available))<1e-6
  for sid,p in self.positions.items():assert sum(x.qty for x in b.lots if x.stock==sid)==p.shares
  for g in b.grants.values():
   u=b.grant_usage(g.gid)
   for dim,lim in [('capital',g.capital_limit),('risk',g.risk_limit)]:
    vals=[u[k+'_'+dim] for k in ['filled','pending','remaining','expired']];assert min(vals)>-1e-5,(g.gid,dim,vals);assert abs(sum(vals)-lim)<1e-5
  return bal
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
   x=self.layers[-1];self.jmeta[x['id']]=dict(sector=bo.sector,episode=bo.episode,pool=bo.pool,role=bo.role,grant_id=bo.grant_id,attempt=bo.attempt,unit_cost=price,last_core_line=str(i['floor']),stock_structure=getattr(self.facts,'structure_lookup',{}).get(sid,{}).get(i['clock'].decision_at.date()),budget_order=bid)
   self.budget.loss(bo.sector,bo.episode,float(r.fees_cny))
   if bo.grant_id:
    g=self.budget.grants[bo.grant_id];g.filled_capital+=r.shares*price;g.filled_risk+=r.shares*max(0.,price-floor);g.expired_capital+=r.shares*max(0.,bo.limit-price);g.expired_risk+=r.shares*(max(0.,bo.limit-bo.floor)-max(0.,price-floor))
   bo.qty-=r.shares
   if not bo.qty:bo.status='filled'
   self.journal.append(dict(kind='real_buy_fill',at=w.at,sid=sid,layer=x['id'],budget_order=bid,shares=r.shares,price=r.gross_cny/D(r.shares),fees=r.fees_cny,pool=bo.pool,role=bo.role,attempt=bo.attempt,grant=bo.grant_id,signal_at=i['clock'].decision_at,CP1_id=i.get('CP1_id')))
  if r:self.sync(w.at)  # Migration ack must already see the actual filled lot.
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
 def split(self,**kw):
  super().split(**kw)
  for x in self.live(kw['sid']):self.jmeta[x['id']]['unit_cost']/=float(kw['ratio'])
  self.journal.append(dict(kind='actual_split',**kw))
def prepare_receipts(shared):
 start=time.monotonic();_,m,f=shared;out={};tr=[]
 for sid in m.lines:
  q=pd.read_parquet(W.CACHE/'CP1-input'/f'{sid}.parquet').loc[:END];z=pd.read_parquet(W.CACHE/'CP1'/f'{sid}.parquet').loc[:END];rec=T.read(T.OLD/'manifest.json') if False else None
  oldrec=W.M.read(T.OLD/'manifest.json')['series'] if False else None
  # Full native event sources already identified and hashed by the cache manifest.
  rr=W.M.read(W.CACHE/'receipts'/f'{sid}.json');path=next(p for p in rr['source_sha256'] if p.endswith('/events.parquet'));ev=pd.read_parquet(path).reindex(q.index);ep=f.f[sid].e0_target.reindex(q.index).astype(bool);r,_,_=T.trace(sid,q,z,ev,ep);assert not any(x['trace_unknown'] for x in r);out[sid]={x['confirmed_day']:x for x in r};tr.extend(r)
 save('STOCK_CANONICAL_RECEIPTS',tr);save('RECEIPT_PREPARATION',dict(stocks=77,receipts=len(tr),seconds=time.monotonic()-start,source='original trace, unmodified CP1 cache',no_new_indicators=True));return out
class Runner(W.Harness):
 def __init__(self,shared,receipts,policies=('A','B')):
  super().__init__(shared,False);self.sector_by_sid={l.security_id:l.sector_id for l in self.bundle.lines};self.accounts={p:Account(p,self.market,self.facts,p=='B',self.sector_by_sid) for p in policies};self.receipts=receipts;self.opportunities=[];self.stage_events=[];self.funding=[];self.balance_audit=[]
  self.industry_rows={};self.industry_cp={r['canonical_series']+'|'+r['confirmed_day']:r for r in T.read(O.parent/'cp1-evidence-trace-20261031/RECEIPTS.json') if r['canonical_series'].startswith('URFI')};self.episode_starts={}
  for sector in sorted(set(self.sector_by_sid.values())):
   rows=T.read(O.parent/'industry-mobile-stage-20261031'/f'{sector}_STATE.json');self.industry_rows[sector]={r['day']:r for r in rows}
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
    b.consumed.update(r['receipt_id'] for r in past if r['receipt_id']);assert not b.grants and not b.lots and not b.orders
  for sid,df in self.facts.f.items():
   if sid not in self.market.lines:continue
   on=df.e0_target.fillna(False).astype(bool);opening=on&~on.groupby(df.segment_id).shift(fill_value=False);z=pd.Series(None,index=df.index,dtype=object)
   for d in df.index[opening]:z.loc[d]=f'{sid}|{int(df.loc[d,"segment_id"])}|{d.date()}'
   self.facts.structure_lookup[sid]={d.date():v for d,v in z.groupby(df.segment_id).ffill().where(on,None).items()}
 def industry(self,a,at):
  day=gidday(at);bar=ordinal(day);b=a.budget
  for sector,rows in self.industry_rows.items():
   r=rows[day];ep=r['E0_episode'];current=b.sectors.get(sector)
   if r['E0_valid'] and (not current or current.episode!=ep):b.start(sector,ep,self.episode_starts[ep])
   if sector not in b.sectors:continue
   if not r['E0_valid'] or r['action']=='end_attempt':
    b.observe(sector,bar,failure=True);result='invalidated'
   elif r['receipt']:
    cp=self.industry_cp[sector+'|'+day];tok=V.Evidence(cp['receipt_id'],sector,'industry_cp1','21',ordinal(cp['formation_start_exclusive']),bar,bar,b.sectors[sector].episode);terms={}
    if b.expand and b.sectors[sector].active:terms=dict(grant_id=tok.event_id,grant_capital=b.nav,grant_risk=.03*b.nav,decision_batch=day,decision_bar=bar)
    result=b.observe(sector,bar,token=tok,**terms)
   else:result='unchanged'
   a.pools_from_model()
   for sid,real in tuple(a.buys.items()):
    bid=a.order_bridge[real.order_id]
    if b.orders[bid].status=='cancel_pending':a.cancel_buy(sid)
   a.sync(at)
   if result!='unchanged':self.stage_events.append(dict(account=a.label,day=day,sector=sector,market_stage=r['stage_name'],result=result,episode=b.sectors[sector].episode,attempt=b.sectors[sector].attempt,financial_level=b.sectors[sector].level,grants=[asdict(g) for g in b.grants.values() if g.sector==sector and g.active]))
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
 def daily_bridge(self,a,at,bal):
  b=a.budget;trade_cash=sum(((D(t['gross_cny'])-D(t['fees_cny'])) if t['side']=='sell' else (-D(t['gross_cny'])-D(t['fees_cny'])) for t in a.trades),Z);div=Z
  for r in a.audit_log:
   if r['kind']=='dividend_accrual':
    x=r['receivable'];div+=D(x['net_local']) if isinstance(x,dict) else x.net_local
  independent=a.initial_cash+trade_cash+div+bal['inventory'];assert abs(independent-bal['nav'])<D('.00000001'),('independent NAV',a.label,at,independent,bal['nav'])
  actual_cap=float(bal['inventory']+sum((o.remaining_budget_cny for o in a.buys.values()),Z));capital,risk,reserve=b.resources();assert abs(capital-actual_cap)<1e-6 and abs(reserve-float(bal['order_reserved']))<1e-6
  qdiff=max([abs(sum(x.qty for x in b.lots if x.stock==sid)-a.quantity(sid)) for sid in set(a.positions)|{x.stock for x in b.lots}]+[0]);assert qdiff==0
  pool_diffs={};marks=self.market.marks(at,a.positions)
  for pool in ['probe','confirmed']:
   direct=sum((D(x['qty'])*marks[x['sid']].cny_price(at) for x in a.layers if x['qty'] and a.jmeta[x['id']]['pool']==pool),Z)+sum((o.remaining_budget_cny for o in a.buys.values() if a.order_meta[o.order_id]['pool']==pool),Z);pool_diffs[pool]=b.resources(pool)[0]-float(direct);assert abs(pool_diffs[pool])<1e-6
  self.balance_audit.append(dict(account=a.label,at=at,NAV_exact=str(bal['nav']),independent_NAV=str(independent),independent_NAV_difference=str(independent-bal['nav']),budget_NAV=b.nav,budget_NAV_difference=b.nav-float(bal['nav']),available_exact=str(a.available),budget_spendable=b.cash-reserve,spendable_difference=b.cash-reserve-float(a.available),reserved_difference=reserve-float(bal['order_reserved']),capital_occupancy_difference=capital-actual_cap,pool_occupancy_difference=pool_diffs,maximum_stock_quantity_difference=qdiff,core_pending_exit_last_known_reference=sum(x['qty']>0 and a.jmeta[x['id']].get('pending_I_exit_reference',False) for x in a.layers)))
 def route(self,a,i,x,at):
  b=a.budget;sid=i['sid'];sector=self.sector_by_sid[sid];s=b.sectors.get(sector);bar=ordinal(i['clock'].decision_at.date());role=i['role'];p=float(x['price']);floor=float(x['floor']);rule=x['rule'];maxq=x['maxq'];rid=i.get('CP1_id');token=None
  if not s or not s.active:return None,'industry_invalidated'
  if role=='mobile':
   cp=i['CP1_trace'];token=V.Evidence(rid,sector,'stock_cp1','21',ordinal(cp['formation_start_exclusive']),bar,bar,s.episode,sid,s.attempt)
   if not b.valid(token,'stock_cp1',bar) or rid in b.consumed:return None,'no_fresh_stock_CP1'
  latest=next((g for g in reversed(list(b.grants.values())) if g.sector==sector and g.active and g.attempt==s.attempt),None)
  routes=[('probe',None)]
  if role=='mobile' and b.expand and latest and s.level>0:
   if b.migrate(sector):a.pools_from_model();routes.append(('confirmed',latest.gid))
  results=[];reasons={}
  for pool,g in routes:
   pc,pr,_=b.resources(pool);sc,sr,_=b.resources(sector=sector);_,ar,reserve=b.resources();pending_fees=sum(o.qty*o.fee_per_share for o in b.orders.values() if o.status in ['open','cancel_pending']);u=b.grant_usage(g) if g else None;frac=.02 if pool=='probe' else (.02,.1,.2)[s.level]
   def allowed(q,detail=False):
    fee=float(LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value));nav=b.nav-pending_fees-fee;cap=q*p;risk=q*max(0.,p-floor);fails=[]
    if cap+fee>min(float(a.available-a.current_nav*D('.1')),b.cash-reserve)+1e-9:fails.append('cash_or_original_reserve')
    if pc+cap>(.10 if pool=='probe' else .60)*nav+1e-9:fails.append('pool_capital')
    if pool=='probe' and pr+risk>.005*nav+1e-9:fails.append('probe_risk')
    if sc+cap>frac*nav+1e-9:fails.append('sector_capital')
    if sr+risk>.01*nav+1e-9:fails.append('sector_risk')
    if ar+risk>.03*nav+1e-9:fails.append('account_risk')
    known_open=x.get('known_open',x['price']/(D(1)+LR.SLIP));held_at_open=float(a.quantity(sid))*float(known_open)
    if held_at_open+cap>.10*float(a.current_nav)+1e-9:fails.append('stock_capital')
    if g and (cap>u['remaining_capital']+1e-9 or risk>u['remaining_risk']+1e-9):fails.append('grant_exhausted')
    return fails if detail else not fails
   q=LR.maximum_quantity(rule,maxq,allowed);results.append((q,pool,g));reasons[pool]=allowed(rule.buy_minimum,True)
  # Maximum legal quantity, probe wins a tie. No split order or speculative consume.
  q,pool,g=max(results,key=lambda z:(z[0],z[1]=='probe'))
  if not q:return None,','.join(sorted(set(sum(reasons.values(),[])))) or 'minimum_unit_not_funded'
  bid=f"{a.label}|{i['clock'].decision_at.isoformat()}|{sid}|{role}";fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value);result=b.request(bid,sid,sector,q,p,floor,token,bar,float(fee/D(q)),probe_request=pool=='probe',role=role,grant_id=g,decision_batch=gidday(i['clock'].decision_at),order_expiry_bar=ordinal(at.date()),core_epoch_locked=role=='core' and a.core_epoch.get(sid)==i['epoch']);assert result=='reserved',(bid,result,reasons)
  i.update(budget_order=bid,pool=pool);return(q,pool,g),None
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
   q,pool,g=route;a.reserve_quantity(i,q,x['price'],x['schedule'],at);a.sync(at);done.add(sid);funded.append((sid,i,x,q));self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='reserved',pool=pool,grant=g,shares=q,price=x['price'],CP1_id=i.get('CP1_id')))
  # Execution proxies are consulted only after all H1-ranked funding decisions.
  for sid,i,x,q in funded:
   win=self.market.window(sid,at,'buy',1)
   if win:assert win.execution_price==x['price'];a.fill_buy(sid,win)
   else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='no_execution_window_after_reservation'))
  a.settle_due(at);a.sync(at);a.minimum_available=min(a.minimum_available,a.available);a.check()
 def dump_joint(self,path):
  path=Path(path);path.mkdir(exist_ok=True)
  for name,data in [('daily',self.daily),('opportunities',self.opportunities),('funding',self.funding),('industry',self.stage_events),('balances',self.balance_audit)]:
   with gzip.open(path/(name+'.jsonl.gz'),'wt') as f:
    for r in data:f.write(json.dumps(M.N.encoded(r),ensure_ascii=False,default=C.encoded)+'\n')
  for key,a in self.accounts.items():
   b=a.budget;payload=dict(trades=a.trades,layers=a.layers,metadata=a.jmeta,journal=a.journal,orders=a.buys,exits=a.exits,audit=a.audit_log,decisions=a.decisions,budget=dict(sectors=b.sectors,grants=b.grants,orders=b.orders,losses={str(k):v for k,v in b.losses.items()},consumed=sorted(b.consumed)),ending_cash=a.available,ending_NAV=a.current_nav)
   with gzip.open(path/(key+'.json.gz'),'wt') as f:json.dump(M.N.encoded(payload),f,ensure_ascii=False,default=C.encoded)
def main():
 t=time.monotonic();shared=W.context();receipts=prepare_receipts(shared);r=Runner(shared,receipts,('B',));r.run(end='2025-07-07',begin=START);r.dump_joint(O/'joint-short');save('JOINT_SHORT',dict(completed=True,closes=len(r.daily),trades=len(r.accounts['B'].trades),seconds=time.monotonic()-t,run_seconds=r.run_seconds));print('JOINT_SHORT',len(r.daily),len(r.accounts['B'].trades),r.run_seconds,flush=True)
if __name__=='__main__':main()
