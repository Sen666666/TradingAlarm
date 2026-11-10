from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import json,hashlib,csv
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');O=ROOT/'mainline_seed_entry_diagnostic_v1';R=ROOT/'mainline_m7_cash_batch_design_v6/once_20260630'
def rd(p):return json.loads(p.read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
rows=rd(O/'FILLED_SEED_CLASSIFICATION.json');orders=rd(R/'ORDERS.json');attempts=rd(R/'ATTEMPTS.json');eq=rd(R/'EQUITY_EVENTS.json');sd={(r['day'],r['sector51']):r for r in rd(R/'SECTOR_DAILY.json')}
ledger=rd(R/'DAY_LEDGER.json');days=[x['day'] for x in ledger];hashes=rd(O/'SOURCE_HASHES.json')
m={x['symbol']:x for x in rd(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))}
blocked=[r for r in rows if r['G2'].startswith('BLOCK')]
focus_ids={'000158.SZ','002261.SZ','300085.SZ','688503.SH','601601.SH','600637.SH','300475.SZ','300364.SZ','301086.SZ'}
focus=[r for r in blocked if r['sid'] in focus_ids]
ids=sorted({r['sid'] for r in focus})
Q=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
def checked_parquet(p,columns=None):
 hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return pd.read_parquet(p,columns=columns)
