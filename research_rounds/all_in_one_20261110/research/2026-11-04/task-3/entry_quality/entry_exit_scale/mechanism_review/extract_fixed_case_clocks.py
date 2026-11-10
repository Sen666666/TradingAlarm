"""Six pre-existing/requested cases: original request/fill and cached CP clocks.
No line-origin tracker or alternative exit.
"""
from pathlib import Path
from collections import defaultdict
import gzip,json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={}
CASES=['000620.SZ','600415.SH','601595.SH','002969.SZ','688146.SH','301319.SZ']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def gz(p,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f] if lines else json.load(f)
def val(x):return None if pd.isna(x) else x.item() if hasattr(x,'item') else x
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};out={}
roots={'2022_2024':B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024','strong':B/'pvr_pool_feasibility/runs/2025_26'}
for ref,root in roots.items():
 e=read(O/(ref+'_ACTUAL_ENTRY_SCALE_JOIN.json'));book=gz(root/'pair/B.json.gz');daily=gz(root/'pair/daily.jsonl.gz',True);dm={x['at'][:10]:x for x in daily};native={x['id']:x for x in book['layers']};allrequests=[x for x in book['audit'] if x['kind']=='pilot_layer_exit']
 for sid in CASES:
  entries=[x for x in e if x['sid']==sid]
  if not entries:continue
  m=sm[sid];fp=Path(m['refs']['facts']);cp=Path(m['refs']['CP1']);assert sha(fp)==m['output_sha256'][str(fp)] and sha(cp)==m['output_sha256'][str(cp)];SRC[str(fp)]=sha(fp);SRC[str(cp)]=sha(cp)
  f=pd.read_parquet(fp,columns=['close','raw_close','factor','i_target','i_floor','segment_id']);z=pd.read_parquet(cp,columns=['receipt','candidate','scale','next_scale','z','s','r','m','phase','reset_reason','frontier','anchor','credit','displacement'])
  requests=[x for x in allrequests if x['sid']==sid];trades=[x for x in book['trades'] if x['security_id']==sid];buy_by_layer={x['layer']:x for x in trades if x['side']=='buy'}
  lo=min(x['decision_at'][:10] for x in entries);hi=daily[-1]['at'][:10];trace=[]
  for d,q in f.loc[lo:hi].iterrows():
   day=str(d.date());c=z.loc[d];rs=[x for x in requests if x['at'][:10]==day];ts=[x for x in trades if x['at'][:10]==day];es=[x for x in entries if x['decision_at'][:10]==day]
   if not (rs or ts or es or bool(c.receipt) or (pd.notna(c.reset_reason) and c.reset_reason not in ['E0_invalid','unprepared'])):continue
   detail=[];seen_request_layer=set()
   for r in rs:
    dd=dm.get(day);live={} if dd is None else {x['id']:x for x in dd['layers']}
    for lid in r['layers']:
     requestkey=(r['at'],lid,r['reason'])
     if requestkey in seen_request_layer:continue
     seen_request_layer.add(requestkey)
     x=live.get(lid);entry=next(a for a in entries if a['layer']==lid);buy=buy_by_layer[lid];after=f.loc[buy['at'][:10]:day];origin=entry['order_floor_unique_semantic_origin_day']
     effective=None if x is None else x['last_core_line'] if x['role']=='core' else x['floor'];same=None if effective is None else abs(float(effective)-float(entry['original_order_floor_causal']))<1e-9
     later_cp=z.loc[buy['at'][:10]:day];before=later_cp.iloc[:-1];nextbuys=[a for a in entries if a['decision_at']>r['at']];nextbuy=min(nextbuys,key=lambda a:a['decision_at']) if nextbuys else None
     detail.append(dict(local_layer=lid,role=entry['role'],reason=r['reason'],request_at=r['at'],actual_fill_at=buy['at'],effective_floor_causal_at_request=effective,initial_order_floor_causal=entry['original_order_floor_causal'],request_line_equals_initial=same,
      request_floor_origin='unchanged_initial_CP1_receipt' if same and origin else 'unknown_I_or_later_ratchet_source_not_reconstructed',known_initial_CP1_origin_if_unchanged=origin if same else None,
      original_valid_holding_closes_through_request=len(after),first_holding_close_request=len(after)==1,
      postfill_new_CP1_before_request_days=[str(x.date()) for x in before.index[before.receipt]],CP1_on_request_day=bool(c.receipt),reset_reason_on_request_day=val(c.reset_reason),
      resets_since_fill=[dict(day=str(t.date()),reason=str(rr.reset_reason)) for t,rr in later_cp.iterrows() if pd.notna(rr.reset_reason) and rr.reset_reason not in ['receipt_consumed','E0_invalid','unprepared']],
      later_actual_sell_parts_for_same_layer_not_unique_request_attribution=[dict(at=t['at'],actual_raw_price=t['price'],parts=[p for p in t['parts'] if p['layer']==lid]) for t in trades if t['side']=='sell' and t['at']>=r['at'] and any(p['layer']==lid for p in t['parts'])],
      next_same_stock_actual_entry_decision=None if nextbuy is None else {k:nextbuy[k] for k in ['layer','decision_at','actual_fill_at','role','action','receipt','original_cost','original_net','initial_order_floor_binding','CP1_used_scale','CP1_current_z','CP1_scale_frozen_at']}))
   trace.append(dict(day=day,causal_close=val(q.close),raw_close=val(q.raw_close),causal_factor=val(q.factor),I_target=val(q.i_target),I_floor_causal=val(q.i_floor),source_segment=val(q.segment_id),CP1_cached={k:val(c[k]) for k in z.columns},actual_native_requests=rs,request_layer_details=detail,request_details_dedup='one_at_layer_reason; raw pilot list can repeat earlier layer while same exit order is extended, not multiple independent new submissions',actual_native_trades=ts,actual_entry_decisions=es))
  out[ref+'|'+sid]=dict(case_selection='pre-existing failure/recovery cases plus explicitly requested嘉美/中船; all actual entries and requests retained, no outcome-based new selection',entries=entries,event_clock_rows=trace,financial_status='Amounts are original saved entries; request is not fill, zero new financial result.')
with (O/'FIXED_CASE_ORIGINAL_CLOCKS.json').open('x') as h:json.dump(out,h,ensure_ascii=False,indent=2,allow_nan=False)
with (O/'FIXED_CASE_CLOCK_SOURCES.json').open('x') as h:json.dump(dict(sources=SRC,script_sha256=sha(__file__),new_accounts=0,new_signals=0,new_line_tracker=0),h,ensure_ascii=False,indent=2)
print('SAVED',len(out),'case windows',sum(len(x['entries']) for x in out.values()),'all actual entry layers')
