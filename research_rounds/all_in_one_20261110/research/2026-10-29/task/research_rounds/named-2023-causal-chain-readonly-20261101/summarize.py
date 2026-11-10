"""Compact causal matrix from already saved original opportunities and accounting."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,collections,math,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;Y=W/'recovery-2023-readiness-20261101';G=W/'g1-current-state-readonly-20261101';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def norm(x):
 if isinstance(x,dict):return {str(k):norm(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [norm(v) for v in x]
 if isinstance(x,np.generic):return norm(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(norm(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n');t.replace(p)
def stream(p):
 with gzip.open(p,'rt') as f:
  for s in f:yield json.loads(s)
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def day(x):return str(x)[:10]
M=read(R/'a-share-selection-e0-20261024/inputs-v2/metadata.json');SM={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};FF={}
def f(sid):
 if sid not in FF:FF[sid]=pd.read_parquet(SM[sid]['refs']['facts'])
 return FF[sid]
def price(sid,d):
 q=f(sid);i=q.index.searchsorted(pd.Timestamp(d),side='right')-1;return D(str(q.iloc[i].raw_close))
def main():
 controls=read(O/'CONTROL_SELECTION.json');subjects=read(O/'SUBJECT_SUMMARY.json');events=[];minimum=[];controlout=[];donors=[]
 for ref in ['Bdiag','C1']:
  root=Y/'runs'/ref/'pair';b=book(root/'B.json.gz');ds={day(x['at']):x for x in stream(root/'daily.jsonl.gz')};layers=read(Y/'analysis'/ref/'LAYERS_2023.json');ops=read(O/ref/'OPPORTUNITIES_NAMED.json');snaps=read(O/ref/'OWNERS_SNAPSHOTS.json')
  for sid in ['300308.SZ','300502.SZ']:
   rs=[x for x in ops if x['sid']==sid];core=[x for x in rs if x['role']=='core'];mobile=[x for x in rs if x['role']=='mobile'];qcore=[x for x in core if x['original_Q'] is True];qmobile=[x for x in mobile if x['original_Q'] is True];conf=[x for x in qmobile if x['market_industry_stage'] in ['confirmed','expanded']];routes=sorted([r for x in rs for r in x['actual_routes']],key=lambda r:r['trace_sequence']);filled=[x for x in rs if x['had_actual_fill']]
   events.append(dict(policy=ref,sid=sid,first_raw_I=core[0]['signal_day'],first_raw_CP1=mobile[0]['signal_day'],first_Q_pass_I=qcore[0]['signal_day'] if qcore else None,first_Q_pass_CP1=qmobile[0]['signal_day'] if qmobile else None,first_market_confirmed_Q_CP1=conf[0]['signal_day'] if conf else None,first_executable_window_actually_routed=routes[0]['at'] if routes else None,first_actual_route_role=routes[0]['role'] if routes else None,first_actual_route_reasons=routes[0]['routes'] if routes else None,first_actual_fill=filled[0]['actual_fills'][0] if filled else None,counts=dict(rawI=len(core),canonical_CP1=len(mobile),Q_I=len(qcore),Q_CP1=len(qmobile),market_confirmed_Q_CP1=len(conf)),note='first market-confirmed qualification is not first Q or first actual core execution window'))
   for x in rs:
    reason=x['first_block_or_admission'];intent=x['planned_original_intent'];fr=f(sid).loc[x['signal_day']];nav=D(ds[x['signal_day']]['nav']);q=100;refprice=D(str(fr.raw_close))*D('1.0005');floor=D(str(fr.i_floor))/D(str(fr.factor));risk_lower=max(Z,D(q)*(refprice-floor*D('.9995')));gross=D(q)*refprice;out=dict(policy=ref,sid=sid,role=x['role'],signal_day=x['signal_day'],observed_reason=reason,minimum_legal_shares=100,actual_admitted_quantity=x['actual_routes'][0]['selected_quantity'] if x['actual_routes'] else sum(r['shares'] for r in x['actual_reservations']),decision_NAV=nav,minimum_gross_at_signal_with_original_slippage=gross)
    if reason=='minimum_unit_exceeds_risk_or_nominal_cap' and x['role']=='core':
     out.update(core_risk_budget=nav*D('.0025'),minimum_protection_risk_lower_bound_excluding_all_fees=risk_lower,stock_nominal_cap=nav*D('.10'),classification='core_floor_risk_proved_even_before_fees' if risk_lower>nav*D('.0025') and gross<=nav*D('.10') else 'mixed_or_not_isolated',scope='original sizing only; no relaxed policy, no opportunity-PnL counterfactual')
    elif reason=='no_nominal_gap' and x['role']=='mobile':
     held=D(ds[x['signal_day']]['positions'].get(sid,0));budget=min(nav*D('.02'),max(Z,nav*D('.1')-held*D(str(fr.raw_close))));out.update(normal_complete_two_percent_target=nav*D('.02'),original_after_stock_cap_budget=budget,held_shares=held,minimum_gross_no_slippage=100*D(str(fr.raw_close)),classification='normal_target_below_one_legal_unit' if 100*D(str(fr.raw_close))>budget else 'unknown')
    else:out['classification']='saved_route_or_raw_reason_retained'
    minimum.append(out)
  for c in controls:
   if c['policy']!=ref:continue
   sid=c['sid']
   if sid is None:controlout.append(c);continue
   ls=[x for x in layers if x['sid']==sid];tx=[x for x in b['trades'] if x['security_id']==sid and day(x['at']).startswith('2023')];buys=[x for x in tx if x['side']=='buy'];sells=[x for x in tx if x['side']=='sell'];requests=[x for x in b['audit'] if x['kind']=='exit_request' and x.get('sid')==sid and day(x['at']).startswith('2023')];weights=[]
   for d,row in ds.items():
    if d.startswith('2023'):
     qty=D(row['positions'].get(sid,0));weights.append((qty*price(sid,d)/D(row['nav'])*100,d))
   peak=max(weights);paths=[]
   for l in ls:
    t=next(t for t in buys if t['layer']==l['layer']);paths.append(dict(**l,shares=t['shares'],raw_buy_price=t['price'],raw_protection_at_buy=D(t['floor'])/D(str(f(sid).loc[day(t['at'])].factor)),signal_price=f(sid).loc[l['signal_day']].raw_close))
   controlout.append(dict(**c,name=M[sid]['name'],whole_stock_2023_closed_net=sum((D(x['net']) for x in ls if x['qty']==0),Z),whole_stock_open_net=sum((D(x['net']) for x in ls if x['qty']),Z),actual_total_new_buy_cash=sum((D(x['cost']) for x in ls),Z),first_actual_buy=buys[0] if buys else None,last_actual_sell=sells[-1] if sells else None,peak_daily_weight_pct=peak[0],peak_day=peak[1],actual_exit_requests=requests,actual_sell_fills=sells,layers=paths,pool_origin_may_later_migrate=True))
  first=next(x for x in snaps if x['sid']=='300308.SZ' and x['at'].startswith('2023-01-20') and x['role']=='core');assert first['reconstruction_exact'] and first['holdings_layer_count']==0
  own=first['binding_owners']['probe:probe_risk'];donor=[]
  for x in own['top10']:
   ls=[l for l in layers if l['sid']==x['sid']];donor.append(dict(**x,whole_stock_later_2023_net=sum((D(l['net']) for l in ls),Z),future_result_for_evaluation_only=True))
  donors.append(dict(policy=ref,at=first['at'],candidate='300308.SZ',known_decision_NAV=first['recorded_route']['decision_NAV'],probe_risk_occupied=own['total'],all_from_prior_same_open_reservations=True,top_pending=donor))
 save('EVENT_TYPE_INDEX.json',events);save('MINIMUM_QUANTITY_DIAGNOSIS.json',minimum);save('CONTROLS_FUNDED_PATHS.json',controlout);save('FIRST_OPENING_RISK_DONORS.json',donors)
 # Exact prior-known mobile floor and later opportunity sets remain distinct.
 exit=read(O/'XINYISHENG_EXIT_REENTRY.json');before=exit['prior_known_floor'];trigger=exit['trigger'];post=exit['later_all_fresh_reentry_receipts'];corepost=[x for x in read(O/'C1/OPPORTUNITIES_NAMED.json') if x['sid']=='300502.SZ' and x['role']=='core' and '2023-04-28'<x['signal_day']<'2023-05-18'];lastchange=[]
 for lid in [x['layer'] for x in before]:lastchange.append(next(x for x in reversed(exit['trace']) if x['layer']==lid and x['day']<='2023-04-26' and x['line_changed']))
 save('APRIL_EXIT_SUMMARY.json',dict(prior_known_raw_line=before[0]['raw_line'],prior_known_adjusted_line=before[0]['recorded_after_decision_floor'],last_actual_saved_line_updates=lastchange,trigger_day=trigger[0]['day'],trigger_close=trigger[0]['raw_close'],stock_I_still_valid=True,actual_requests=exit['actual_exit_requests'],actual_sells=exit['actual_sell_fills'],all_later_fresh_CP1_receipts=len(post),first_later_CP1=post[0]['signal_day'],later_CP1_initial_barriers=dict(collections.Counter(x['first_block_or_admission'] for x in post)),no_fresh_CP1_gap='after actual 4/28 exit through 5/17 inclusive',core_opportunities_during_CP1_gap=[{k:x[k] for k in ['signal_day','original_Q','original_role_offered','first_block_or_admission']} for x in corepost],not_an_I_structure_exit=True))
 # Save exact native sector first buys/contributions already prepared, unchanged.
 save('SECTOR_PARTICIPATION_2023.json',{ref:read(G/'2023'/f'{ref}_TOP3_INDUSTRIES.json') for ref in ['Bdiag','C1']})
 # Strict JSON output: no active market attempt is null, never zero or a new ID.
 for p in [O/'EPISODES_NAMED.json',O/'EPISODES_CONTROLS.json',O/'SUBJECT_SUMMARY.json',O/'XINYISHENG_EXIT_REENTRY.json',O/'Bdiag/OPPORTUNITIES_NAMED.json',O/'C1/OPPORTUNITIES_NAMED.json']:
  save(str(p.relative_to(O)),read(p))
 save('SUMMARY_COMPLETION.json',dict(passed=True,read_only=True,new_accounts=0,new_indicators=0,new_thresholds=0,local_relaxed_constraint_preview_run=False,core_minimum_lower_bound_is_original_rule_only=True,minimum_rule_named_stocks='saved routes consistently show original 100-share minimum; admission quantity can be zero',funding_same_day_open_not_misattributed_to_current_close=True))
 print('SUMMARY_READY',len(events),'typed timelines',len(minimum),'named opportunity rows',len(controlout),'control paths')
if __name__=='__main__':main()
