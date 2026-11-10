"""One unchanged B instrumentation replay. Counterfactuals never submit orders."""
from pathlib import Path
from bisect import bisect_right
from collections import Counter
import collections,gzip,inspect,json,math,pickle,time
import pandas as pd
import launch_v3 as L
J=L.J;D=J.D;Z=D(0);OUT=J.O/'risk-occupancy-diagnostic'
SPECS={'URFI881267':('2025-07-01','2025-09-30','2025-09-30'),
 'URFI881276':('2025-10-01','2025-12-31','2025-12-31'),
 'URFI881107':('2026-01-01','2026-03-31','2026-03-04')}
def in_case(sector,day):return sector in SPECS and SPECS[sector][0]<=day<=SPECS[sector][1]
def dump_gz(path,rows):
 with gzip.open(path,'wt') as f:
  for x in rows:f.write(json.dumps(L.W.canon(x),ensure_ascii=False)+'\n')
def persist_available(r):
 OUT.mkdir(parents=True,exist_ok=True)
 dump_gz(OUT/'AVAILABLE_ROUTED_MOBILE.jsonl.gz',r.diag)
 dump_gz(OUT/'AVAILABLE_RISK_SNAPSHOTS.jsonl.gz',r.snapshots)
 dump_gz(OUT/'AVAILABLE_ELIGIBLE_CP1.jsonl.gz',r.eligible)

def can_migrate(b,sector):
 s=b.sectors[sector]
 if not b.expand or not s.active or not s.level:return False
 if any(o.sector==sector and o.attempt==s.attempt and o.pool=='probe' and o.qty>0 and o.status in ('open','cancel_pending') for o in b.orders.values()):return False
 moved=sum(x.qty*b.prices[x.stock] for x in b.lots if x.sector==sector and x.attempt==s.attempt and x.pool=='probe')
 fees=sum(o.qty*o.fee_per_share for o in b.orders.values() if o.status in ('open','cancel_pending'))
 return b.resources('confirmed')[0]+moved<=.60*(b.nav-fees)+1e-9

# Derive from the exact frozen function. Remove only account_risk, make its
# migration check read-only, and stop before request/receipt consumption.
original=inspect.getsource(J.Runner.route)
pure=original.replace('def route(', 'def no_account_check(',1)
pure=pure.replace("if b.migrate(sector):a.pools_from_model();routes.append('confirmed')","if can_migrate(b,sector):routes.append('confirmed')")
needle="    if ar+risk>.03*nav+1e-9:fails.append('account_risk')\n"
assert pure.count(needle)==1;pure=pure.replace(needle,'')
cut=pure.index('  bid=f');pure=pure[:cut]+"  return(q,pool),None\n"
env=dict(J.__dict__,can_migrate=can_migrate);exec(pure.strip(),env);no_account_check=env['no_account_check']

