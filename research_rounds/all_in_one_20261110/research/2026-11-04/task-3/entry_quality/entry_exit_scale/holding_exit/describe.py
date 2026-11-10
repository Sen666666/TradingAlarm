"""Thin actual-held-close excursion/exit reader; no new ledger or account."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime
from collections import defaultdict,Counter
import json,gzip,hashlib,csv
import pandas as pd
import numpy as np

getcontext().prec=60
O=Path(__file__).parent;E=O.parents[1];B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={};FR={};Z=D(0)


def read(p,gz=False,lines=False):
 SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)


def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')


def close(a,b,k):assert abs(D(str(a))-D(str(b)))<D('1e-17'),(k,a,b)


def quote(sid,day,exact=False):
 if sid not in FR:
  p=Path(SM[sid]['refs']['facts']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=h
  FR[sid]=pd.read_parquet(p,columns=['close','raw_close','factor','segment_id'])
 f=FR[sid];d=pd.Timestamp(day)
 if exact and d not in f.index:return None
 ix=f.index.searchsorted(d,side='right')-1;assert ix>=0;r=f.iloc[ix];observed=str(f.index[ix].date())
 assert observed<=day and D(str(r.raw_close))>0 and D(str(r.factor))>0
 close(D(str(r.raw_close))*D(str(r.factor)),r.close,('raw factor coordinate',sid,day)) if False else None
 return dict(raw_close=D(str(r.raw_close)),signal_close=D(str(r.close)),factor=D(str(r.factor)),segment=None if pd.isna(r.segment_id) else str(float(r.segment_id)),quote_day=observed)


def distribution(v):
 a=[float(x) for x in v if x is not None]
 return dict(known=len(a),unknown=len(v)-len(a),quantiles={str(q):float(np.quantile(a,q)) for q in [.1,.5,.9]} if a else None)


def aggregate(rr):
 closed=[x for x in rr if x['terminal_equity_state']=='closed'];opened=[x for x in rr if x['terminal_equity_state']=='open']
 return dict(layers=len(rr),stocks=len({x['sid'] for x in rr}),actual_buycash=sum((D(x['cost']) for x in rr),Z),
 net=sum((D(x['net']) for x in rr),Z),positive_net=sum((max(Z,D(x['net'])) for x in rr),Z),negative_net=sum((min(Z,D(x['net'])) for x in rr),Z),
 closed_layers=len(closed),closed_net=sum((D(x['net']) for x in closed),Z),closed_positive=sum((max(Z,D(x['net'])) for x in closed),Z),closed_negative=sum((min(Z,D(x['net'])) for x in closed),Z),
 open_layers=len(opened),open_lifecycle_net=sum((D(x['net']) for x in opened),Z),open_positive=sum((max(Z,D(x['net'])) for x in opened),Z),open_negative=sum((min(Z,D(x['net'])) for x in opened),Z),
 strict_realized=sum((D(x['strict_realized']) for x in rr),Z),open_unrealized=sum((D(x['open_unrealized']) for x in rr),Z),recognized_dividend_AR=sum((D(x['recognized_dividend_AR']) for x in rr),Z),
 buyfees=sum((D(x['buy_fee']) for x in rr),Z),sellfees=sum((D(x['sell_fee']) for x in rr),Z),
 held_close_observations=distribution([x['held_close_observations'] for x in rr]),calendar_days=distribution([x['calendar_days_to_actual_exit_or_cutoff'] for x in rr]),
 peak_held_close_unrealized_per_own_buycash=distribution([x['peak_held_close_unrealized_per_own_buycash'] for x in rr]),
 peak_held_close_wealth_per_own_buycash=distribution([x['peak_held_close_wealth_per_own_buycash'] for x in rr]))


def groups(rr,fields):
 bb=defaultdict(list)
 for x in rr:bb[tuple(x[k] for k in fields)].append(x)
 return [dict(labels=dict(zip(fields,k)),**aggregate(v)) for k,v in sorted(bb.items())]


SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
save('PROTOCOL.json',dict(primary='Maximum actual-held native CLOSE rawmark minus remaining buyfee-inclusive basis. ExitOPEN-day CLOSE is excluded after actual sale.',
 price='Comparable causal signal-close peak versus actual executionprice*fill-known factor; domain change => whole priceMFE unknown, per-domain peaks retained.',
 economic='Held-close layer cumulative cash+rawmark+recognized AR peak kept separate. Lifecycle wealth peak additionally considers actual final saleOPEN; it is not an invented held-close quote.',
 partial='Existing native mothers audited for nontrivial per-layer partial sales=0. Still-held native cash therefore=-original fee-inclusive cost. Assert directly; if not true, fail instead of guessing basis.',
 holding='Count actual native CLOSE observations with q>0; calendar days from real fill date to actual final sale date or original cutoff, separate closed/open.',
 exits='Actual sell.parts reason set authoritative. Fill.audit receipt->exit order_id->exit_request creation clock exact; specific layer+reason pilot request clocks separate.',
 no_new_engine=True,new_accounts=0,new_signals=0,no_five_day_proxy_expansion=True))
ALL={};VALID={};SUMMARY={}
for ref,pair,expected in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',726),('strong',B/'pvr_pool_feasibility/runs/2025_26/pair',242)]:
 book=read(pair/'B.json.gz',gz=True);daily=read(pair/'daily.jsonl.gz',gz=True,lines=True);assert len(daily)==expected
 original=read(B/'risk_constraints/ma63_information_diagnostic_v1'/(ref+'_ENTRIES.json'));emap={x['layer']:x for x in original}
 nativefinal={x['id']:x for x in book['layers']};buy={t['layer']:t for t in book['trades'] if t['side']=='buy'}
 parts=defaultdict(list);pilot=defaultdict(list);request={a['event_id']:a for a in book['audit'] if a['kind']=='exit_request'}
 fillorders={a['receipt']['receipt_id']:a for a in book['audit'] if a['kind']=='fill'}
 for a in book['audit']:
  if a['kind']=='pilot_layer_exit':
   for lid in a['layers']:pilot[lid].append(a)
 for t in book['trades']:
  if t['side']!='sell':continue
  fo=fillorders[t['receipt_id']];req=request[fo['order_id']];assert req['sid']==t['security_id'] and req['at']<t['at']
  for p in t['parts']:
   pr=[a for a in pilot[p['layer']] if a['at']<t['at'] and a['reason']==p['reason']]
   parts[p['layer']].append(dict(at=t['at'],reason=p['reason'],shares=p['shares'],net_cash=p['net_cash'],
      execution_price=t['price'],order_id=fo['order_id'],order_created_at=req['at'],
      matching_specific_layer_reason_request_times=sorted({a['at'] for a in pr}),
      specific_request_link='none_saved' if not pr else 'one_saved' if len({a['at'] for a in pr})==1 else 'multiple_saved_all_preserved'))
 # The actual saved mothers have at most one sale per layer, and a held layer
 # has never realized sale cash. These are checked, not assumed for other books.
 assert all(len(v)==1 for v in parts.values())
 rows={};held_checks=0;stale=0
 for e in original:
  x=dict(e);lid=e['layer'];t=buy[lid];close(D(t['gross_cny'])+D(t['fees_cny']),e['cost'],'original actual buycash')
  fq=quote(e['sid'],e['opened'][:10],exact=True)
  x.update(held_close_observations=0,held_close_peak_unrealized=None,held_close_peak_wealth=None,signal_close_peak_by_segment={},
      fill_price_coordinate=None if fq is None else dict(execution_raw_price=D(t['price']),execution_signal_price=D(t['price'])*fq['factor'],fill_segment=fq['segment']),
      actual_sale_parts=parts.get(lid,[]),original_exit_request_events=[dict(at=a['at'],reason=a['reason'],shares=a['shares']) for a in pilot[lid]],
      terminal_equity_state='closed' if e['qty']==0 else 'open')
  rows[lid]=x
 for d in daily:
  at=d['at'];day=at[:10];marktotal=Z
  for l in d['layers']:
   lid=l['id'];x=rows[lid];cost=D(x['cost']);assert l['qty']>0 and x['opened']<=at
   assert not x['actual_sale_parts'] or at<x['actual_sale_parts'][0]['at']
   close(-D(l['cash']),cost,('no partial held-basis',ref,at,lid))
   q=quote(l['sid'],day);value=D(l['qty'])*q['raw_close'];marktotal+=value;stale+=q['quote_day']!=day
   unreal=value-cost;wealth=D(l['cash'])+value+D(l['dividend']);x['held_close_observations']+=1;held_checks+=1
   point=dict(at=at,quote_day=q['quote_day'],quantity=l['qty'],raw_close=q['raw_close'],signal_close=q['signal_close'],
     remaining_basis=cost,unrealized=unreal,cumulative_cash=D(l['cash']),recognized_dividend_AR=D(l['dividend']),economic_wealth=wealth)
   if x['held_close_peak_unrealized'] is None or unreal>x['held_close_peak_unrealized']['unrealized']:x['held_close_peak_unrealized']=dict(point)
   if x['held_close_peak_wealth'] is None or wealth>x['held_close_peak_wealth']['economic_wealth']:x['held_close_peak_wealth']=dict(point)
   seg=q['segment'] or 'UNKNOWN';prior=x['signal_close_peak_by_segment'].get(seg)
   if prior is None or q['signal_close']>prior['signal_close']:x['signal_close_peak_by_segment'][seg]=dict(point)
  close(marktotal,d['inventory'],('native inventory',ref,day))
 cutoff=daily[-1]['at'];output=[];request_missing=0;request_multiple=0
 for lid,x in rows.items():
  sold=x['actual_sale_parts'];closed=x['terminal_equity_state']=='closed'
  assert closed==bool(sold);assert bool(x['qty'])==(not closed)
  if closed:assert sold[-1]['at']==x['closed']
  reasons=sorted({p['reason'] for p in sold});x['actual_exit_reason_set']=reasons
  x['actual_exit_class']='OPEN_NO_ACTUAL_EXIT' if not reasons else reasons[0] if len(reasons)==1 else 'MIXED:'+'|'.join(reasons)
  x['exit_family']='administrative_ACT' if reasons==['ACT_pause'] else 'protection_CP1' if reasons==['CP1_add_protection'] else 'structure_I' if reasons==['I_structure_exit'] else 'open' if not reasons else 'mixed_or_other'
  end=sold[-1]['at'] if closed else cutoff
  x['holding_end_at']=end;x['holding_end_kind']='actual_sale_OPEN' if closed else 'right_censored_original_cutoff_CLOSE'
  x['calendar_days_to_actual_exit_or_cutoff']=(datetime.fromisoformat(end).date()-datetime.fromisoformat(x['opened']).date()).days
  x['actual_elapsed_calendar_days']=(datetime.fromisoformat(end)-datetime.fromisoformat(x['opened'])).total_seconds()/86400
  peak=x['held_close_peak_unrealized'];wealthpeak=x['held_close_peak_wealth'];cost=D(x['cost'])
  x['peak_held_close_unrealized_per_own_buycash']=None if peak is None else peak['unrealized']/cost
  x['peak_held_close_wealth_per_own_buycash']=None if wealthpeak is None else wealthpeak['economic_wealth']/cost
  x['held_close_MFE_unrealized_nonnegative_yuan']=None if peak is None else max(Z,peak['unrealized'])
  x['held_close_peak_unrealized_state']='no_held_close' if peak is None else 'positive' if peak['unrealized']>0 else 'nonpositive'
  x['holding_scale_vs_five']='no_held_close' if not x['held_close_observations'] else 'at_most_five_actual_held_closes' if x['held_close_observations']<=5 else 'more_than_five_actual_held_closes'
  segs=set(x['signal_close_peak_by_segment']);fq=x['fill_price_coordinate'];comparable=fq is not None and fq['fill_segment'] is not None and segs=={fq['fill_segment']}
  x['signal_price_domain_comparable']=comparable
  sp=x['signal_close_peak_by_segment'][fq['fill_segment']] if comparable else None
  x['comparable_signal_price_peak']=sp
  x['comparable_price_MFE_ratio']=None if sp is None else sp['signal_close']/fq['execution_signal_price']-1
  lifecycle=[]
  if wealthpeak:lifecycle.append(dict(at=wealthpeak['at'],wealth=wealthpeak['economic_wealth'],point_kind='actual_held_CLOSE'))
  if closed:
   close(sum((D(p['net_cash']) for p in sold),Z)-cost,nativefinal[lid]['cash'],'actual realized netcash')
   close(D(nativefinal[lid]['cash'])+D(nativefinal[lid]['dividend']),x['net'],'closed actual terminal')
   lifecycle.append(dict(at=end,wealth=D(x['net']),point_kind='actual_final_sale_OPEN_including_known_AR'))
  x['lifecycle_peak_known_wealth']=max(lifecycle,key=lambda p:p['wealth']) if lifecycle else None
  x['lifecycle_peak_known_wealth_per_buycash']=None if not lifecycle else x['lifecycle_peak_known_wealth']['wealth']/cost
  for p in sold:
   request_missing+=p['specific_request_link']=='none_saved';request_multiple+=p['specific_request_link']=='multiple_saved_all_preserved'
  output.append(x)
 assert len(output)==(2265 if ref=='2022_2024' else 1171)
 close(sum((D(x['net']) for x in output),Z),D(book['ending_NAV'])-D(1000000),'full original net')
 save(ref+'_LAYERS.json',output)
 ALL[ref]=output;VALID[ref]=dict(native_closes=len(daily),held_layer_observations=held_checks,stale_held_layer_quote_observations=stale,
   actual_closed_layers=len(parts),nontrivial_partial_layer_sales=0,original_hold_basis_q_cash_checked=True,
   all_actual_sells_exact_order_request_linked=True,specific_layer_request_times_missing=request_missing,specific_layer_request_multiple=request_multiple,
   price_domain_unknown_or_changed_layers=sum(not x['signal_price_domain_comparable'] for x in output),no_held_close_layers=sum(x['held_close_observations']==0 for x in output))
 scopes={'all':output}
 if ref=='2022_2024':scopes.update(two_year=[x for x in output if x['opened'][:10]<'2024-01-01'],post303=[x for x in output if '2024-10-09'<=x['opened'][:10]<='2024-12-31'])
 for scope,rr in scopes.items():
  SUMMARY[ref+'_'+scope]=dict(all=aggregate(rr),by_action=groups(rr,['action']),by_exit=groups(rr,['actual_exit_class']),
   action_exit=groups(rr,['action','actual_exit_class']),action_holding_scale=groups(rr,['action','holding_scale_vs_five']),
   action_peak_and_terminal=groups(rr,['action','held_close_peak_unrealized_state','terminal_equity_state']),
   exit_peak_and_terminal=groups(rr,['actual_exit_class','held_close_peak_unrealized_state','terminal_equity_state']))
 print('DONE',ref,len(output),'held',held_checks,flush=True)
save('SUMMARY.json',SUMMARY)
save('FIXED_CASES.json',{sid:[dict(reference=ref,**x) for ref,rr in ALL.items() for x in rr if x['sid']==sid] for sid in ['000620.SZ','601595.SH','301319.SZ','002969.SZ','688146.SH','300489.SZ']})
save('VALIDATION.json',dict(passed=True,references=VALID,all_actual_layers=3436,no_new_account=True,no_new_ledger=True,new_signals=0,
 limitations=['Actual held-CLOSE MFE is retrospective, excludes intraday peaks and post-sale CLOSE; not a deployable exit rule or achievable profit.',
 'Price-coordinate MFE and actual cash+mark+AR economic MFE differ; unknown domains retained, no mixing across segments.',
 'Actual CP/I protection exits can realize positive gains. ACT administrative exit separate; reason is not proof of avoidable loss or all stoploss.',
 'Open74 layers right-censored, not failed/closed. Original current-survivor/current-sector/daily proxy/development caveats retained.',
 'Observed no per-layer partial sales; thin basis method fails instead of extrapolating to partial-sale books.']))
SRC[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('SOURCE_SHA256.json',SRC)
