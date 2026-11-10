"""Fixed descriptive joins. Future labels never select a new trading rule."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
from datetime import date
import gzip,hashlib,json,time
import analyze_matched_holdings as A
O=Path(__file__).resolve().parent;SRC={};Z=D(0)
def read(p,lines=False):
 p=Path(p);SRC[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
 if p.suffix=='.gz':
  with gzip.open(p,'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
 return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def dist(vals):
 a=sorted(D(str(v))for v in vals);n=len(a)
 return dict(n=n,mean=sum(a,Z)/n if n else None,median=(a[n//2]if n%2 else(a[n//2-1]+a[n//2])/2)if n else None,
  p10=a[int((n-1)*.1)]if n else None,p90=a[int((n-1)*.9)]if n else None,min=a[0]if n else None,max=a[-1]if n else None)
def period(r):
 d=r['OPEN']
 return(d[:4]if d<'2024-09-24'else'2024_after924')if r['window']=='long'else('2026H1'if d>='2026-01-01'else'2025H2')
def main():
 start=time.monotonic();SRC[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 p=O/'EXANTE_DIAGNOSTIC_STRATA.txt';SRC[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
 rows=read(O/'MATCHED_HOLDINGS.jsonl.gz',True)
 feats={r['key']:r for r in read(O/'features/EXANTE_EVENT_FEATURES.jsonl.gz',True)}
 events={r['key']:r for r in read(O/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz',True)}
 later={r['first_event_key']:r for r in read(O/'events/FIRST_SOURCE_I_EPOCH_REJECT_WITH_LATER_BUYS.json')}
 for r in rows:
  r['exante']=feats[r['key']];r['period']=period(r)
  r['semiconductor126']=r['industry']=='URFI881121'
  r['later_original_participation']=later.get(r['key'])
 save('FOUR_QUADRANT_BY_WINDOW.json',A.summary(rows,lambda r:r['window']))
 save('FOUR_QUADRANT_BY_OPEN_COHORT.json',A.summary(rows,lambda r:(r['window'],r['period'])))
 save('FOUR_QUADRANT_PURE_INDUSTRY.json',A.summary([r for r in rows if r['classification']in['sector_capital_only','both_sector_only']],lambda r:(r['window'],r['classification'])))
 save('SEMICONDUCTOR_FOUR_QUADRANTS.json',A.summary([r for r in rows if r['semiconductor126']],lambda r:(r['window'],r['period'])))
 groups=[('PVR_gap',lambda r:r['exante']['PVR_gap_stratum']),
  ('old_COR_weak',lambda r:r['exante']['old_COR_weak_stratum']),
  ('candidate_COR_new_and_any_old_weak',lambda r:'yes'if r['exante']['candidate']['COR_new_ok']is True and r['exante']['old_COR_weak_count']>0 else'no_or_unknown'),
  ('original_lock',lambda r:'prior_exit_lock'if r['exante']['old_prior_CLOSE_exit_lock_stock_count']else'no_prior_stock_exit_lock'),
  ('capital_bound',lambda r:'not_ruled_out'if r.get('not_ruled_out_by_capital_bound')else'ruled_out_or_unknown')]
 for name,fn in groups:save('EXANTE_'+name+'_OUTCOMES.json',A.summary(rows,lambda r:(r['window'],fn(r))))
 counts=defaultdict(Counter);money=defaultdict(lambda:defaultdict(list));single_new=[]
 for r in rows:
  e=events[r['key']];k=(r['window'],r['period']);c=counts[k];c['first_events']+=1
  q=e['original_OPEN_contract_preview'];money[k]['minimum_buy_cash'].append(q['dated_minimum_cash']);money[k]['frozen_preview_max_gross'].append(q['OPEN_preview_max_gross'])
  n=r['new'];c[n['status']]+=1
  if n.get('known_net'):
   money[k]['candidate_net_return_pct'].append(n['net_return_pct']);money[k]['candidate_net_PnL_at_minimum_unit'].append(n['net_liquidation_profit'])
   money[k]['holding_calendar_days'].append((date.fromisoformat(n['horizon_CLOSE_day'])-date.fromisoformat(n['OPEN'])).days)
  if r['matched_status']=='known_conditional_match'and r['classification']in['sector_capital_only','both_sector_only']and r['quadrant']=='new_profit_old_loss':
   single_new.append(dict(key=r['key'],window=r['window'],period=r['period'],classification=r['classification'],
    new_return=r['new_net_return_pct'],old_return=r['old_all']['old_net_return_from_current_gross_mark_pct'],
    equal_cash_gap=r['equal_cash_gap'],required_relief_scenario_gap=r.get('release_adjusted_conditional_gap'),
    not_ruled_out_by_capital_bound=r.get('not_ruled_out_by_capital_bound'),
    PVR_gap=r['exante']['PVR_gap_stratum'],candidate_COR_new_ok=r['exante']['candidate']['COR_new_ok'],
    old_COR_weak_count=r['exante']['old_COR_weak_count'],old_prior_exit_lock=r['exante']['old_prior_CLOSE_exit_lock_stock_count']))
 save('CANDIDATE_NET_AND_AMOUNT_DISTRIBUTIONS.json',[dict(window=k[0],OPEN_cohort=k[1],counts=dict(v),distributions={n:dist(x)for n,x in money[k].items()})for k,v in counts.items()])
 save('PURE_INDUSTRY_NEW_PROFIT_OLD_LOSS_ALL.json',single_new)
 # Same batch actual fills are a different baseline, not old assets available to sell.
 batch=[]
 for r in rows:
  b=r.get('same_batch_filled_alternatives',{})
  if b.get('status')!='actual_committed_new_fills_Tplus1_not_rotation_donors'or not r['new'].get('known_net'):continue
  nr=D(r['new']['net_return_pct']);orr=D(b['net_return_from_actual_buy_cash_pct'])
  batch.append(dict(key=r['key'],window=r['window'],OPEN_cohort=r['period'],new_net_return_pct=nr,
    committed_net_return_pct=orr,quadrant=A.quadrant(nr,orr),can_sell_committed_at_that_OPEN=False))
 save('SAME_BATCH_ACTUAL_FILL_COMPARISON.json',batch)
 bc=[]
 for w in ['long','strong']:
  a=[r for r in batch if r['window']==w];bc.append(dict(window=w,events=len(a),quadrants=dict(Counter(r['quadrant']for r in a)),
   candidate_return=dist(r['new_net_return_pct']for r in a),committed_return=dist(r['committed_net_return_pct']for r in a)))
 save('SAME_BATCH_SUMMARY.json',bc)
 pure=[r for r in rows if r['matched_status']=='known_conditional_match'and r['classification']in['sector_capital_only','both_sector_only']]
 examples=[]
 for quad in ['new_profit_old_profit','new_profit_old_loss','new_loss_old_profit','new_loss_old_loss']:
  a=[r for r in pure if r['quadrant']==quad and r.get('not_ruled_out_by_capital_bound')and r.get('release_adjusted_conditional_gap')is not None]
  if not a:continue
  a.sort(key=lambda r:D(r['release_adjusted_conditional_gap']))
  for r in [a[0],a[-1]]if len(a)>1 else a:
   examples.append(dict(key=r['key'],quadrant=quad,display_selection='Posthoc low/high required-release scenario among pure-industry not-capital-excluded cases; never a signal',
    event=events[r['key']],new=r['new'],old_all=r['old_all'],release_bound=r['release_bound'],
    equal_cash_gap=r['equal_cash_gap'],release_adjusted_conditional_gap=r['release_adjusted_conditional_gap'],exante=r['exante']))
 save('BALANCED_EXAMPLES.json',examples)
 # Keep the complete joined event table so all descriptive slices are reproducible.
 with gzip.open(O/'MATCHED_WITH_EXANTE.jsonl.gz','wt')as h:
  for r in rows:h.write(json.dumps(r,ensure_ascii=False,default=str,allow_nan=False)+'\n')
 save('OPPORTUNITY_COST_SOURCE_SHA256.json',SRC)
 save('OPPORTUNITY_COST_SCOPE.json',dict(rows=len(rows),known_old_matches=sum(r['matched_status']=='known_conditional_match'for r in rows),
  seconds=time.monotonic()-start,new_portfolio_policy_accounts=0,read_only_join=True,period_definition='OPEN-entry cohort, not calendar-period portfolio wealth',
  all_future_evaluation_only=True,unknown_retained=True,source_schema_caveat='COR diagnostic is original pure evidence projection, not the full old RS/age/weekly policy. PVR strata are independent diagnostics, not a COR/PVR hybrid rule.',
  money_not_summed_as_portfolio_gain=True))
 print(json.dumps(dict(rows=len(rows),pure_new_profit_old_loss=len(single_new),same_batch_cases=len(batch),seconds=time.monotonic()-start),ensure_ascii=False))
if __name__=='__main__':main()
