from common import *
from fast_market import FastMarket
from decimal import Decimal as D,ROUND_CEILING
from dataclasses import replace,asdict
from datetime import time,timedelta
from bisect import bisect_right
import collections,time as timer
from run_first10 import first10_specs

PAD=D('1000000000000');CAP=D('1000000');CORE=D('100000');LEVELS=[CORE,D('300000'),D('600000'),CAP]
class Account(ledger.SectorAccount):
 def __init__(self,*args,**kw):
  super().__init__(*args,**kw);self.book={};self.stage={};self.anchor={};self.order_meta={};self.mode='F100';self.last_grade={};self.counts=collections.Counter()
 @property
 def available(self):return self._available
 @available.setter
 def available(self,value):
  self._available=value
  if not hasattr(self,'minimum_available') or value<self.minimum_available:self.minimum_available=value;self.minimum_at=getattr(self,'as_of',None)
 def fill_buy(self,sid,window):
  order=self.buys.get(sid);meta=self.order_meta.get(order.order_id) if order else None;r=super().fill_buy(sid,window)
  if r:
   self.book[sid]=self.book.get(sid,D(0))+r.gross_cny;assert self.book[sid]<=CAP+D('1e-8')
   self.anchor[sid]=meta['anchor'];self.stage[sid]=meta['stage'];self.counts['buy_fills']+=1;self.counts[meta['kind']+'_fills']+=1
  return r
 def fill_exit(self,sid,window):
  old=self.quantity(sid);r=super().fill_exit(sid,window)
  if r:
   self.book[sid]=self.book[sid]*D(old-r.shares)/D(old);self.counts['sell_fills']+=1
   if not self.quantity(sid):
    for x in [self.book,self.stage,self.anchor,self.last_grade]:x.pop(sid,None)
  return r
 def expire_day_buys(self,at):
  extra={s for s,o in self.buys.items() if o.purpose=='annual_rebalance' and not o.filled_shares and self.delay_events and not o.delay_remaining and at.date()>=o.earliest_at.date()}
  r=super().expire_day_buys(at);self.daily_delay_credit.update(extra);return r
 def buy(self,sid,quote,clock,budget,anchor,stage,kind):
  budget=min(budget,CAP-self.book.get(sid,D(0)));budget=(budget*100).to_integral_value(rounding='ROUND_FLOOR')/100
  if budget<=0:return
  assert self.available>CAP*2000
  purpose='initial' if kind=='initial' else 'annual_rebalance'
  ok,reason=self.reserve_budget(quote=quote,clock=clock,gross_budget_cny=budget,purpose=purpose,candidate_id=f'{kind}:{sid}:{clock.decision_at.isoformat()}')
  self.counts[kind+'_orders']+=1
  if ok:
   self.order_meta[reason]=dict(anchor=float(anchor),stage=stage,kind=kind)
   self.audit_log.append(dict(kind='sizing_buy_intent',at=clock.decision_at,sid=sid,order_id=reason,amount=budget,held_cost=self.book.get(sid,D(0)),signal_price=float(anchor),stage=stage,sizing_kind=kind,mode=self.mode))
  else:
   self.counts[reason]+=1;self.audit_log.append(dict(kind='sizing_rejection',at=clock.decision_at,sid=sid,reason=reason,sizing_kind=kind,budget=budget))
 def full_exit(self,sid,quote,clock):
  old=self.exits.get(sid)
  if old and old.purpose=='annual_rebalance':
   old.remaining_target=None;old.purpose='structure_exit';old.earliest_at=max(old.earliest_at,clock.earliest_execution_at)
   self.audit_log.append(dict(kind='upgrade_full_exit',at=clock.decision_at,sid=sid,event_id=old.event_id))
  self.request_exit(quote,clock)
 def reduce(self,sid,quote,clock,target):
  cost=self.book.get(sid,D(0));qty=self.quantity(sid)
  if sid in self.exits or not qty or cost<=target:return
  keep=max(1,int((D(qty)*target/cost).to_integral_value(rounding=ROUND_CEILING)));sale=quote.quantity.sell_floor(qty-keep,qty)
  if sale<=0:return
  self.request_reduction(quote,clock,sale);self.counts['reduction_orders']+=1
  self.audit_log.append(dict(kind='sizing_reduction',at=clock.decision_at,sid=sid,shares=sale,target_cost=target,held_cost=cost,mode=self.mode))

