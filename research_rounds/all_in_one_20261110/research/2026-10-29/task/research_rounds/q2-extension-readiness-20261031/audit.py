"""Read existing inputs/checkpoints and describe fixed price windows; no runner."""
from pathlib import Path
import json,gzip,pickle,sys,time,hashlib,collections
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
sys.path.insert(0,str(W/'execution-pressure-preflight-20261031'));import pressure_runner as R
from initialization_guard import IO
J=R.J;L=R.L;U=L.U
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):IO.write_json(O/(n+'.json'),J.W.canon(x))
def quant(x):
 x=pd.Series(x).dropna().astype(float)
 return dict(n=len(x),**{str(q):float(x.quantile(q)) for q in (0,.1,.25,.5,.75,.9,1)}) if len(x) else dict(n=0)
def draw(series,start,end):
 s=series.loc[start:end];peak=s.cummax();dd=1-s/peak;under=s.lt(peak);longest=run=0;segments=[];begin=None
 for d,on in under.items():
  if on:
   if begin is None:begin=d
   run+=1;longest=max(longest,run)
  elif begin is not None:
   part=dd.loc[begin:d];segments.append(dict(start=str(begin.date()),recovered=str(d.date()),observations=run,max_drawdown_pct=float(part.max()*100),censored=False));begin=None;run=0
 if begin is not None:segments.append(dict(start=str(begin.date()),recovered=None,observations=run,max_drawdown_pct=float(dd.loc[begin:].max()*100),censored=True))
 return dict(price_reference_return_pct=float((s.iloc[-1]/s.iloc[0]-1)*100),max_drawdown_pct=float(dd.max()*100),longest_below_peak_observations=longest,drawdown_segments=segments)
