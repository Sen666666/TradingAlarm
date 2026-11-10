"""Append only Dec8-Jan14 original cached rows into a SEPARATE full daily file.
Does not import/run the prior reader or change its14-row output.
"""
from pathlib import Path
import hashlib,json,gzip,math
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');OUT=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={};SID='000547.SZ'
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 SRC[str(p)]=h.hexdigest();return p
def rj(p):return json.loads(bind(p).read_text())
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,pd.Timestamp):return x.isoformat()
 if isinstance(x,dict):return {k:clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return[clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
original_file=bind(OUT/'DAILY_ORIGINAL_E0_G1_I_CP_AND_LEDGER.json');original_hash=SRC[str(original_file)];old=json.loads(original_file.read_text());old_by={r['day']:r for r in old}
rec=next(r for r in rj(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')if r['symbol']==SID)
def frame(path,expected):p=bind(path);assert SRC[str(p)]==expected;return pd.read_parquet(p)
facts=frame(rec['refs']['facts'],rec['output_sha256'][rec['refs']['facts']]);cp=frame(rec['refs']['CP1'],rec['output_sha256'][rec['refs']['CP1']])
ep=next(p for p in rec['source_sha256']if p.endswith('/events.parquet'));events=frame(ep,rec['source_sha256'][ep]);ip=next(p for p in rec['source_sha256']if p.endswith('/000547.SZ.parquet'));ix=frame(ip,rec['source_sha256'][ip]);receipts=rj(rec['refs']['receipts']);by_receipt={r['confirmed_day']:r for r in receipts}
selected=facts.loc['2025-12-08':'2026-01-14'];dates=[str(t.date())for t in selected.index];wanted=set(dates)
if not len(dates):
 save('FULL_DAILY_APPEND_STATUS.json',dict(status='NOT_SAVED',reason='No original cached observations in exact requested interval; no rows synthesized.'));raise SystemExit(0)
pair=ROOT/'new_price_trend_v1/funding/runs/strong_OFF/pair';book=json.load(gzip.open(bind(pair/'B.json.gz'),'rt'));daily={}
with gzip.open(bind(pair/'daily.jsonl.gz'),'rt')as f:
 for line in f:
  r=json.loads(line);day=r['at'][:10]
  if day in wanted:daily[day]=r
  if day>'2026-01-14':break
ops=[];fund=[]
for file,target in [('opportunities.jsonl.gz',ops),('funding.jsonl.gz',fund)]:
 with gzip.open(bind(pair/file),'rt')as f:
  for line in f:
   r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
   if r.get('sid')==SID and day in wanted:target.append(r)
   if day>'2026-01-14':break
decisions={r['at'][:10]:r for r in book['decisions']if r['at'][:10]in wanted};references=rj(OUT/'KNOWN_REFERENCES_AND_RECLAIM_CLOCKS.json')['references'];rows=[];missing=[]
for day in dates:
 at=pd.Timestamp(day)
 if day not in daily or day not in decisions or at not in cp.index or at not in events.index or at not in ix.index:
  missing.append(dict(day=day,status='NOT_SAVED_COMPLETE_ORIGINAL_ROW'));continue
 f=facts.loc[at];c=cp.loc[at];e=events.loc[at];g=ix.loc[at];d=daily[day];equal={a:bool(f[a]==g[b])for a,b in [('g_grade','grade'),('g_fresh_up','fresh_up'),('g_acute_down','acute_down'),('g_ready','strength_ready')]};assert all(equal.values())
 hist=events.loc[:at];peaks=hist[hist.event.eq(-1)&hist.confirmed_pivot_price.notna()];lows=hist[hist.event.eq(1)&hist.confirmed_pivot_price.notna()]
 def last_known(p):
  if p.empty:return None
  z=p.iloc[-1];return dict(confirmation_day=str(p.index[-1].date()),pivot_day=z.confirmed_pivot_date,pivot_price=z.confirmed_pivot_price,event=z.event)
 previous=[r for r in receipts if r['confirmed_day']<=day]
 rows.append(dict(day=day,decision_clock=decisions[day]['at'],facts=f.to_dict(),original_price_event=e.to_dict(),known_confirmed_high=last_known(peaks),known_confirmed_low=last_known(lows),cached_G1=dict(grade=g.grade,fresh_up=g.fresh_up,acute_down=g.acute_down,strength_ready=g.strength_ready,phase=g.phase,up_reasons=g.up_reasons,legacy_ix_target_not_actual_I=g.ix_target),actual_G1_fields_equal_saved_IX=equal,CP=c.to_dict(),canonical_receipt_today=by_receipt.get(day),last_historical_canonical_receipt=previous[-1]if previous else None,historical_receipt_warning='Historical receipt is not an unconsumed new trade credential; no model state was rebuilt.',reference_comparisons=[dict(reference_id=r['id'],known_today=r['known_day']<=day,reference_price=r['price']if r['known_day']<=day else None,close_strictly_above=bool(f.close>r['price'])if r['known_day']<=day else None)for r in references],original_stock_qty_at_CLOSE=d['positions'].get(SID,0),original_live_layers_at_CLOSE=[r for r in d['layers']if r['sid']==SID],original_opportunity=[r for r in ops if r['day']==day],original_frozen_intents=[r for r in decisions[day]['intents']if r['sid']==SID],original_ACT_checkpoints=[r for r in book['audit']if r.get('kind')=='risk_checkpoint'and r['at'][:10]==day]))
combined=old+[clean(r)for r in rows];combined.sort(key=lambda r:r['day']);assert len({r['day']for r in combined})==len(combined)
for day,r in old_by.items():assert next(x for x in combined if x['day']==day)==r
assert hashlib.sha256(original_file.read_bytes()).hexdigest()==original_hash
save('FULL_DAILY_ORIGINAL_2025_11_20_2026_01_16.json',combined)
save('FULL_DAILY_APPEND_ORIGINAL_FUNDING_AND_TRADES.json',dict(execution_boundary='Completed original No60 daily-bar-proxy ledger, not broker receipts/minute executions.',original_added_interval_funding=fund,original_trades_in_added_interval=[r for r in book['trades']if r['security_id']==SID and '2025-12-08'<=r['at'][:10]<='2026-01-14'],original_exit_proposals_in_added_interval=[r for r in book['audit']if r.get('kind')=='pilot_layer_exit'and r.get('sid')==SID and '2025-12-08'<=r['at'][:10]<='2026-01-14'],scope='No derived period PnL, size/routing or counterfactual trade.'))
save('FULL_DAILY_APPEND_STATUS.json',dict(status='SAVED_ORIGINAL_SLICE_APPENDED_TO_SEPARATE_FILE',old14_file_sha256_before_and_after=original_hash,old14_rows_unchanged=True,added_rows=len(rows),full_rows=len(combined),missing=missing,requested_append=['2025-12-08','2026-01-14'],new_models_indicators_strategies_accounts_backtests=0,account_earnings_note='Closed layer lifecycle gain51001.61 includes2025December price advance; this append does not relabel it as2026calendar-year gain or calculate annual attribution.'))
SRC[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('FULL_DAILY_APPEND_SOURCE_SHA256.json',SRC)
print(json.dumps(dict(old_rows=len(old),added_rows=len(rows),full_rows=len(combined),missing=len(missing),old14_unchanged=True,new_models=0),ensure_ascii=False))