class DiagnosticRunner(L.PreparedRunner):
 def __init__(self,*args,gold_daily,gold_trades,**kwargs):
  super().__init__(*args,policies=('B',),**kwargs)
  self.gold_daily=gold_daily;self.gold_trades=gold_trades;self.diag=[];self.snapshots=[];self.first_exclusive=set();self.eligible=[];self.intent_log=[];self.actual_open_routes=[]
  self.attempt_start={}
  self.fixed_dates={}
  for sector,rows in self.industry_rows.items():
   for day,r in rows.items():
    if r['action']=='probe':self.attempt_start[str(r['E0_episode'])+':'+str(r['receipt_id'])]=day
   if sector in SPECS:
    begin,end,peak=SPECS[sector];selected=[r for d,r in rows.items() if begin<=d<=end]
    dates={'price_peak':peak}
    for stage,label in [(2,'first_confirmed_or_higher'),(3,'first_expanded')]:
     found=next((r for r in selected if r['stage']>=stage),None)
     dates[label]=found['day'] if found else None
    self.fixed_dates[sector]=dates
  dates,cols,score=self.bundle._h1_cache;self.h1_dates=dates;self.h1_cols=cols;self.h1_score=score
 def h1(self,sid,at):
  p=self.h1_dates.searchsorted(pd.Timestamp(at.date()),side='right')-1;j=self.h1_cols.get(sid)
  if p<0 or j is None:return None
  x=float(self.h1_score[p,j]);return x if math.isfinite(x) else None
 def scalar(self,a):
  b=a.budget;pc,pr,_=b.resources('probe');cc,cr,_=b.resources('confirmed');capital,risk,reserve=b.resources()
  fees=sum(o.qty*o.fee_per_share for o in b.orders.values() if o.status in ('open','cancel_pending'))
  return dict(marked_NAV=b.nav,last_decision_NAV=str(a.current_nav),available_cash=str(a.available),
   inventory_value=sum(x.qty*b.prices[x.stock] for x in b.lots),total_capital_with_pending=capital,total_risk=risk,
   probe_capital=pc,probe_risk=pr,confirmed_capital=cc,confirmed_risk=cr,pending_reserve=reserve,pending_fees=fees,
   nominal_risk_limit_before_new_order_fee=.03*(b.nav-fees),ACT_on=a.risk_state['on'])
 def snapshot(self,a,at,known_at,label,candidate=None):
  b=a.budget;actual={str(x['id']):x for x in a.layers};lots=[];pending=[];by_stock=collections.defaultdict(lambda:dict(risk=0.,principal=0.,giveback=0.,value=0.,qty=0,lots=[]))
  for x in b.lots:
   m=b.prices[x.stock];q=x.qty;cost=x.cost;floor=x.floor;p=q*max(min(m,cost)-floor,0.);g=q*max(m-max(cost,floor),0.);risk=q*max(m-floor,0.)
   assert abs(p+g-risk)<1e-7,(x.batch,'risk partition')
   z=actual[x.batch];row=self.facts.row(x.stock,known_at);state=b.sectors[x.sector];scheduled=x.stock in a.exits and z['id'] in a.sell_layers.get(x.stock,set())
   known_i=None if row is None or pd.isna(row.i_target) else bool(row.i_target)
   known_e0=None if row is None or pd.isna(row.e0_target) else bool(row.e0_target)
   if scheduled:reason='native sell request outstanding; unsold shares still consume resources'
   elif x.role=='core' and known_i is True and a.risk_state['on']:reason='original I core remains valid; ACT on; no core exit required'
   elif x.role=='mobile':reason='no outstanding exit for this layer; native mobile close protection has not latched an exit; industry invalidation alone does not sell it'
   else:reason='unknown; inspect native state rather than infer from eventual outcome'
   item=dict(batch=x.batch,stock=x.stock,sector=x.sector,pool=x.pool,role=x.role,quantity=q,unit_raw_fill_cost_split_adjusted=cost,mark=m,effective_raw_floor=floor,
    principal_downside=p,profit_giveback=g,risk=risk,market_value=q*m,gross_mark_profit=q*(m-cost),
    full_layer_economic_PnL_including_realized_cash_and_dividend=float(z['cash']+z['dividend'])+q*m,
    opened=z['opened'],holding_calendar_days=(at.date()-z['opened'].date()).days,attempt=x.attempt,attempt_started=self.attempt_start.get(x.attempt),
    current_industry_attempt=state.attempt,current_industry_active=state.active,current_industry_level=state.level,
    old_attempt_probe_occupancy=x.pool=='probe' and x.attempt!=state.attempt,
    known_stock_I=known_i,known_stock_E0=known_e0,
    known_stock_H1=self.h1(x.stock,known_at),known_sector_H1=self.h1(x.sector,known_at),
    has_pending_buy=x.stock in a.buys,has_pending_sell=scheduled,why_not_exited=reason)
   lots.append(item);s=by_stock[x.stock];s['risk']+=risk;s['principal']+=p;s['giveback']+=g;s['value']+=q*m;s['qty']+=q;s['lots'].append(x.batch)
  for o in b.orders.values():
   if o.qty<=0 or o.status not in ('open','cancel_pending'):continue
   pending.append(dict(order=o.oid,stock=o.stock,sector=o.sector,role=o.role,pool=o.pool,quantity=o.qty,unit_limit=o.limit,floor=o.floor,
    capital=o.qty*o.limit,risk=o.qty*max(o.limit-o.floor,0.),fees=o.qty*o.fee_per_share,status=o.status,created_bar=o.created_bar,attempt=o.attempt))
  principal=sum(x['principal_downside'] for x in lots);giveback=sum(x['profit_giveback'] for x in lots);pending_risk=sum(x['risk'] for x in pending)
  assert abs(principal+giveback+pending_risk-b.resources()[1])<1e-6
  sectors=collections.defaultdict(lambda:dict(risk=0.,principal=0.,giveback=0.,value=0.))
  for x in lots:
   s=sectors[x['sector']];s['risk']+=x['risk'];s['principal']+=x['principal_downside'];s['giveback']+=x['profit_giveback'];s['value']+=x['market_value']
  for x in pending:sectors[x['sector']]['risk']+=x['risk']
  return dict(label=label,at=at,signal_evidence_known_at=known_at,candidate=candidate,resources=self.scalar(a),
   principal_downside=principal,profit_giveback=giveback,pending_buy_risk=pending_risk,
   decomposition_gap=principal+giveback+pending_risk-b.resources()[1],
   cost_definition='original budget Lot.cost: actual raw buy fill price adjusted for splits; fees/dividends separate; not a newly reset personal cost',
   top10_stocks=sorted([dict(stock=k,**x) for k,x in by_stock.items()],key=lambda x:x['risk'],reverse=True)[:10],
   top10_sectors=sorted([dict(sector=k,**x) for k,x in sectors.items()],key=lambda x:x['risk'],reverse=True)[:10],lots=lots,pending_orders=pending)
 def route(self,a,i,x,at):
  before=self.scalar(a);rid=i.get('CP1_id');sector=self.sector_by_sid[i['sid']];known=i['clock'].decision_at;target=i['role']=='mobile' and in_case(sector,str(known.date()))
  snap=self.snapshot(a,at,known,'target_mobile_before_route',dict(stock=i['sid'],receipt=rid,H1=i['score'],sector=sector,rank=i['rank'])) if target else None
  answer,why=super().route(a,i,x,at)
  self.actual_open_routes.append(dict(at=at,signal_at=known,sid=i['sid'],sector=sector,role=i['role'],CP1_id=rid,rank=i['rank'],
   actual=answer,why=why,risk_before=before['total_risk'],pending_reserve_before=before['pending_reserve']))
  if i['role']=='mobile':
   if answer:cf,cfwhy=answer,'already_admitted_actual_quantity; no counterfactual order submitted'
   else:
    b=a.budget;unchanged=(a.available,len(b.orders),len(b.consumed),len(b.stock_requests),b.resources())
    cf,cfwhy=no_account_check(self,a,i,x,at)
    assert unchanged==(a.available,len(b.orders),len(b.consumed),len(b.stock_requests),b.resources()),'counterfactual mutated real path'
   row=dict(at=at,signal_at=known,sid=i['sid'],sector=sector,receipt=rid,actual_route=answer,actual_reason=why,
    without_account_check_route=cf,without_account_check_reason=cfwhy,resources_before=before,H1=i['score'],rank=i['rank'])
   self.diag.append(row)
   if snap:
    snap['route']=row;self.snapshots.append(snap)
    if why=='account_risk' and sector not in self.first_exclusive:
     self.first_exclusive.add(sector);L.save(OUT/('FIRST_EXCLUSIVE_'+sector+'.json'),snap)
     if not (OUT/'FIRST_COMPLETE_BLOCK.json').exists():L.save(OUT/'FIRST_COMPLETE_BLOCK.json',snap)
  return answer,why
 def planning(self,at):
  before=len(self.opportunities);super().planning(at);a=self.accounts['B'];d=str(at.date())
  assert L.W.canon(self.daily[-1])==self.gold_daily[d],('B daily changed',d)
  assert L.W.canon(a.trades)==self.gold_trades[:len(a.trades)],('B trade prefix changed',d)
  pending={(i['sid'],i['role']):i for i in a.pending}
  for r in self.opportunities[before:]:
   if not r['CP1_id'] or r['mobile_Q'] is not True:continue
   s=a.budget.sectors.get(r['sector']);i=pending.get((r['sid'],'mobile'))
   self.eligible.append(dict(receipt=r['CP1_id'],sid=r['sid'],sector=r['sector'],day=d,roles=r['roles'],barriers=r['barriers'],
    industry_active=bool(s and s.active),industry_level=None if s is None else s.level,
    mobile_intent_created=i is not None,earliest_execution=None if i is None else i['clock'].earliest_execution_at))
  for i in a.pending:self.intent_log.append(dict(day=d,sid=i['sid'],role=i['role'],CP1_id=i.get('CP1_id'),earliest=i['clock'].earliest_execution_at))
  # One compact complete lot-risk state each close; fixed label selection later
  # does not require a second historical run.
  self.snapshots.append(self.snapshot(a,at,at,'daily_close'))
 def checkpoint(self,out,last_event):
  # Preserve an actual restart state as well as the small progress manifest.
  # In particular a budget stop must not discard the in-memory diagnostics.
  out=Path(out);out.mkdir(parents=True,exist_ok=True)
  keys=('last_epoch','epoch','global_watch','applied_actions','daily','risk','opportunities','stage_events','funding','balance_audit',
   'diag','snapshots','first_exclusive','eligible','intent_log','actual_open_routes')
  payload=dict(last_completed_event=last_event,source_freeze=self.source_freeze,
   runner={k:getattr(self,k) for k in keys},
   accounts={k:{f:v for f,v in a.__dict__.items() if f not in ('market','facts')} for k,a in self.accounts.items()})
  raw=pickle.dumps(payload,protocol=5);target=out/'checkpoint.pkl';temp=out/'checkpoint.tmp';temp.write_bytes(raw);temp.replace(target)
  assert pickle.loads(raw)['last_completed_event']==last_event
  L.save(OUT/'PROGRESS.json',dict(last_completed_event=last_event,closes=len(self.daily),unique_routed_mobile=len(self.diag),first_exclusive_sectors=sorted(self.first_exclusive)))