class Sink:
 def __init__(self,p):
  p.mkdir(parents=True,exist_ok=False);self.p=p;self.fs={n:gzip.open(p/f'{n}.jsonl.gz','wt',compresslevel=1) for n in ['daily','fills','audit']};self.n=0
 def daily(self,aid,a,at,market):
  marks=market.marks(at,a.positions);bal=a.balance(at,marks,market.currency_fx(at));row=dict(account=aid,at=at,**bal,pnl=bal['nav']-PAD,peak_funding=PAD-a.minimum_available,peak_funding_at=a.minimum_at,positions={s:p.shares for s,p in a.positions.items()},pending_buys=tuple(a.buys),pending_sells=tuple(a.exits),holding_count=len(a.positions),holding_cost=sum(a.book.values(),D(0)),max_single_cost=max(a.book.values(),default=D(0)),counts=dict(a.counts))
  for s,o in a.buys.items():assert a.book.get(s,D(0))+o.remaining_budget_cny<=CAP+D('1e-8')
  for name,items in [('fills',a.fills),('audit',a.audit_log)]:
   for r in items:
    if not isinstance(r,dict):r=asdict(r)
    self.fs[name].write(json.dumps(native.encoded(dict(account=aid,**r)),ensure_ascii=False)+'\n')
   items.clear()
  self.fs['daily'].write(json.dumps(native.encoded(row),ensure_ascii=False)+'\n');self.n+=1
 def close(self):
  for f in self.fs.values():f.close()

class Runner(native.HistoryRunner):
 def run_fast(self,facts):
  dates=[str(x) for x in facts['dates']];symbols=[str(x) for x in facts['symbols']];di={d:i for i,d in enumerate(dates)};sj={s:j for j,s in enumerate(symbols)}
  cutoffs={x for x in self.market.cutoffs if self.start<=x<=self.end};opens={x for xs in self.market.sessions.values() for x in xs if self.start<=x<=self.end};actions={datetime.combine(datetime.fromisoformat(d).date(),time.min,native.TZ) for d in self.actions_by_date};events=sorted(cutoffs|opens|{x for x in actions if self.start<=x<=self.end});all_opens=sorted({x for xs in self.market.sessions.values() for x in xs})
  for at in events:
   for a in self.accounts.values():a.settle_due(at)
   self._actions(at)
   for a in self.accounts.values():self._payments(a,at)
   if at in opens:
    for aid,a in self.accounts.items():
     for sid in sorted(a.exits):
      w=self.market.window(sid,at,'sell',a.cost_multiplier)
      if w:a.fill_exit(sid,w)
     a.settle_due(at)
     for sid in sorted(a.buys):
      w=self.market.window(sid,at,'buy',a.cost_multiplier)
      if w:a.fill_buy(sid,w)
     a.settle_due(at)
   if at not in cutoffs:continue
   i=di[at.date().isoformat()];clock=admission.Clock(at,all_opens[bisect_right(all_opens,at)],at.date());qualified={symbols[j] for j in np.flatnonzero(facts['eligible'][i])}
   for aid,a in self.accounts.items():
    a.expire_day_buys(at)
    for sid in tuple(a.positions):
     j=sj[sid];u=int(facts['up'][i,j])
     if u==0:
      quote=self.market.quote(sid,at)
      if quote:a.full_exit(sid,quote,clock)
      continue
     if a.mode in ['C','D'] and sid not in a.exits:
      grade=int(facts['grade'][i,j]);old=a.last_grade.get(sid,-99)
      if grade!=-99:
       target=None
       if a.mode=='C' and old!=-99 and grade<old:target={4:CAP,3:LEVELS[2],2:LEVELS[1]}.get(grade,CORE)
       if a.mode=='D' and (grade<=-2 or bool(facts['acute'][i,j])):
        target=CORE
        if a.stage.get(sid,0):a.audit_log.append(dict(kind='sizing_reset',at=at,sid=sid,mode=a.mode))
        a.stage[sid]=0
       if target is not None:
        quote=self.market.quote(sid,at)
        if quote:a.reduce(sid,quote,clock,target)
      a.last_grade[sid]=grade
    for sid in sorted(qualified):
     if sid in a.exits or sid in a.buys:continue
     j=sj[sid];held=a.quantity(sid);quote=None
     if not held:
      quote=self.market.quote(sid,at)
      if quote:
       budget=CAP if a.mode=='F100' else D('300000') if a.mode=='F30' else CORE
       a.buy(sid,quote,clock,budget,facts['signal_price'][i,j],0,'initial')
      continue
     if a.mode.startswith('F'):continue
     grade=int(facts['grade'][i,j]);signal=float(facts['signal_price'][i,j])
     if grade<2 or not facts['fresh'][i,j] or signal<=a.anchor.get(sid,float('inf')):continue
     quote=self.market.quote(sid,at)
     if quote is None or quote.raw_price<=a.book[sid]/D(held):continue
     if a.mode in ['A','D']:
      stage=a.stage.get(sid,0)+1
      if stage>=len(LEVELS):continue
      target=LEVELS[stage]
     else:stage={2:1,3:2,4:3}.get(grade,3);target=LEVELS[stage]
     if target>a.book[sid]:a.buy(sid,quote,clock,target-a.book[sid],signal,stage,'add')
    a.daily_delay_credit.clear();self.sink.daily(aid,a,at,self.market)
   if (i+1)%20==0:print(json.dumps(dict(stage='replaying',date=at.date().isoformat(),paths=len(self.accounts),daily_rows=self.sink.n)),flush=True)
  return dict(status='complete',accounts=list(self.accounts),days=len(cutoffs),daily_rows=self.sink.n,technical=self.synthetic)

