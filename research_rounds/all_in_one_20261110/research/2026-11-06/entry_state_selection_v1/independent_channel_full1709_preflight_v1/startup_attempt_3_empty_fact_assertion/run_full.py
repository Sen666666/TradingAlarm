"""One all-universe causal market-state pass. No accounts, orders or economics."""
from pathlib import Path
import json,time,hashlib,traceback,sys
import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
from engine import *
from fast_core import simulate
MEMBERSHIP=R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv'

def save(name,obj):
 (O/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')

class Stream:
 def __init__(self,name):self.name=name;self.writer=None;self.rows=0
 def write(self,f):
  if not len(f):return
  f=f.copy()
  for c in f.columns:
   if f[c].dtype==object:f[c]=f[c].astype('string')
  t=pa.Table.from_pandas(f,preserve_index=False)
  if self.writer is None:self.writer=pq.ParquetWriter(O/self.name,t.schema,compression='zstd')
  elif t.schema!=self.writer.schema:t=t.cast(self.writer.schema)
  self.writer.write_table(t);self.rows+=len(f)
 def close(self):
  if self.writer:self.writer.close()

def freeze():
 assert not (O/'RUN_ONCE.json').exists(),'One-shot guard: no second market pass.'
 eq=json.loads((O/'PRE_RUN_EQUIVALENCE.json').read_text());assert eq['status']=='PASS'
 assert eq['optimized_sha256']==sha(O/'fast_core.py') and eq['engine_sha256']==sha(O/'engine.py') and eq['core_sha256']==sha(P/'core.py')
 # Freeze and verify every consumed path before any universe market computation.
 for sid,m in sorted(manifest.items()):
  path=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));src(path,m['source_sha256'][path])
  for k in ['facts','CP1']:
   path=m['refs'][k];src(path,m['output_sha256'][path])
 for p in [MEMBERSHIP,O/'run_full.py',O/'engine.py',O/'fast_core.py',O/'build_and_verify.py',O/'PRE_RUN_EQUIVALENCE.json',O/'TRANSLATION.json',P/'core.py',P/'PROTOCOL.md',P/'INDEPENDENT_AUDIT.json']:src(p)
 save('INPUT_HASHES.json',S)
 save('FIXED_WINDOWS.json',[dict(window=w,start=a,end=b) for w,a,b in WINDOWS])
 save('OUTPUT_SCHEMA.json',dict(join_key=['sid','day'],window_values=[w for w,a,b in WINDOWS],receipt_id='sid|root_day YYYY-MM-DD|day YYYY-MM-DD; frozen source segment is carried in identity; birth dates cannot repeat per sid',daily='All frozen core fields unchanged, valid is price_valid. Plus raw and adjusted OHLC, amount, raw_volume, adjustment_factor, native e0_ready/e0_floor/g_ready, source identity and quality flags, metadata, window. Daily rows include missing-history calendar rows explicitly.',coverage='1709 x 3 rows, including all 22 manifest no-local-history names. Birth/receipt/failure/unknown and known/unknown day counts; no-history is not a negative signal.',carry='One row per sid/window with exact first-window-day state and carried root birthdate; first-day failure/UNKNOWN retains old-root identity. No window-start reinitialization.',births='BIRTHS.parquet is births inside fixed windows; FULL_WARM_BIRTHS.parquet contains all warm-history births including roots carried into a window.',receipts='RECEIPTS.parquet is every fresh frontier receipt in fixed windows, never fills; all market fields identical to daily.',next_open='Immediate next common-calendar open only. Raw price/source/factor observations; daily one-price flag is only a fact, not fill. No skipping to a later valid bar. June30 next-open may be outside frozen observation horizon.',review='engine.replay(sid,cut) truncates raw,facts,CP prior to building input and calculating; fast_core.simulate(q) versus original core simulate(q) for exact sampling. No old runner imported.'))
 protocol='''# Full 1709 market-state preflight\n\nThe unique algorithm is the immutable audited independent_channel_probe_preflight_v1/core.py. Its original protocol is incorporated without a formula change. Price C > strictly previous 20 High births a root independently of E0/I/G/PVR and amount. Freeze latest lowest close a (not before last failure), U, Ca, strictly a-prior-21 valid amount median B and R=log(U/Ca). F and Q accrue only positive new log-close frontier; Q contribution min(1,sqrt(amount/B))*delta. Price root exists even if amount is UNKNOWN. Q>=R confirms; proven prior confirmation is not erased by later missing amount. S_birth=minLow[a..birth]; subsequent close <= old S fails before any ready+target E0 floor may raise max(S,E0floor). No old-I or old-E0 closure exit gate. Only new frontier gives a fresh receipt.\n\nAll 1709 fixed STOCK_MANIFEST names: 1687 complete and 22 explicitly no local observations through end. The complete calendar prefix starts at 2007-08-01 and each source supplies its complete locally available same-source history through 2026-06-30. Calendar rows before a symbol exists are not negative signals. Root warming never restarts at a study-window boundary. The three all-stock fixed output windows are 2022-01-01..2022-12-31, 2024-09-01..2024-12-31, 2026-01-01..2026-06-30. 2026 URFI881121 is a subsidiary current-roster slice only. The roster is not PIT membership.\n\nThe optimized function is a mechanical iteration/access translation and passes exact all-column equality for all five full warmed price paths, all existing 46 synthetic checks and optimized-vs-original synthetic comparisons before this pass. Raw/facts/CP alignment, source identity and amount-valid separation are extracted as functions from the prior runners without importing runner bodies. No parameter search, altered constants, PVR gate, account, shares, fees, economic returns, fills or execution forecasts.\n\nPrice/source/factor validity failure quarantines a root as UNKNOWN; not a sale or account unlock. Amount UNKNOWN affects only volume credit. Missing native E0 facts cannot provide takeover; existing mismatched coordinates make price knowledge invalid. Next open means the immediately next common calendar OPEN and only factual raw observation. One-price days are not tradability evidence; orderability, real ACK, fill, budget and responsibility remain unknown. Receipts are market permissions conditional on the unchanged execution contract, never trades.\n\nBoundary of proof: stored input hashes and forward-only market computation are verified; this pass does not independently re-audit upstream corporate-action publication times, factor construction, E0/I/CP native causal construction, exchange authenticity, suspension rules, dated lot limits, or current-roster survivorship. The five earlier examples were consumed development cases, not an OOS sample; these historical windows have previously been researched. A true truncated-input prefix check proves only causality conditional on the frozen upstream facts.\n'''
 (O/'PROTOCOL.md').write_text(protocol)
 save('RUN_ONCE.json',dict(engineering_attempt=3,resumed_completed_stocks=177,no_completed_market_state_recomputed=True,started_utc=str(pd.Timestamp.now(tz='UTC')),input_hash_file_sha256=sha(O/'INPUT_HASHES.json'),protocol_sha256=sha(O/'PROTOCOL.md'),schema_sha256=sha(O/'OUTPUT_SCHEMA.json'),windows_sha256=sha(O/'FIXED_WINDOWS.json'),market_pass_count=1,account_runs=0))
 print('FROZEN',len(S),'input files',flush=True)

