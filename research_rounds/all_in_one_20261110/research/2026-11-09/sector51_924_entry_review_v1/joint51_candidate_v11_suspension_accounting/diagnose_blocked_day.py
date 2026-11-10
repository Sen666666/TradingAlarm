"""Read-only all-target diagnosis of a rolled-back day; never executes an account."""
from pathlib import Path
from decimal import Decimal as D
import json,sys
import pandas as pd
P=Path(__file__).resolve().parent.parent;O=P/sys.argv[1];R=O/'full_20241031_once';read=lambda p:json.loads(p.read_text());blocked=read(R/'UNCERTIFIED_DAY.json');assert blocked
when=blocked['day'];dt=pd.Timestamp(when);attempts={x['sid']:x for x in read(R/'ATTEMPTS.json') if x['final_qty']>0};pending={x['sid']:x for x in read(R/'PENDING_AT_END.json')};targets=sorted(set(attempts)|set(pending));m={x['symbol']:x for x in read(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))};sm=pd.read_csv(O/'CLASSIFICATION_ALL1709.csv').set_index('symbol').sector51.to_dict();base=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1');events=read(base/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json')+read(P/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json')
if (O/'ADDITIONAL_REVIEWED_EVENTS.json').exists():events+=read(O/'ADDITIONAL_REVIEWED_EVENTS.json')
em={(x['sid'],x['ex_date']):x for x in events};rows=[];alltargets=[]
for s in targets:
 a=attempts.get(s) or pending[s];rawp=Path(next(p for p in m[s]['source_sha256'] if p.endswith('/signal.parquet')));raw=pd.read_parquet(rawp);z=raw.loc[dt].to_dict() if dt in raw.index else {};ap=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions')/(s+'.json');acts=[x for x in read(ap)['events'] if x['effective_date']==when];ev=em.get((s,when));issues=[]
 try:
  if not pd.notna(z.get('raw_open')) or D(str(z.get('raw_open')))<=0:issues.append('OPEN_MISSING')
 except Exception:issues.append('OPEN_MISSING')
 if tuple(str(z.get(k)) for k in ['source_kind','source_path','segment_id'])!=tuple(a['origin']):issues.append('SOURCE_CHANGE')
 try:
  f0=D(a['factor']);f1=D(str(z.get('adjustment_factor')))
  if not f1.is_finite() or f1<=0:issues.append('FACTOR_INVALID')
  elif abs(f1/f0-1)>D('1e-11') and ev is None:issues.append('UNADMITTED_FACTOR_CHANGE')
  elif ev is not None and (abs(f0/D(ev['factor_old'])-1)>D('1e-11') or abs(f1/D(ev['factor_new'])-1)>D('1e-11')):issues.append('FACTOR_BRIDGE_MISMATCH')
 except Exception:issues.append('FACTOR_UNCHECKABLE')
 if acts and ev is None:issues.append('UNADMITTED_EQUITY_EVENT')
 pol=next((p for p in read(O/'SUSPENSION_POLICY.json')['policies'] if p['sid']==s and when in p['covered_dates']),None);covered=pol is not None;valuation_note=None
 if covered and not z:
  issues=[x for x in issues if x not in ['OPEN_MISSING','SOURCE_CHANGE','FACTOR_UNCHECKABLE']]
  anchor=raw.loc[pd.Timestamp(pol['mark_source_day'])]
  if tuple(str(anchor[k]) for k in ['source_kind','source_path','segment_id'])!=tuple(a['origin']):issues.append('SUSPENSION_ANCHOR_SOURCE_MISMATCH')
  if D(a['factor'])!=D(pol['factor']):issues.append('SUSPENSION_ANCHOR_FACTOR_MISMATCH')
  if acts or ev:issues.append('SUSPENSION_EQUITY_REQUIRES_SEPARATE_BRIDGE')
  valuation_note='EXPLICIT_NONTRADABLE_STALE_ANCHOR_ONLY_NO_OBSERVED_BRIDGE'
 row=dict(valuation_note=valuation_note,day=when,sid=s,sector51=sm[s],held_qty=attempts[s]['final_qty'] if s in attempts else 0,pending_seed=s in pending,issues=issues,actions=acts,action_path=str(ap),signal_path=str(rawp),existing_fact_cache=[str(base/d/(s+'.json')) for d in ['cash_dividend_source_feasibility_v1/raw','cash_dividend_2024_coverage_v1/raw'] if (base/d/(s+'.json')).exists()]);alltargets.append(row)
 if issues:rows.append(row)
for fn,v in [('BLOCKED_DAY_ALL_TARGETS.json',alltargets),('BLOCKED_DAY_ALL_ISSUES.json',rows)]: (O/fn).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(blocked_day=when,targets=len(targets),issues=len(rows),rows=rows),ensure_ascii=False))