def main():
 assert not (OUT/'DONE.json').exists(),'do not duplicate completed diagnostic replay'
 OUT.mkdir(exist_ok=True);L.save(OUT/'PROTOCOL.json',dict(no_policy_change=True,scope='same frozen full-universe B only',budget_load_replay_seconds=300,
  estimate_seconds=[210,240],revision='authorized repaired instrumentation replay; old failed180s evidence retained',counterfactual='remove account_risk check only, independent read-only instantaneous requests; never submit or sum quantity',
  actual_source='run-universe/pair B; exact every-close daily and trade-prefix assertions',snapshot_selection='each case earliest raw exclusively account_risk route refusal; first confirmed/expanded market observation and old price-peak close'))
 (OUT/'COUNTERFACTUAL_SOURCE.py').write_text(pure)
 started=time.monotonic();shared,receipts,cp,states,ir,identity=L.inputs('universe')
 golden=json.load(gzip.open(J.O/'run-universe/pair/B.json.gz','rt'));gd={}
 for line in gzip.open(J.O/'run-universe/pair/daily.jsonl.gz','rt'):
  r=json.loads(line)
  if r['account']=='B':gd[str(r['at'])[:10]]=r
 r=DiagnosticRunner(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir,gold_daily=gd,gold_trades=golden['trades'])
 r.source_freeze={str(J.O/'joint_v3.py'):L.sha(J.O/'joint_v3.py'),str(J.BASE/'budget_v3/model.py'):L.sha(J.BASE/'budget_v3/model.py'),str(Path(__file__)):L.sha(__file__),str(L.U/'STOCK_MANIFEST.json'):L.sha(L.U/'STOCK_MANIFEST.json')}
 prepared=time.monotonic();print('DIAGNOSTIC_INPUT_READY',prepared-started,flush=True)
 (OUT/'technical').mkdir(parents=True,exist_ok=True)
 try:done=r.run_prepared(OUT/'technical',max(1,300-(prepared-started)))
 finally:persist_available(r)
 if not done:
  L.save(OUT/'BUDGET_STOP.json',dict(load_seconds=prepared-started,total_seconds=time.monotonic()-started,no_strategy_result=True,progress=r.daily[-1]['at'] if r.daily else None));return
 a=r.accounts['B'];assert L.W.canon(a.trades)==golden['trades'];assert str(a.current_nav)==golden['ending_NAV']
 dump_gz(OUT/'ROUTED_MOBILE.jsonl.gz',r.diag);dump_gz(OUT/'RISK_SNAPSHOTS.jsonl.gz',r.snapshots)
 dump_gz(OUT/'ALL_ACTUAL_ROUTE_SEQUENCE.jsonl.gz',r.actual_open_routes);dump_gz(OUT/'ELIGIBLE_CP1.jsonl.gz',r.eligible);dump_gz(OUT/'ACTUAL_INTENTS.jsonl.gz',r.intent_log)
 L.save(OUT/'FIXED_STAGE_DATES.json',r.fixed_dates)
 L.save(OUT/'DONE.json',dict(completed=True,load_seconds=prepared-started,total_load_replay_audit_seconds=time.monotonic()-started,
  B_actual_trades_exact=True,B_all182_daily_rows_exact=True,B_ending_NAV=golden['ending_NAV'],new_policy_paths=0,diagnostic_same_B_replay=1,
  unique_global_Q_pass_CP1=len(r.eligible),routed_mobile_records=len(r.diag),snapshot_count=len(r.snapshots),no_counterfactual_mutation=True,
  sources=r.source_freeze))
 print('DIAGNOSTIC_DONE',time.monotonic()-started,len(r.eligible),len(r.diag),flush=True)

if __name__=='__main__':main()