def main(mode):
 facts=dict(np.load(HERE/'prepared/facts.npz'));cutoff='2015-03-31' if mode.startswith('short') else '2018-12-28' if mode=='prefix' else None
 if cutoff:
  mask=facts['dates']<=cutoff;facts={k:(v[mask] if k not in ['symbols'] else v) for k,v in facts.items()}
 b=load_bundle(OLD/'inputs-v2/input-manifest.json');m=FastMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'))
 if cutoff:
  for sid,f in m.raw.items():m.raw[sid]=f.loc[:cutoff].copy()
  m.actions={s:[e for e in es if e['effective_date']<=cutoff] for s,es in m.actions.items()}
  # Rebuild raw array provider after the physical truncation.
  for sid,a in m.arr.items():
   n=len(m.raw[sid]);m.arr[sid]={k:(v[v<n] if k in ['good','positive'] else v[:n] if isinstance(v,np.ndarray) else v) for k,v in a.items()}
 modes=['F100'] if mode.startswith('controls') else ['F10','F30','A','B','C','D'] if mode=='economic' else ['F100','F10','F30','A','B','C','D'];stresses=['base'] if mode=='prefix' else ['base','cost2','delay1'];ss=tuple(replace(s,account_id=f'{p}__{s.account_id}',initial_capital_cny=PAD) for p in modes for s in first10_specs() if s.variant=='S0' and s.stress.name in stresses)
 native.first10_specs=lambda:ss;native.SectorAccount=Account
 path=HERE/('accounts-v1' if mode=='economic' else 'technical/'+mode);sink=Sink(path);r=Runner(b,m,start=native.iso('2015-01-01T00:00:00+08:00'),end=native.iso((cutoff or '2026-10-22')+'T15:10:00+08:00'),sink=sink,synthetic=mode!='economic')
 for aid,a in r.accounts.items():a.mode=aid.split('__')[0]
 if mode=='economic':
  assert read(HERE/'technical/controls-v2-identity.json')['passed'];assert read(HERE/'technical/short-validation.json')['passed'];assert read(HERE/'technical/synthetic.json')['passed']
  paths=list((HERE/'code').glob('*.py'))+[HERE/'PROTOCOL.md',HERE/'prepared/manifest.json',HERE/'prepared/facts.npz',HERE/'technical/controls-v2-identity.json',HERE/'technical/short-validation.json',HERE/'technical/synthetic.json',OLD/'code/sector_account.py',OLD/'inputs-v2/input-manifest.json',OLD/'inputs-v2/economic-protocol.json']
  write(HERE/'account-freeze-v1.json',dict(recorded_at=now(),before_results=True,paths=21,new_economic_paths=18,controls=3,sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}))
 t=timer.time()
 try:
  summary=r.run_fast(facts);write(path/'summary.json',summary)
  for aid,a in r.accounts.items():write(path/f'{aid}-final.json',dict(available=a.available,peak_funding=PAD-a.minimum_available,peak_funding_at=a.minimum_at,positions=a.positions,book=a.book,buys=a.buys,exits=a.exits,dividends=a.dividends,settlements=a.settlements,fees_cny=a.fees_cny,counts=dict(a.counts)))
  write(path/'provenance.json',dict(recorded_at=now(),seconds=timer.time()-t,financial_ledger_unchanged=True,fast_market_fact_provider=True,original_window_checks=m.window_identity_checks,original_mark_checks=m.mark_identity_checks,mode=mode))
 except BaseException as e:write(path/'failure.json',dict(error=repr(e),at=now()));raise
 finally:sink.close()
 print(json.dumps(dict(done=True,mode=mode,seconds=timer.time()-t)),flush=True)
if __name__=='__main__':main(sys.argv[1])