known=checked_parquet(Q/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet',ids)
right=checked_parquet(Q/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet',ids)
ps=checked_parquet(Q/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',['sid','day','state']);ps=ps[ps.sid.isin(ids)].pivot(index='day',columns='sid',values='state').reindex(index=known.index,columns=ids)
known &= ps.ge(0)
frames={};facts={}
for sid in ids:
 mm=m[sid]
 for kind,p in [('raw',next(p for p in mm['source_sha256'] if p.endswith('/signal.parquet'))),('facts',mm['refs']['facts'])]:
  h=hashlib.sha256(Path(p).read_bytes()).hexdigest();assert h=={**mm['source_sha256'],**mm['output_sha256']}[p];hashes[p]=h
  z=pd.read_parquet(p).loc[:'2025-01-20'];(frames if kind=='raw' else facts)[sid]=z
def lin(z):return tuple(z[c] for c in ['source_kind','source_path','segment_id'])
admitted={(x['sid'],x['ex_date']) for x in rd(R/'EVENT_ADMISSION.json')}
seed={x['round_id']:x for x in orders if x['side']=='BUY_SEED'}
wait=[]
for r in focus:
 sid=r['sid'];raw=frames[sid];fact=facts[sid];sig=r['signal_day'];start=r['plan_day'];base=raw.loc[pd.Timestamp(start)];origin=lin(base);factor=base.adjustment_factor
 initial_floor=fact.loc[sig:start,'i_floor'].max();floor=initial_floor;H=r['G2_anchor'];log=[];cancel=None;ready=None;pause=[]
 for ds in [d for d in days if d>=start]:
  dt=pd.Timestamp(ds);z=raw.loc[dt];f=fact.loc[dt];sec=sd[(ds,r['sector51'])];stock=1 if bool(known.at[dt,sid]) and bool(right.at[dt,sid]) else 0 if bool(known.at[dt,sid]) else -1
  why=None
  if lin(z)!=origin:why='CANCEL_SOURCE_CHANGED'
  elif abs(float(z.adjustment_factor)/float(factor)-1)>1e-11 and (sid,ds) not in admitted:why='PAUSE_UNADMITTED_FACTOR_BRIDGE'
  if f.i_target==0:why='CANCEL_I_FALSE'
  elif sec['state']==0:why='CANCEL_SECTOR_FALSE'
  elif stock==0:why='CANCEL_STOCK_FALSE'
  if f.i_target==1 and pd.notna(f.i_floor) and f.i_floor>0:floor=max(floor,float(f.i_floor))
  C=float(z.raw_close*z.adjustment_factor);valid=bool(z.observed_bar and z.price_eligible and z.volume_eligible and not z.source_invalid and not z.synthetic_event_bar)
  if valid and C<=floor:why='CANCEL_I_FLOOR_BREACH'
  if why is None and (sec['state']==-1 or stock==-1 or f.i_target not in [0,1] or not valid):why='PAUSE_UNKNOWN'
  gate=valid and C>H
  log.append(dict(day=ds,stock_state=stock,sector_state=sec['state'],M=sec['M'],I_state=int(f.i_target) if pd.notna(f.i_target) else None,I_floor=floor,close=C,H=H,gate_pass=gate,status=why or ('STRUCTURE_READY' if gate else 'STRUCTURE_WAIT')))
  if why and why.startswith('CANCEL'):cancel=ds;break
  if why and why.startswith('PAUSE'):pause.append(ds);continue
  if gate:ready=ds;break
  factor=z.adjustment_factor
 readyrow=log[-1];nextday=None;openadj=None;openfloor=None;costchange=None
 if ready:
  dates=raw.index[raw.index>pd.Timestamp(ready)]
  if len(dates):
   nd=dates[0];nz=raw.loc[nd];nextday=str(nd.date());openadj=float(nz.raw_open*nz.adjustment_factor);openfloor=openadj>floor
   original=raw.loc[pd.Timestamp(r['seed_day'])];oldop=float(original.raw_open*original.adjustment_factor);costchange=(openadj/oldop-1)*100
 wait.append(dict(round_id=r['round_id'],name=r['name'],sid=sid,baseline_plan=start,baseline_seed=r['seed_day'],original_signal=sig,original_nav=seed[r['round_id']]['frozen_attempt_NAV'],original_budget_2pct=str(D(seed[r['round_id']]['frozen_attempt_NAV'])*D('.02')),initial_wait_floor=initial_floor,failed_high=H,baseline_round_net=r['net'],first_daily_gate_and_structure_ready=ready,cancel_day=cancel,cancel_or_last_reason=readyrow['status'],next_open_day=nextday,next_adjusted_open=openadj,next_open_above_current_I_floor=openfloor,next_open_vs_original_open_pct=costchange,pause_days=pause,daily_path=log,execution_limit='Gate and existing I/sector/stock/source checks only. Size, dated fee/lot, price-limit, reserve, event identity/spend and actual funding not replayed. Not a filled trade.'))
# Exact known-at-exit check, and disaggregate acquisition/structural reasons.
by=defaultdict(list);be=defaultdict(list)
for x in orders:by[x['round_id']].append(x)
for x in eq:
 if x.get('round_id') and x['event']=='ACCRUE_NET80':be[x['round_id']].append(x)
qa=[];reason=[]
for a in attempts:
 if not a.get('exit_day') or a['final_qty']:continue
 os=by[a['id']];es=be[a['id']];net=sum((D(o['cash_delta']) for o in os if o['day']<=a['exit_day']),D(0))+sum((D(e['receivable_delta']) for e in es if e['day']<=a['exit_day']),D(0))
 assert net==D(a['marked_net_pnl'])
 if net>=0:continue
 last=next(x for x in reversed(os) if x['side'].startswith('SELL'))
 why=last['reason'];kind='CAPITAL_RELOCATION' if why in ['CURRENT_NON_MAINLINE_SEED_RETIREMENT','NON_MAINLINE_EXPANSION','MAINLINE_EXPANSION_SURPLUS'] else 'I_CP_OR_SECTOR_INVALIDATION'
 reason.append(dict(round_id=a['id'],sid=a['sid'],exit_day=a['exit_day'],last_exit_reason=why,reason_class=kind,known_at_exit_net=net,full_round_net=a['marked_net_pnl']))
lossmap={x['round_id']:x for x in reason}
affected=[]
for r in blocked:
 anchor=[lossmap[x] for x in r['G2_anchor_rounds']]
 affected.append(dict(round_id=r['round_id'],sid=r['sid'],name=r['name'],seed_day=r['seed_day'],net=r['net'],anchor_reason_classes=sorted(set(x['reason_class'] for x in anchor)),anchor_reasons=sorted(set(x['last_exit_reason'] for x in anchor)),anchors=anchor))
startup=[]
for d in ['2024-09-23','2024-09-24','2024-09-25','2024-09-26','2024-09-27','2024-09-30']:
 for phase in ['EVENT','RESIDUAL','MATURE']:
  rr=[x for x in rows if x['seed_day']==d and x['phase']==phase]
  startup.append(dict(actual_open=d,phase=phase,plan_closes=sorted(set(x['plan_day'] for x in rr)),rounds=len(rr),all_in=sum((D(x['seed_cost']) for x in rr),D(0)),G1_block=sum(x['G1'].startswith('BLOCK') for x in rr),G2_block=sum(x['G2'].startswith('BLOCK') for x in rr),G2_blocked_names=[x['name'] for x in rr if x['G2'].startswith('BLOCK')]))
save('WAIT_TIMING_FOCUS',wait);save('LOSS_REASON_CLASSIFICATION',reason);save('BLOCKED_ANCHOR_REASONS',affected);save('STARTUP_ACTUAL_OPEN_BY_PHASE',startup)
save('OBSERVABILITY_QA',dict(closed_rounds_verified=sum(bool(a.get('exit_day')) and not a['final_qty'] for a in attempts),known_at_exit_vs_final_net_mismatches=0,loss_rounds=len(reason),loss_reason_counts=dict(Counter(x['last_exit_reason'] for x in reason)),reason_class_counts=dict(Counter(x['reason_class'] for x in reason)),notes=['Known-at-exit net uses executed cashflows through exit day plus ACCRUE_NET80 entitlements already confirmed by then, never later cash receipts or facts.','A hypothetical future accounting correction must be recorded at discovery time; it must not rewrite historical admission decisions. G2 is not recommended for implementation.']))
save('SOURCE_HASHES_WITH_TIMING',hashes)
print(json.dumps(wait,ensure_ascii=False,default=str))
