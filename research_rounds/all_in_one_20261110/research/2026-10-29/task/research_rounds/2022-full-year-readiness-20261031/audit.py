"""Read existing full-warm inputs for fixed calendar 2022; no account or signal generation."""
from pathlib import Path
import sys,json,time,hashlib,collections,csv
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'q2-normal-continuation-20261031'))
import continuation as E
J,L=E.J,E.L
START='2022-01-01';END='2022-12-31'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):E.IO.write_json(O/n,J.W.canon(x))
def quant(v):
 s=pd.Series(v).dropna().astype(float)
 return {'n':len(s),**{str(q):float(s.quantile(q)) for q in [0,.1,.25,.5,.75,.9,1]}} if len(s) else {'n':0}
def main():
 t=time.monotonic();sm=read(L.U/'STOCK_MANIFEST.json');im=read(L.U/'INDUSTRY_MANIFEST.json');fixed=read(L.U/'FREEZE.json')['stocks'];assert len(fixed)==1709 and len(im)==90
 runtime=read(J.M.P/'manifest.json');records={r['series_id']:r for r in runtime['series']}
 masterpath=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/results/stock-data-audit/master-crosswalk.csv');master={r['symbol']:r for r in csv.DictReader(masterpath.open())}
 rulespath=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');rules=read(rulespath);cal=pd.DatetimeIndex(sorted({pd.Timestamp(d[:10]) for d in rules['calendars']['A']}));days=cal[(cal>=START)&(cal<=END)];prior=cal[cal<days[0]][-1];last=days[-1]
 h=np.load(J.M.P/'h1.npz');hdates=pd.DatetimeIndex(h['dates']);symbols={str(s):i for i,s in enumerate(h['symbols'])};hm=(hdates>=days[0])&(hdates<=last);hs=pd.DataFrame(h['score'][hm],index=hdates[hm],columns=[str(s) for s in h['symbols']]).reindex(days)
 counts=pd.DataFrame(0,index=days,columns=['facts_observed','raw_valid_OHLC','positive_volume','E0_ready','G_ready','CP1_ready','H1_known','joint_E0_G_H1_ready']);stocks=[];native_receipts=0;missing_receipt_series=0;preIPO=[];source_drift=[]
 save('PROTOCOL.json',dict(fixed_year=2022,calendar_start=str(days[0].date()),calendar_end=str(last.date()),previous_close=str(prior.date()),market_days=len(days),fixed_identities=1709,industries=90,proposed_initial_cash=1000000,new_account_paths=0,new_signal_or_large_cache_generation=0,year_not_selected_by_strategy_returns=True,point_in_time_membership=False,sources={str(p):sha(p) for p in [L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',L.U/'FREEZE.json',J.M.P/'manifest.json',J.M.P/'h1.npz',J.M.O/'recovery.csv',rulespath,masterpath]}))
 for n,r in enumerate(sm):
  sid=r['symbol'];f=pd.read_parquet(r['refs']['facts'],columns=['raw_close','factor','e0_ready','g_ready','i_buy','i_target']);cp=pd.read_parquet(r['refs']['CP1'],columns=['ready','receipt']);q=f.loc[START:END];cq=cp.loc[START:END]
  rr=records[sid];raw=pd.read_parquet(rr['raw']['path'],columns=['trade_date','open','high','low','close','volume','observed_bar','price_eligible']);raw.index=pd.DatetimeIndex(pd.to_datetime(raw.trade_date)).normalize();raw=raw.loc[START:END]
  known=raw[['open','high','low','close']].apply(np.isfinite).all(axis=1)&raw[['open','high','low','close']].gt(0).all(axis=1)&raw.high.ge(raw.low)&raw.observed_bar.eq(True)&raw.price_eligible.eq(True)
  hv=hs[sid].notna() if sid in hs else pd.Series(False,index=days)
  fields=dict(facts_observed=pd.Series(True,index=q.index),raw_valid_OHLC=known,positive_volume=known&raw.volume.gt(0)&np.isfinite(raw.volume),E0_ready=q.e0_ready.eq(True),G_ready=q.g_ready.eq(True),CP1_ready=cq.ready.eq(True),H1_known=hv,joint_E0_G_H1_ready=q.e0_ready.eq(True)&q.g_ready.eq(True)&hv.reindex(q.index).eq(True))
  for k,s in fields.items():counts[k]+=s.reindex(days).eq(True).fillna(False).astype(int)
  ipo=pd.to_datetime(master.get(sid,{}).get('ipoDate'),errors='coerce');pre=raw.index[(raw.index<ipo)&known] if pd.notna(ipo) else []
  if len(pre):preIPO.append(dict(sid=sid,IPO=str(ipo.date()),valid_rows_before_IPO=len(pre)))
  receipts=read(r['refs']['receipts']);nr=sum(START<=x['confirmed_day']<=END for x in receipts);nc=int(cq.receipt.eq(True).sum());native_receipts+=nc;missing_receipt_series+=int(nc>nr)
  warm=f.loc[f.index<days[0]]
  stocks.append(dict(sid=sid,IPO=str(ipo.date()) if pd.notna(ipo) else None,first_cached_observation=str(f.index.min().date()) if len(f) else None,warm_observations=len(warm),facts_rows=len(q),valid_OHLC=int(known.sum()),positive_volume=int(fields['positive_volume'].sum()),CP1_ready=int(cq.ready.eq(True).sum()),CP1_native_receipts=nc,CP1_canonical_receipts_cached=nr,I_true_fresh_days=int((q.i_buy.eq(True)&q.i_target.eq(True)).sum()),joint_E0_G_H1_ready=int(fields['joint_E0_G_H1_ready'].sum()),raw_factor_unknown=int(q.factor.isna().sum()),missing_expected_observation_days=len(days)-len(q.index.intersection(days))))
  if (n+1)%500==0:print('STOCK_READ',n+1,round(time.monotonic()-t,2),flush=True)
 stock_seconds=time.monotonic()-t;counts.index.name='day';counts.to_csv(O/'DAILY_STOCK_COUNTS.csv');save('STOCK_COVERAGE.json',stocks)
 meta=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'));names={r['sector_id']:r['industry'] for r in meta.values()};industries=[];prices={};stages={};stageunknown=pd.Series(0,index=days);industry_source_files={}
 for r in im:
  g=r['series'];fp=J.M.O/'industry-facts'/f'{g}.parquet';f=pd.read_parquet(fp);rawrec=records[g];raw=pd.read_parquet(rawrec['raw']['path']);d=pd.DatetimeIndex(pd.to_datetime(raw.trade_date)).normalize();raw.index=d;rq=raw.loc[START:END];s=pd.read_parquet(r['refs']['state']);q=s[(s.day>=START)&(s.day<=END)].set_index('day');q.index=pd.to_datetime(q.index);z=pd.read_parquet(r['refs']['CP1'],columns=['ready','receipt']);iq=f.loc[START:END]
  st=q.stage_name.reindex(days);unknown=st.isna()|q.action.reindex(days).eq('unknown');stageunknown+=unknown.astype(int);stages[g]=st.where(~unknown);prices[g]=f.raw_close.reindex(pd.DatetimeIndex([prior]).append(days));rr=read(r['refs']['receipts']);cpr=int(z.loc[START:END].receipt.eq(True).sum());rn=sum(START<=x['confirmed_day']<=END for x in rr)
  amount_known=int((np.isfinite(rq.amount)&rq.amount.ge(0)).sum()) if 'amount' in rq else None
  industries.append(dict(sector=g,name=names.get(g),facts_rows=len(iq),E0_ready=int(iq.e0_ready.eq(True).sum()),raw_rows=len(rq),raw_amount_known=amount_known,raw_volume_known=int(np.isfinite(rq.volume).sum()),state_rows=len(q),state_unknown=int(unknown.sum()),CP1_ready=int(z.loc[START:END].ready.eq(True).sum()),native_receipts=cpr,canonical_receipts_cached=rn,H1_known=int(hs[g].notna().sum()) if g in hs else 0,price_start=str(f.index.min().date()),full_state_start=str(s.day.min())))
  industry_source_files[str(fp)]=sha(fp);industry_source_files[r['refs']['state']]=sha(r['refs']['state'])
 price=pd.DataFrame(prices);ret=price.loc[last]/price.loc[prior]-1;rank=ret.sort_values(ascending=False);stage=pd.DataFrame(stages,index=days);density=pd.DataFrame({k:stage.eq(k).sum(axis=1) for k in ['observe','probe','confirmed','expanded']});density['unknown']=stageunknown;density['confirmed_or_expanded']=density.confirmed+density.expanded;density.index.name='day';density.to_csv(O/'DAILY_INDUSTRY_STAGE_COUNTS.csv')
 recovery=pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).reindex(days);positive=ret[ret>0];r21=price.pct_change(21,fill_method=None).reindex(days);dailyret=price.pct_change(fill_method=None).reindex(days);breadth=(dailyret>0).sum(axis=1)/dailyret.notna().sum(axis=1)
 # R21 uses only the matrix's previous-close+year slice here. First20 observations
 # are deliberately unknown instead of silently importing incomplete lookback.
 marketdesc=dict(year=2022,first=str(days[0].date()),last=str(last.date()),prior=str(prior.date()),market_days=len(days),industry_return_pct=quant(ret*100),positive=int(ret.gt(0).sum()),negative=int(ret.lt(0).sum()),flat=int(ret.eq(0).sum()),unknown=int(ret.isna().sum()),ranked_industries=[dict(sector=g,name=names.get(g),return_pct=float(v*100)) for g,v in rank.items()],positive_gain_top3_share=float(positive.nlargest(3).sum()/positive.sum()) if len(positive) else None,daily_positive_industry_fraction=quant(breadth),stage_density={k:quant(density[k]) for k in density},zero_confirmed_or_expanded_days=int(density.confirmed_or_expanded.eq(0).sum()),zero_expanded_days=int(density.expanded.eq(0).sum()),stage_is_not_full_Q_or_actual_funding=True,external_original_market=dict(rows=len(recovery),missing_by_field=recovery.isna().sum().to_dict(),fast_on_days=int(recovery.fast_on.eq(True).sum()),breakout_days=int(recovery.breakout.eq(True).sum()),breadth=quant(recovery.breadth)),not_no_mainline_certification=True)
 save('INDUSTRY_COVERAGE.json',industries);save('MARKET_STATE_2022.json',marketdesc)
 ipos=pd.to_datetime(pd.Series([x['IPO'] for x in stocks]),errors='coerce');covered=[x for x in stocks if x['facts_rows']];na=[x['sid'] for x in stocks if not x['facts_rows']]
 result=dict(readonly=True,new_account_paths=0,new_signal_cache_generated=False,identities=1709,market_days=len(days),facts_present_stocks=len(covered),no_2022_facts=len(na),no_2022_facts_ids=na,positive_volume_ever=sum(x['positive_volume']>0 for x in stocks),CP1_ready_ever=sum(x['CP1_ready']>0 for x in stocks),joint_E0_G_H1_ready_ever=sum(x['joint_E0_G_H1_ready']>0 for x in stocks),stock_count_distributions={k:quant(counts[k]) for k in counts},IPO_dates_known=int(ipos.notna().sum()),IPO_unknown=int(ipos.isna().sum()),IPO_before_2022=int(ipos.lt(pd.Timestamp(START)).sum()),IPO_during_2022=int((ipos.ge(pd.Timestamp(START))&ipos.le(pd.Timestamp(END))).sum()),IPO_after_2022=int(ipos.gt(pd.Timestamp(END)).sum()),valid_preIPO_anomalies=preIPO,CP1_native_stock_receipts=native_receipts,CP1_receipt_series_needing_trace_export=missing_receipt_series,industry_native_CP1_receipts=sum(x['native_receipts'] for x in industries),industry_cached_canonical_receipts=sum(x['canonical_receipts_cached'] for x in industries),industry_full_coverage=all(x['state_rows']==len(days) and x['facts_rows']==len(days) for x in industries),sources_sha256=industry_source_files,seconds=time.monotonic()-t,stock_read_seconds=stock_seconds,current_snapshot_not_PIT=True,year_already_consumed_by_prior_research=True,remaining_pre_run_gates=['reexport canonical2022 stock/industry receipts from existing full-warm CP1 inputs/output and unchanged trace; no price model rerun needed','read-only/source-prefix checks for2022 receipts and stock I/fullQ','parameterize date endpoints while preserving original calendar/fees at2022 dates; fresh1m account no pre-start grants','freeze new import identity/hash and existing current reference contract before any future account authorization'])
 save('READINESS.json',result);print('READONLY_DONE',json.dumps({k:result[k] for k in ['seconds','facts_present_stocks','no_2022_facts','CP1_ready_ever','CP1_receipt_series_needing_trace_export','industry_full_coverage','CP1_native_stock_receipts','industry_native_CP1_receipts']},ensure_ascii=False),flush=True);print('MARKET',json.dumps({k:marketdesc[k] for k in ['positive','negative','industry_return_pct','stage_density','zero_confirmed_or_expanded_days','zero_expanded_days']},ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e),new_account_paths=0));raise