def main():
 t=time.monotonic();freeze=read(U/'FREEZE.json');sm=read(U/'STOCK_MANIFEST.json');im=read(U/'INDUSTRY_MANIFEST.json');fixed=freeze['stocks'];assert len(fixed)==1709 and len(im)==90
 runtime=J.M.P;records={x['series_id']:x for x in read(runtime/'manifest.json')['series']};market=pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True)
 days=market.loc['2026-04-01':'2026-06-30'].index;counts=pd.DataFrame(0,index=days,columns=['facts_observed','E0_ready','CP1_ready','raw_OHLC_known','raw_positive_volume','raw_flat_HL','raw_missing_volume','H1_known'])
 rows=[];mismatch=[];newly_observable=[];native_columns=['raw_close','factor','i_target','i_buy','i_floor','e0_ready','e0_floor']
 for n,r in enumerate(sm):
  sid=r['symbol'];f=pd.read_parquet(r['refs']['facts']);cp=pd.read_parquet(r['refs']['CP1'],columns=['ready','receipt']);fq=f.loc['2026-04-01':'2026-06-30'];cq=cp.loc['2026-04-01':'2026-06-30']
  nf=pd.read_parquet(W/'native-I-cache-interface-20261031/facts'/f'{sid}.parquet',columns=native_columns).loc['2026-04-01':'2026-06-30']
  aa=fq[native_columns].copy(deep=False);bb=nf.copy(deep=False);aa.index=aa.index.as_unit('ns');bb.index=bb.index.as_unit('ns')
  try:pd.testing.assert_frame_equal(aa,bb,check_exact=True,check_dtype=False,check_freq=False)
  except AssertionError as e:mismatch.append(dict(sid=sid,kind='Q2 native I/facts mismatch',detail=str(e)[:200]))
  raw=pd.read_parquet(records[sid]['raw']['path'],columns=['trade_date','open','high','low','close','volume','observed_bar','price_eligible'])
  raw.index=pd.DatetimeIndex(pd.to_datetime(raw.trade_date)).normalize();raw=raw.loc['2026-04-01':'2026-06-30']
  known=raw[['open','high','low','close']].apply(np.isfinite).all(axis=1)&raw[['open','high','low','close']].gt(0).all(axis=1)&raw.high.ge(raw.low)&raw.observed_bar.eq(True)&raw.price_eligible.eq(True)
  exact=raw.close.reindex(fq.index);gap=exact-fq.raw_close
  if (gap.dropna().abs()>1e-10).any():mismatch.append(dict(sid=sid,kind='Q2 current raw vs cached raw_close mismatch',n=int((gap.dropna().abs()>1e-10).sum())))
  fields=dict(facts_observed=pd.Series(True,index=fq.index),E0_ready=fq.e0_ready.eq(True),CP1_ready=cq.ready.eq(True),raw_OHLC_known=known,raw_positive_volume=known&raw.volume.gt(0)&np.isfinite(raw.volume),raw_flat_HL=known&raw.high.eq(raw.low),raw_missing_volume=known&~np.isfinite(raw.volume))
  # Count known True observations only. This does not impute a missing price,
  # readiness flag or trading qualification; mother denominator stays1709.
  for k,s in fields.items():counts[k]+=s.reindex(days).eq(True).fillna(False).astype(int)
  receipts=read(r['refs']['receipts']);nr=sum('2026-04-01'<=x['confirmed_day']<='2026-06-30' for x in receipts)
  had_old=len(f.loc['2025-07-01':'2026-03-31'])>0
  if not had_old and len(fq):newly_observable.append(sid)
  rows.append(dict(sid=sid,manifest_status=r['status'],cache_through=r.get('cache_through'),Q2_facts_rows=len(fq),Q2_CP1_ready=int(cq.ready.eq(True).sum()),Q2_CP1_unready_or_unknown=int(cq.ready.ne(True).sum()),Q2_CP1_receipts=nr,Q2_raw_rows=len(raw),Q2_valid_OHLC=int(known.sum()),Q2_positive_volume=int((known&raw.volume.gt(0)&np.isfinite(raw.volume)).sum()),first_local_eligible_observation=str(f.index.min().date()) if len(f) else None,last_local_eligible_observation=str(f.index.max().date()) if len(f) else None))
  if n%400==399:print('READ_INPUTS',n+1,round(time.monotonic()-t,2),flush=True)
 h=np.load(J.M.P/'h1.npz');hdates=pd.DatetimeIndex(h['dates']);symbols={str(s):i for i,s in enumerate(h['symbols'])};mask=(hdates>=days.min())&(hdates<=days.max());hs=h['score'][mask]
 for k,d in enumerate(hdates[mask]):
  if d in counts.index:counts.loc[d,'H1_known']=sum(np.isfinite(hs[k,symbols[s]]) for s in fixed if s in symbols)
 counts.index.name='day';counts.to_csv(O/'Q2_DAILY_INPUT_COUNTS.csv')
 state=[];prices={}
 for r in im:
  g=r['series'];st=pd.read_parquet(r['refs']['state']);q=st[(st.day>='2026-04-01')&(st.day<='2026-06-30')];f=pd.read_parquet(J.M.O/'industry-facts'/f'{g}.parquet');prices[g]=f.raw_close
  state.append(dict(sector=g,Q2_state_rows=len(q),Q2_ready_price_rows=int(f.loc['2026-04-01':'2026-06-30'].e0_ready.eq(True).sum()),Q2_receipts=int(q.receipt.eq(True).sum()),last=str(f.index.max().date())))
 availability=dict(fixed_identities=len(fixed),current_snapshot_not_PIT=True,manifest_statuses=dict(collections.Counter(x['status'] for x in sm)),stock_rows_audited=len(rows),stocks_with_Q2_facts=sum(x['Q2_facts_rows']>0 for x in rows),stocks_without_Q2_facts=sum(not x['Q2_facts_rows'] for x in rows),newly_observable_after_original_window=newly_observable,stocks_Q2_CP1_ever_ready=sum(x['Q2_CP1_ready']>0 for x in rows),stocks_Q2_price_but_CP1_never_ready=[x['sid'] for x in rows if x['Q2_facts_rows'] and not x['Q2_CP1_ready']],Q2_market_observations=len(days),daily_counts={k:quant(counts[k]) for k in counts},industry_state=state,Q2_native_cache_mismatches=mismatch,market_clock_through=str(market.index.max().date()),H1_through=str(hdates.max().date()),market_clock_sha256=sha(J.M.O/'recovery.csv'),stock_manifest_sha256=sha(U/'STOCK_MANIFEST.json'),industry_manifest_sha256=sha(U/'INDUSTRY_MANIFEST.json'),new_cache_generated=False,new_account_paths=0)
 save('INPUT_COVERAGE',availability);save('STOCK_COVERAGE',rows);print('INPUT_AUDIT_DONE',round(time.monotonic()-t,2),'mismatches',len(mismatch),flush=True)
 # No account object is initialized or restored here. Read checkpoint state only.
 checkpoints=[]
 for ref,base in [('B3',J.O/'run-universe'),('B_diag',R.BASE.O/'run')]:
  path=base/'checkpoint.pkl';p=pickle.loads(path.read_bytes());a=p['accounts']['B'];oldfreeze=p['source_freeze'];changed=[dict(path=k,expected=v,actual=sha(k) if Path(k).exists() else None) for k,v in oldfreeze.items() if not Path(k).exists() or sha(k)!=v]
  with gzip.open(base/'pair/B.json.gz','rt') as z:book=json.load(z)
  assert J.W.canon(a['trades'])==book['trades'];assert J.W.canon(a['layers'])==book['layers'];assert J.W.canon(a['jmeta'])==book['metadata'];assert str(a['available'])==book['ending_cash']
  b=a['budget'];checkpoints.append(dict(reference=ref,path=str(path),sha256=sha(path),last_completed_event=str(p['last_completed_event']),account_keys=list(p['accounts']),selected_account='B',checkpoint_has_generation_identity=path.with_suffix('.provenance.json').exists(),source_freeze_files=len(oldfreeze),changed_frozen_sources=changed,matching_final_book=True,available=str(a['available']),holdings=len(a['positions']),pending_buys=len(a['buys']),pending_sells=len(a['exits']),trade_records=len(a['trades']),core_epoch_locks=len(a['core_epoch']),industry_states=len(b.sectors),accumulated_negative_realization_and_fees=sum(b.losses.values()),ACT=a['risk_state'],preserved_fields=['positions/lots/layers/meta','cash/reservations/settlements/dividend_AR','orders/expiry/receipt_consumption','core_epoch/last_buy','ACT/on/peak/phase','industry/stock epoch/attempt','losses/all fees/trade history','actions applied/dividends paid'],restore_executed=False))
 save('CHECKPOINT_READINESS',dict(checkpoints=checkpoints,new_account_paths=0,design='explicit selected-account legacy continuation after verifying frozen input/code and unchanged historical prefix; new source_freeze linked to parent checkpoint, never spoof/backfill old identity',required_adapter_changes=['parameterize readonly input horizon from March31 to June30 without altering original caches','build complete Q2 immutable input views before importing old mutable B state','select B from original combined A/B checkpoint; retain only this reference','explicitly verify legacy source/prefix/final-book before restoring into new-version identity; old strict source_freeze cannot be bypassed silently','run existing event loop with end June30 and resume_after exact March31; no account initialization reset']))
 # Fixed-window market description, never informed by account returns.
 price=pd.DataFrame(prices).sort_index();base=pd.Timestamp('2025-06-30');end=pd.Timestamp('2026-06-30');common=market.loc[base:end].index
 price=price.reindex(common);ref=(price/price.loc[base]).mean(axis=1,skipna=False)
 features=pd.read_parquet(J.M.F);meta=read(ROOT/'research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');names={x['sector_id']:x['industry'] for x in meta.values()}
 windows=[('2025Q3','2025-06-30','2025-07-01','2025-09-30'),('2025Q4','2025-09-30','2025-10-01','2025-12-31'),('2026Q1','2025-12-31','2026-01-01','2026-03-31'),('2026Q2','2026-03-31','2026-04-01','2026-06-30'),('prior9months','2025-06-30','2025-07-01','2026-03-31')];descriptions=[]
 daily_returns=price.pct_change(fill_method=None);daily_up=daily_returns.gt(0).sum(axis=1)/daily_returns.notna().sum(axis=1)
 for label,prior,start,last in windows:
  rr=price.loc[last]/price.loc[prior]-1;positive=rr[rr>0].sort_values(ascending=False);f=features[(features.day>=start)&(features.day<=last)];breadth=f.groupby('day').R21.agg(lambda s:s.gt(0).sum()/s.notna().sum());mk=market.loc[start:last]
  descriptions.append(dict(window=label,observations=len(mk),industry_return_pct=quant(rr*100),positive=int(rr.gt(0).sum()),negative=int(rr.lt(0).sum()),flat=int(rr.eq(0).sum()),unknown=int(rr.isna().sum()),positive_gain_top3_share=float(positive.head(3).sum()/positive.sum()) if len(positive) else None,top3=[dict(sector=g,industry=names.get(g),return_pct=float(v*100)) for g,v in positive.head(3).items()],daily_up_industry_breadth=quant(daily_up.loc[start:last]),R21_positive_industry_breadth=quant(breadth),equal90_price_reference=draw(ref,prior,last),original_external_market=dict(fast_on_days=int(mk.fast_on.eq(True).sum()),breakout_days=int(mk.breakout.eq(True).sum()),breadth=quant(mk.breadth),market_measurement=quant(mk.market)),not_no_mainline_certification=True))
 save('MARKET_STATE_DESCRIPTION',dict(protocol_sha256=sha(O/'PROTOCOL.txt'),windows=descriptions,industry_price_source='existing same-provider raw industry facts, no strategy returns used',no_trading_thresholds=True))
 save('COMPLETION',dict(read_only=True,new_account_paths=0,new_cache_generation=0,seconds=time.monotonic()-t,coverage_complete=True,extension_condition='data/schema ready if no mismatch; explicit legacy continuation wrapper and prefix checks required before authorized future run',no_OOS=True))
 for x in descriptions:print('STATE',x['window'],'up/down',x['positive'],x['negative'],'median',round(x['industry_return_pct']['0.5'],3),'Qref DD',round(x['equal90_price_reference']['max_drawdown_pct'],3),flush=True)
 print('READONLY_DONE',round(time.monotonic()-t,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  IO.write_json(O/'ERROR.json',dict(type=type(e).__name__,reason=str(e),new_account_paths=0));raise