def next_opens(sid,q,z):
 rows=[]
 for r in z.itertuples():
  pos=full_cal.get_loc(r.day);nd=full_cal[pos+1] if pos+1<len(full_cal) else pd.NaT
  rr=q.loc[nd] if nd in q.index else None
  pv=bool(rr.price_valid) if rr is not None else False
  have_price=rr is not None and np.isfinite(rr.raw_open) and rr.raw_open>0
  identical=bool(rr.identity==r.identity) if pv else None
  factor=bool(np.isclose(rr.adjustment_factor,r.adjustment_factor,rtol=1e-11)) if pv else None
  rows.append(dict(sid=sid,day=r.day,window=r.window,root_day=r.root_day,receipt_id=r.receipt_id,born=r.born,phase=r.phase,signal_raw_close=r.raw_close,signal_floor=r.S_new,signal_factor=r.adjustment_factor,signal_identity=r.identity,next_common_open_day=nd,next_raw_open=float(rr.raw_open) if have_price else np.nan,next_adjusted_open=float(rr.open) if pv else np.nan,next_price_valid=pv,next_amount_valid=bool(rr.amount_valid) if rr is not None else None,next_identity=str(rr.identity) if pv else None,next_factor=float(rr.adjustment_factor) if pv else np.nan,source_match=identical,factor_match=factor,source_factor_match=bool(identical and factor) if pv else None,all_day_one_price=bool(rr.raw_open==rr.raw_high==rr.raw_low==rr.raw_close) if pv else None,next_open_above_signal_floor=bool(rr.open>r.S_new) if pv else None,observation_status='KNOWN_RAW_DAILY_OBSERVATION_NOT_FILL' if pv else 'OUTSIDE_FROZEN_INPUT_HORIZON' if rr is None else 'UNKNOWN_PRICE_SOURCE',historical_fill='UNKNOWN_NOT_SIMULATED',earliest_sale_open_day=full_cal[pos+2] if pos+2<len(full_cal) else pd.NaT))
 f=pd.DataFrame(rows)
 if len(f):
  for c in ['source_match','factor_match','source_factor_match','all_day_one_price','next_open_above_signal_floor','next_amount_valid']:f[c]=f[c].astype('boolean')
 return f

