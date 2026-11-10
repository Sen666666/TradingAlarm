"""Independent original-book/source audit only. Does not construct an account."""
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal as D, getcontext, ROUND_CEILING, ROUND_HALF_UP
import json, gzip, hashlib
import pandas as pd
import numpy as np

getcontext().prec=55
O=Path(__file__).parent
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
E=O.parents[1]
SRC={}; FF={}; RAW={}; Z=D(0)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(s) for s in f] if lines else json.load(f)
def save(n,v):
 with (O/n).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def same(x,y,label): assert abs(D(str(x))-D(str(y)))<D('1e-11'),(label,x,y)
def version(rows,day):
 q=[x for x in rows if x['from']<=day and (x.get('to') is None or day<x['to'])];assert len(q)==1;return q[0]
SM={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
PM=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
RM={r['series_id']:r for r in read(PM)['series']}
rules=read(R/'pvr-act-comparison-20261027/execution-rules-v2.json')
protocol=read(R/'a-share-selection-e0-20261024/inputs-v2/economic-protocol.json')
def facts(sid):
 if sid not in FF:
  p=Path(SM[sid]['refs']['facts']);assert sha(p)==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=sha(p)
  FF[sid]=pd.read_parquet(p,columns=['close','raw_close','factor','segment_id','i_target','i_floor','e0_target','e0_floor'])
 return FF[sid]
def fact(sid,day):
 f=facts(sid);i=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert i>=0
 return f.iloc[i],str(f.index[i].date()),i
def raw(sid):
 if sid not in RAW:
  p=Path(RM[sid]['raw']['path']);assert sha(p)==RM[sid]['raw']['sha256'];SRC[str(p)]=sha(p)
  f=pd.read_parquet(p,columns=['trade_date','open','high','low','volume']).set_index('trade_date');assert f.index.is_unique
  RAW[sid]=f
 return RAW[sid]
def agg(rr):
 return dict(layers=len(rr),cost=sum((D(x['cost']) for x in rr),Z),net=sum((D(x['net']) for x in rr),Z),
  positive=sum((max(Z,D(x['net'])) for x in rr),Z),negative=sum((min(Z,D(x['net'])) for x in rr),Z))
def grouped(rr,key):
 bb=defaultdict(list)
 for r in rr:bb[r[key]].append(r)
 return {k:agg(v) for k,v in sorted(bb.items())}

ALL={}; CHECK={}; I_ROWS={}; BASELINE={}
pairs={'2022_2024':B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024',
       'strong':B/'pvr_pool_feasibility/runs/2025_26'}
for ref,run in pairs.items():
 book=read(run/'pair/B.json.gz',gz=True)
 held=read(E/'entry_exit_scale/holding_exit'/f'{ref}_LAYERS.json')
 hm={x['layer']:x for x in held};buy={t['layer']:t for t in book['trades'] if t['side']=='buy'}
 fills=[x for x in book['audit'] if x['kind']=='fill'];reqs={x['event_id']:x for x in book['audit'] if x['kind']=='exit_request'}
 trades={t['receipt_id']:t for t in book['trades']}
 counters=Counter(); fees=defaultdict(lambda:Z); accr=defaultdict(lambda:Z);paid=defaultdict(lambda:Z); price_rows=[]
 sessions=sorted({x[:10] for x in rules['calendars']['A']});six={x:i for i,x in enumerate(sessions)}
 for a in fills:
  t=trades[a['receipt']['receipt_id']];sid=t['security_id'];day=t['at'][:10];side=t['side'];q=t['shares'];p=D(t['price']);op=D(t['raw_open'])
  f=raw(sid);r=f.loc[pd.Timestamp(day)];same(op,r.open,('raw open',ref,sid,day));same(p,op*(D('1.0005') if side=='buy' else D('.9995')),'slip')
  same(D(t['gross_cny']),q*p,'gross');assert t['at'][11:19]=='09:30:00';assert a['source']==RM[sid]['raw']['sha256']
  assert r.volume>0 and r.high>r.low
  i=f.index.get_loc(pd.Timestamp(day));pv=f.iloc[:i].volume;pv=pv[np.isfinite(pv)&pv.gt(0)].tail(20);assert len(pv)==20
  capacity=int(min(pv.mean()*.01,r.volume));assert q<=capacity
  venue=version(rules['venue_versions'][sid],day)['venue'];sch=version(rules['fee_versions'][venue],day)['schedule'];assert a['fee_schedule']==sch['schedule_id']
  computed={}
  for c in sch['components']:
   if c.get('side','both') not in ['both',side]:continue
   name=c['name'];key=(side,a['order_id'],name);basis=c.get('amount_basis','notional')
   base=q*p if basis=='notional' else D(q) if basis=='shares' else D(q)*D(str(rules['security_metadata'][sid]['par_value']))
   total=max(D(c.get('minimum_local','0')),accr[key]+base*D(c['rate']) if c.get('basis','order')=='order' else base*D(c['rate']))
   if c.get('maximum_local') is not None:total=min(total,D(c['maximum_local']))
   if c.get('rounding_unit') is not None:
    unit=D(c['rounding_unit']);total=(total/unit).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*unit
   v=max(Z,total-paid[key]) if c.get('basis','order')=='order' else total;computed[name]=v
   accr[key]+=base*D(c['rate']);paid[key]+=v;fees[name]+=v
  assert set(computed)==set(a['fee_components'])
  for k,v in computed.items():same(v,a['fee_components'][k],('feecomponent',k))
  same(sum(computed.values(),Z),t['fees_cny'],'totalfees')
  qr=version(rules['quantity_versions'][sid],day)['rule']
  if side=='buy':
   counters['buys']+=1;counters['buy_fill_non_order_lot']+=int(q<qr['buy_minimum'] or (q-qr['buy_minimum'])%qr['buy_step']!=0)
   prev=f.iloc[:i].iloc[-1];counters['open_differs_previous_observed_close_not_computed_here']+=0
  else:
   counters['sells']+=1
   for part in t['parts']:
    lid=part['layer'];b=buy[lid];assert six[day]>six[b['at'][:10]],('T+1',ref,lid)
   req=reqs[a['order_id']];counters['sell_next_native_open']+=int(six[day]-six[req['at'][:10]]==1)
  counters['raw_open_exact']+=1;counters['same_day_positive_volume_and_nonflat']+=1;counters['capacity_within_original_proxy']+=1;counters['fees_exact']+=1
  price_rows.append(dict(receipt_id=t['receipt_id'],sid=sid,at=t['at'],side=side,shares=q,raw_open=op,execution_price=p,
   capacity_proxy=capacity,fee_schedule=sch['schedule_id'],fees=t['fees_cny'],fill_order_id=a['order_id']))
 irows=[]
 # Classify actual I-reason layers at their FIRST I-specific request, while
 # preserving actual executed order creation independently (it can be earlier).
 for x in held:
  if x['actual_exit_class']!='I_structure_exit':continue
  clocks=sorted({z['at'] for z in x['original_exit_request_events'] if z['reason']=='I_structure_exit'})
  assert clocks;at=clocks[0];day=at[:10];r,qd,idx=fact(x['sid'],day);assert qd==day and not bool(r.i_target)
  # Exit-day i_floor is original projector's preserved pre-exit floor. It
  # is not a terminal label and is available at this decision CLOSE.
  ifloor=None if not np.isfinite(r.i_floor) else D(str(r.i_floor));c=D(str(r.close))
  efloor=None if not np.isfinite(r.e0_floor) else D(str(r.e0_floor))
  e0off=not bool(r.e0_target);broken=ifloor is not None and c<=ifloor
  prior=facts(x['sid']).iloc[:idx];known=prior[prior.i_target.eq(True)&prior.i_floor.notna()]
  prev=None if known.empty else known.iloc[-1];same_domain=prev is not None and str(prev.segment_id)==str(r.segment_id)
  priorline=None if not same_domain else D(str(prev.i_floor))
  status='I_floor_broken' if broken else 'E0_structure_off_above_I_floor' if e0off and ifloor is not None else 'source_reset_or_unknown_floor' if ifloor is None else 'unexplained_soft_Ioff'
  z={k:x[k] for k in ['layer','sid','name','action','role','cost','net','opened','closed']}
  z.update(first_I_request_at=at,actual_executed_order_created_at=x['actual_sale_parts'][0]['order_created_at'],quote_day=qd,
   causal_close=c,I_target=False,I_exit_floor=ifloor,I_floor_broken=broken,E0_target=bool(r.e0_target),E0_exit_floor=efloor,
   previous_active_I_floor=priorline,previous_active_I_same_domain=same_domain,hard_boundary_class=status,
   grace_necessary_condition_preserve_I_floor_and_E0=bool(ifloor is not None and c>ifloor and not e0off),
   original_terminal_net_is_label_only=True)
  irows.append(z)
 assert len({x['layer'] for x in irows})==len(irows)
 if ref=='2022_2024':
  views={'full_2022_2024':held,'2022_2023':[x for x in held if x['opened'][:4] in ['2022','2023']],
         'post303':[x for x in held if '2024-10-09'<=x['opened'][:10]<='2024-12-31']}
 else:views={'strong':held}
 summaries={}
 for v,rr in views.items():
  lids={x['layer'] for x in rr};ir=[x for x in irows if x['layer'] in lids]
  summaries[v]=dict(all_layers=agg(rr),original_exit_families=grouped(rr,'actual_exit_class'),
   I_layers=agg(ir),I_hard_boundary_classes=grouped(ir,'hard_boundary_class'),
   grace_necessary_condition=agg([x for x in ir if x['grace_necessary_condition_preserve_I_floor_and_E0']]),
   I_action_groups=grouped(ir,'action'))
 cp=read(run/'checkpoint.json');prov=read(run/'checkpoint.provenance.json');assert cp['sha256']==prov['checkpoint_sha256']
 relevant={p:h for p,h in cp['source_freeze'].items() if p.endswith(('/native_rank.py','/joint_v3.py','/pilot.py','/fast_market.py','/multi_runner.py','/sector_account.py','/engine.py','/policies_g1.py','/policy.py'))}
 srcchecks={p:sha(p)==h for p,h in relevant.items()};assert all(srcchecks.values())
 CHECK[ref]=dict(counters=dict(counters),fee_components=fees,total_fee=sum(fees.values(),Z),original_book_fills=len(fills),
  I_layers=len(irows),unexplained_soft_Ioff=sum(x['hard_boundary_class']=='unexplained_soft_Ioff' for x in irows),
  grace_necessary_condition_count=sum(x['grace_necessary_condition_preserve_I_floor_and_E0'] for x in irows),
  used_source_freeze_relevant_files_exact=srcchecks,new_accounts=0,account_steps=0)
 ALL.update(summaries);I_ROWS[ref]=irows
 save(ref+'_I_EXIT_BOUNDARIES.json',irows);save(ref+'_ORIGINAL_FILL_AUDIT.json',price_rows)
 BASELINE[ref]=dict(run=str(run),checkpoint_at=cp['at'],checkpoint_sha256=cp['sha256'],checkpoint_file_exists=(run/'checkpoint.pkl').exists(),
  baseline_layers=len(held),buy_fills=sum(t['side']=='buy' for t in book['trades']),sell_fills=sum(t['side']=='sell' for t in book['trades']),
  ending_NAV=book['ending_NAV'],ending_cash=book['ending_cash'],trades=hashlib.sha256(json.dumps(book['trades'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
  original_daily=str(run/'pair/daily.jsonl.gz'),original_book=str(run/'pair/B.json.gz'),identity=prov['engine_identity'])

save('ORIGINAL_PATH_SUMMARY.json',ALL);save('VALIDATION.json',dict(status='PASS',checks=CHECK,new_accounts=0,new_account_steps=0,new_policies=0,
 caveat='Necessary checks on original daily-bar research proxy, not historical exchange-rule certification or actual fill feasibility.'))
save('BASELINE_REPRODUCTION_TARGETS.json',BASELINE)
save('PROTOCOL_LIMITS.json',dict(original_protocol_subset={k:protocol[k] for k in ['approved_proxy_ids','participation_rate','daily_execution','sellable_lag_sessions','settlement_lag_sessions','dividend_net_factor','bonus_sellable_lag_sessions','fractional_split_policy','stale_action_mark_policy','limitations']},
 execution='Actual exact-day raw OPEN plus 5bps adverse slip; original planner uses last-known CLOSE only for decision quote/mark, never substitutes it as original execution OPEN.',
 I='G1_I exits only E0 shadow off or close<=old I floor; grade/cold/acute do not independently switch I off. Core has no separate CP branch. Ioff is structural protection.',
 grace='Do not defer broken I floor or invalid E0 shadow. The necessary condition Ioff & C>I_exit_floor & E0_on has the original-path coverage reported here. Mobile old CP floor remains separately hard even when Ioff branch would otherwise bypass its test.',
 stats='Original per-layer future net remains explicitly terminal diagnostic label. No counterfactual account value or avoidable-loss assertion.',
 no_new_account=True))
SRC[str(Path(__file__).resolve())]=sha(__file__)
save('SOURCE_SHA256.json',SRC)
save('DELIVERABLE_SHA256.json',{str(p):sha(p) for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
print(json.dumps(dict(validation=CHECK,summary=ALL),default=str,ensure_ascii=False))
