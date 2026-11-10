"""Saved-event attribution only. No financial event or modified account preview."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json,pickle,sys,hashlib
HERE=Path(__file__).resolve().parent;W=HERE.parent;ORIG=W/'g-s-C-two-day-finance-20261102'
sys.path.insert(0,str(ORIG));import provider_fix1 as F
P=F.P;E=F.E;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def save(p,x):E.IO.write_json(p,x,encoder=E.encode)
def load(p):
 side=read(p.with_suffix('.provenance.json'));assert P.sha(p)==side['checkpoint_sha256']
 with p.open('rb') as f:r=pickle.load(f)
 return r
def getpaths(k,mode):
 days=P.EXPECTED[k];out=[]
 for day in days:
  for phase in ('OPEN','CLOSE'):
   root=ORIG/'runs'/f'{k}-{mode}'
   if k=='2022' and mode=='C10' and day==days[-1] and phase=='CLOSE':root=ORIG/'runs/2022-C10-recovered'
   out.append(root/(day+'-'+phase+'.json'))
 return out
def analyze(k):
 end=getpaths(k,'C10')[-1];r=load(end.with_suffix('.pkl'));a=r.account;opening=P.EXPECTED[k][-1]+' 09:30:00+08:00'
 result=r.results[0];cert=result['certificate'];v=r.trusted[cert['trusted_id']];s=v['snapshot'];ds=v['demands'];dem={z['sid']:z for z in ds}
 stats=defaultdict(lambda:dict(candidate_count=0,positive_Q=0,maximum_capital=Z,planned_close_gross=Z,reserved_open_gross=Z,filled_gross=Z,closing_market_value=Z))
 detail=[];Q=cert['Q']
 for d in ds:
  st=stats[d['sector']];st['candidate_count']+=1;st['maximum_capital']+=D(d['max_q'])*d['mark'];q=Q[d['sid']];st['positive_Q']+=q>0;st['planned_close_gross']+=D(q)*d['mark']
 for sid,q in Q.items():
  if not q:continue
  d=dem[sid];oid=next((o for o,m in a.supports.items() if m.get('C_certificate')==cert['certificate_id'] and m['original_intent']['sid']==sid),None)
  m=a.supports.get(oid);unit=m['limit'] if m else Z;reserved=D(m['quantity'])*unit if m else Z;fillq=sum(f.shares for f in a.fills if f.security_id==sid);gross=sum((f.gross_cny for f in a.fills if f.security_id==sid),Z)
  mark=a.market.prices[sid];st=stats[d['sector']];st['reserved_open_gross']+=reserved;st['filled_gross']+=gross;st['closing_market_value']+=D(fillq)*mark
  raw_upper=int(d['max_q']);native_constraints=[]
  if m and m['quantity']<q:
   # This is a bound identity from the saved original request, not a relaxed
   # feasibility preview: p*Q exceeds the ORIGINAL ten-percent target.
   if D(q)*unit>D(s['decision_nav'])*D('.1'):native_constraints.append('stock10_or_10percent_per_stock_target_at_open')
  detail.append(dict(sid=sid,sector=d['sector'],use=d['use'],max_q=raw_upper,planned_q=q,planned_close_mark=d['mark'],planned_close_gross=D(q)*d['mark'],reserved_q=m['quantity'] if m else 0,opening_limit=unit,reserved_open_gross=reserved,filled_q=fillq,filled_gross=gross,closing_market_value=D(fillq)*mark,clipped_constraints_proven=native_constraints,notes='not isolated causal attribution if multiple constraints coexist'))
 planned=sum(D(q)*dem[sid]['mark'] for sid,q in Q.items() if q)
 submitted=sum(z['reserved_open_gross'] for z in detail);cfills=sum(z['filled_gross'] for z in detail)
 torders={oid:m for oid,m in a.supports.items() if m['use']=='T'}
 t_reserved=sum((D(m['quantity'])*m['limit'] for m in torders.values()),Z)
 allgross=sum((f.gross_cny for f in a.fills if f.side=='buy'),Z);tfill=allgross-cfills
 cmark=sum((z['closing_market_value'] for z in detail),Z);inv=a.exported(r.last_completed_event)['balance']['inventory'];b=a.exported(r.last_completed_event)['balance']
 assert allgross==cfills+tfill
 projected_risk_checks=[z for z in result['projection']['validation']['checks'] if z['constraint']=='account_risk6']
 raw_need=Counter()
 for z in result['projection']['trace']:
  if not z['q']:
   for why in z['blockers_or_necessary_bounds']:
    if why.startswith('necessary_bound:'):raw_need[why]+=1
 forward=[]
 for result in r.results:
  cert=result['certificate'];vv=r.trusted[cert['trusted_id']];dd={d['sid']:d for d in vv['demands']}
  count=sum(q>0 for q in cert['Q'].values());checks=result['projection']['native_checks'];factor=(3+count) if result is r.results[0] else 2
  forward.append(dict(at=result['at'],demands=len(dd),positive_Q=count,zero_Q=sum(not q for q in cert['Q'].values()),D=cert['D'],planned_close_gross=sum((D(q)*dd[sid]['mark'] for sid,q in cert['Q'].items() if q),Z),native_checks_per_projection=checks,source_derived_successful_solve_calls=factor,native_check_work_lower_bound=checks*factor,
   count_status='source-derived: plan solve+verify, first active opening verify, and one verify per positive-Q submit attempt; not runtime instrumented'))
 return dict(window=k,source_checkpoint=str(end.with_suffix('.pkl')),source_sha256=P.sha(end.with_suffix('.pkl')),first_day_snapshot=dict(nav=s['nav'],decision_nav=s['decision_nav'],available=s['available'],rows=len(s['rows']),demands=len(ds)),
  waterfall=dict(reference90percent_initial_NAV=D(900000),C_planned_close_gross=planned,planning_gap_from90=D(900000)-planned,C_reserved_open_gross=submitted,C_price_and_qty_delta=submitted-planned,C_fill_gross=cfills,C_execution_gross_shortfall=submitted-cfills,T_reserved_gross=t_reserved,T_actual_fill_gross=tfill,total_actual_fill_gross=allgross,closing_inventory=inv,holding_price_movement=inv-allgross,fees=b['fees_cny'],closing_NAV=b['nav'],closing_inventory_over_NAV=inv/b['nav'],ending_native_buy_reserve=b['order_reserved'],notes='only arithmetic path terms telescope; constraint capacities/opportunities do not add'),
  C_rows=detail,sector_first_plan={sec:dict(z) for sec,z in stats.items()},first_plan_last_risk_check=projected_risk_checks[-1] if projected_risk_checks else None,first_plan_zero_Q_necessary_bounds=dict(raw_need),plans=forward,
  first_open_routes=a.rejections,terminal_native_callbacks=a.native_callbacks,
  metadata=dict(first_day_full_no_position=True,actual_first_OPEN_has_no_intents=True,price_future_used_by_diagnostic_only=False,financial_events_executed=0))
def timings(k,mode):
 roots=getpaths(k,mode);completion=read(roots[-1].parent/'COMPLETED.json');start=completion.get('started_at');events=[]
 prior=datetime.fromisoformat(start).timestamp() if start else None
 for p in roots:
  t=p.stat().st_mtime
  # C10 recovery is a separate clock, not contiguous timing for the old arm.
  if k=='2022' and mode=='C10':prior=None
  events.append(dict(event=p.name,saved_wall_UTC=datetime.fromtimestamp(t,timezone.utc).isoformat(),seconds_since_prior_save_or_run_start=t-prior if prior is not None else None,includes='event + checkpoint export + I/O; not pure method timing'))
  prior=t
 return dict(window=k,mode=mode,run_started=start,run_completed=completion.get('completed_at'),events=events,total_seconds=(datetime.fromisoformat(completion['completed_at'])-datetime.fromisoformat(start)).total_seconds() if start else None,method_profile_available=False)
def main():
 F.guard();P.H.guards();P.engine_guard()
 out=dict(scope='read-only saved-event diagnostic; financial events0',windows={k:analyze(k) for k in P.EXPECTED},timings=[timings(k,m) for k in P.EXPECTED for m in ('C10','C_BATCH20')],original_index_sha256=P.sha(ORIG/'ARTIFACT_SHA256.json'))
 save(HERE/'DIAGNOSTIC.json',out)
 print(json.dumps({k:z['waterfall'] for k,z in out['windows'].items()},default=str,indent=2))
if __name__=='__main__':main()