def main():
 meta=pd.read_csv(MEMBERSHIP).rename(columns={'sector_id':'sector'}).set_index('sid');assert set(manifest)<=set(meta.index);assert {'name','industry','sector'}<=set(meta.columns)
 freeze();t=time.monotonic()
 recovery=O/'startup_attempt_2_empty_facts';prior_daily=pd.read_parquet(recovery/'DAILY_STATES.parquet');prior_births=pd.read_parquet(recovery/'FULL_WARM_BIRTHS.parquet');completed=set(prior_daily.sid);prior_groups={sid:g.set_index('day') for sid,g in prior_daily.groupby('sid',sort=False)};assert len(completed)==177
 streams={n:Stream(n+'.parquet') for n in ['DAILY_STATES','RECEIPTS','BIRTHS','FULL_WARM_BIRTHS','FAILURES_UNKNOWN','MARKET_EVENTS','NEXT_OPEN_OBSERVATIONS','SEMICONDUCTOR_2026_DAILY','SEMICONDUCTOR_2026_RECEIPTS']}
 cov=[];carry=[];errs=[];sources=[]
 try:
  for num,(sid,m) in enumerate(sorted(manifest.items()),1):
   try:
    q=data(sid);resumed=sid in completed
    if resumed:allz=prior_groups[sid].drop(columns=['window']);x=allz
    else:x=simulate(q);allz=output_frame(sid,q,x)
    md=meta.loc[sid]
    for c in ['name','industry','sector']:allz[c]=str(md[c])
    observed=q.close.notna();first=q.index[observed][0] if observed.any() else pd.NaT
    if m['status']!='complete':assert not observed.any(),sid
    sources.append(dict(sid=sid,manifest_status=m['status'],first_local_price_day=first,last_local_price_day=q.index[observed][-1] if observed.any() else pd.NaT,full_calendar_rows=len(q),full_observed_rows=int(observed.sum()),full_price_known=int(q.price_valid.sum()),full_births=int(prior_births.sid.eq(sid).sum()) if resumed else int(x.born.sum())))
    if not resumed:streams['FULL_WARM_BIRTHS'].write(allz[allz.born].reset_index())
    for w,a,b in WINDOWS:
     z=allz.loc[a:b].copy();z['window']=w;f=z.reset_index();g=q.loc[a:b];known=int(z.valid.sum());obs=int(g.close.notna().sum())
     status='NO_LOCAL_HISTORY_BY_END' if not observed.any() else 'NO_LOCAL_HISTORY_IN_WINDOW' if not obs and (pd.isna(first) or first>pd.Timestamp(b)) else 'NO_PRICE_KNOWN_IN_WINDOW' if not known else 'PARTIAL_PRICE_KNOWN' if known<len(z) else 'ALL_PRICE_KNOWN'
     firstrow=z.iloc[0];prior=x.loc[x.index<z.index[0]];pr=prior.iloc[-1] if len(prior) else None
     carried=bool(firstrow.active and not firstrow.born and pd.notna(firstrow.root_day) and firstrow.root_day<z.index[0])
     roots=set(z.root_day.dropna());active_roots=set(z.loc[z.active,'root_day'].dropna());rr=z[z.receipt]
     cov.append(dict(sid=sid,window=w,name=str(md['name']),industry=str(md['industry']),sector=str(md['sector']),manifest_status=m['status'],coverage_status=status,days=len(z),observed_price_rows=obs,price_known=known,price_unknown=len(z)-known,amount_known=int(z.amount_valid.sum()),amount_unknown=len(z)-int(z.amount_valid.sum()),price_and_amount_known=int((z.valid&z.amount_valid).sum()),valid_price_amount_unknown=int((z.valid&~z.amount_valid).sum()),native_E0_ready_known=int(g.e0_ready.notna().sum()),native_E0_ready=int(g.e0_ready.eq(1).sum()),coordinate_known=int(g.coordinate_valid.sum()),root_unknown=int(z.root_unknown.sum()),births=int(z.born.sum()),receipts=int(z.receipt.sum()),receipt_roots=int(rr.root_day.nunique()),failures=int(z.failed.sum()),active_days=int(z.active.sum()),roots_intersecting=len(roots),active_roots_intersecting=len(active_roots),confirmations=int(z.confirmed_now.sum()),probe_days=int(z.phase.eq('PROBE').sum()),probe_amount_unknown_days=int(z.phase.eq('PROBE_AMOUNT_UNKNOWN').sum()),confirmed_days=int(z.phase.eq('CONFIRMED').sum()),carried_root_at_start=carried,carry_root_birthdate=firstrow.root_day if carried else pd.NaT,first_local_price_day=first,birth_E0_off=int((z.born&z.E0.eq(0)).sum()),birth_I_off=int((z.born&z.I.eq(0)).sum()),birth_i_buy_off=int((z.born&z.i_buy.eq(0)).sum()),birth_CP_off=int((z.born&z.CP.eq(0)).sum())))
     carry.append(dict(sid=sid,window=w,first_window_day=z.index[0],first_day_active=bool(firstrow.active),first_day_born=bool(firstrow.born),first_day_failed=bool(firstrow.failed),first_day_root_unknown=bool(firstrow.root_unknown),first_day_root_day=firstrow.root_day,carried_active_at_start=carried,carried_root_birthdate=firstrow.root_day if carried else pd.NaT))
     if not resumed:
      streams['DAILY_STATES'].write(f);streams['RECEIPTS'].write(f[f.receipt]);streams['BIRTHS'].write(f[f.born]);streams['FAILURES_UNKNOWN'].write(f[f.failed|f.root_unknown]);streams['MARKET_EVENTS'].write(f[f.born|f.receipt|f.failed|f.root_unknown|f.confirmed_now|f.e0_raised]);streams['NEXT_OPEN_OBSERVATIONS'].write(next_opens(sid,q,f[f.receipt]))
     if not resumed and w=='2026H1' and str(md['sector'])=='URFI881121':streams['SEMICONDUCTOR_2026_DAILY'].write(f);streams['SEMICONDUCTOR_2026_RECEIPTS'].write(f[f.receipt])
   except Exception as e:
    err=dict(sid=sid,type=type(e).__name__,error=str(e),traceback=traceback.format_exc());errs.append(err);print('ERROR',json.dumps(err),flush=True);raise
   if num%100==0 or num==len(manifest):
    print('PROGRESS',json.dumps(dict(stocks=num,total=len(manifest),seconds=round(time.monotonic()-t,2),daily_rows=streams['DAILY_STATES'].rows+len(prior_daily[prior_daily.sid.isin(sorted(completed)[:num])]),receipts=streams['RECEIPTS'].rows+int(prior_daily.loc[prior_daily.sid.isin(sorted(completed)[:num]),'receipt'].sum()),errors=len(errs))),flush=True)
 finally:
  for s in streams.values():s.close()
  if errs:save('ERRORS.json',errs)
 # Consolidate verified completed chunks and the resumed remainder without recomputing roots.
 chunks=O/'completed_remainder_chunks';chunks.mkdir()
 for name,stream in streams.items():
  p=O/(name+'.parquet');prior=recovery/(name+'.parquet')
  if not prior.exists():continue
  parts=[prior]
  if p.exists():p.rename(chunks/p.name);parts.append(chunks/p.name)
  writer=None;rows=0
  for part in parts:
   pf=pq.ParquetFile(part)
   for batch in pf.iter_batches():
    table=pa.Table.from_batches([batch])
    if writer is None:writer=pq.ParquetWriter(p,table.schema,compression='zstd')
    elif table.schema!=writer.schema:table=table.cast(writer.schema)
    writer.write_table(table);rows+=len(table)
  if writer:writer.close()
  stream.rows=rows
 c=pd.DataFrame(cov);c.to_csv(O/'COVERAGE.csv',index=False);pd.DataFrame(carry).to_csv(O/'WINDOW_CARRY.csv',index=False);pd.DataFrame(sources).to_csv(O/'FULL_HISTORY_COVERAGE.csv',index=False)
 assert len(c)==1709*3 and c.groupby('window').size().eq(1709).all()
 sums=c.groupby('window').agg(stocks=('sid','size'),covered_stocks=('price_known',lambda v:int((v>0).sum())),no_local_history_by_end=('manifest_status',lambda v:int(v.ne('complete').sum())),price_known=('price_known','sum'),price_unknown=('price_unknown','sum'),amount_known=('amount_known','sum'),births=('births','sum'),receipts=('receipts','sum'),failures=('failures','sum'),root_unknown=('root_unknown','sum'),active_days=('active_days','sum'),carried_roots_at_start=('carried_root_at_start','sum')).reset_index();sums.to_csv(O/'WINDOW_SUMMARY.csv',index=False)
 c[c.sector.eq('URFI881121')&c.window.eq('2026H1')].to_csv(O/'SEMICONDUCTOR_2026_COVERAGE.csv',index=False)
 expected=json.loads((O/'INPUT_HASHES.json').read_text());assert all(sha(p)==h for p,h in expected.items()),'Input changed during run'
 save('SOURCE_HASHES.json',S)
 output={p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in ['OUTPUT_HASHES.json','QA.json']};save('OUTPUT_HASHES.json',output)
 save('QA.json',dict(status='COMPLETE_MARKET_PREFLIGHT_PENDING_INDEPENDENT_AUDIT',stocks=1709,complete_manifest=1687,no_local_history_manifest=22,coverage_rows=len(c),successful_full_universe_coverage=1,engineering_start_attempts=3,first_attempt_computed_stock_count=1,first_attempt_output_rows=0,second_attempt_completed_stock_count=177,third_attempt_reused_stocks=177,third_attempt_new_stock_paths=1532,original_market_algorithm_unchanged=True,account_runs=0,orders=0,fills=0,returns=0,all_input_hashes_unchanged=True,full_warm_each_stock=True,original_core_unchanged=sha(P/'core.py')==json.loads((O/'PRE_RUN_EQUIVALENCE.json').read_text())['core_sha256'],upstream_PIT_not_reaudited=True,errors=errs,output_rows={k:v.rows for k,v in streams.items()},seconds=time.monotonic()-t))
 print('COMPLETE',sums.to_json(orient='records'),flush=True)
if __name__=='__main__':main()
