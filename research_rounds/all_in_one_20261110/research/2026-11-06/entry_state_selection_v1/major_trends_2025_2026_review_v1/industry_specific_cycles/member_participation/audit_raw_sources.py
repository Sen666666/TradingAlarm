import pathlib,json,pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'major_trends_2025_2026_review_v1/industry_specific_cycles/member_participation'
H={r['sid']:r for r in json.load(open(R/'account_comparison_continuous_v1/inputs/H1_MANIFEST.json'))}
U=pd.read_csv(O/'ALL_MEMBER_WINDOW_RETURNS.csv');U=U[U.window.isin(['二次底部至行业峰值','重返前高至行业峰值'])]
stocks=U.symbol.unique().tolist()
hist=pd.read_parquet('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet',columns=['symbol','trade_date','close'],filters=[('symbol','in',stocks),('trade_date','>=',pd.Timestamp('2024-01-01')),('trade_date','<=',pd.Timestamp('2026-05-15'))]).set_index(['symbol','trade_date']).close
assert not hist.index.duplicated().any()
cache={};frames={};checks=[];adjusterrors=[];switches=[];rawrows=[]
def rawget(path,st,dt):
 if path.endswith('daily_bars.parquet'):return hist.get((st,dt),np.nan)
 if path not in cache:
  a=json.load(open(path)); bars=a.get('bars',[])
  cache[path]={pd.Timestamp(b['date']):float(b['close']) for b in bars}
 return cache[path].get(dt,np.nan)
for st in stocks:
 q=pd.read_parquet(next(p for p in H[st]['source_identity'] if p.endswith('/signal.parquet'))).loc['2024-01-01':'2026-10-22']
 frames[st]=q
 good=q.close.notna()&q.raw_close.notna()&q.adjustment_factor.notna()
 adjusterrors.append(float((q.loc[good,'close']-q.loc[good,'raw_close']*q.loc[good,'adjustment_factor']).abs().max()))
 changed=q.source_kind.ne(q.source_kind.shift())&q.source_kind.notna()&q.source_kind.shift().notna()
 for dt in q.index[changed]:
  loc=q.index.get_loc(dt)
  if loc<1:continue
  prev=q.index[loc-1];row=q.loc[dt];old=q.loc[prev];new_path=row.source_path
  new_prev=rawget(new_path,st,prev);new_cur=rawget(new_path,st,dt)
  switches.append({'symbol':st,'prev_date':str(prev.date()),'date':str(dt.date()),'old_kind':old.source_kind,'new_kind':row.source_kind,'old_raw':old.raw_close,'new_raw':row.raw_close,'new_provider_prev_raw':new_prev,'new_provider_current_raw':new_cur,'overlap_prev_diff':new_prev-old.raw_close,'new_raw_diff':new_cur-row.raw_close,'factor_ratio':row.adjustment_factor/old.adjustment_factor,'adj_change_pct':100*(row.close/old.close-1)})
for r in U.to_dict('records'):
 if not r['endpoint_known']:continue
 st=r['symbol'];q=frames[st];a=pd.Timestamp(r['start']);z=pd.Timestamp(r['end'])
 x=q.loc[a];y=q.loc[z];rr={**r,'raw_start':x.raw_close,'raw_end':y.raw_close,'raw_return_pct':100*(y.raw_close/x.raw_close-1),'factor_ratio':y.adjustment_factor/x.adjustment_factor}
 rawrows.append(rr)
 for role,dt in [('start',a),('end',z)]:
  v=q.loc[dt];raw=rawget(v.source_path,st,dt)
  checks.append({'sector':r['sector'],'window':r['window'],'symbol':st,'role':role,'date':str(dt.date()),'signal_raw':v.raw_close,'original_raw':raw,'diff':raw-v.raw_close,'source_kind':v.source_kind,'source_path':v.source_path})
A=pd.DataFrame(checks);S=pd.DataFrame(switches);V=pd.DataFrame(rawrows)
C=pd.read_csv(O.parent/'SIX_INDEPENDENT_CYCLES.csv');peaks=[]
for r in C[C.sid.str.startswith('URFI')].to_dict('records'):
 q=pd.read_parquet(next(p for p in H[r['sid']]['source_identity'] if p.endswith('/signal.parquet')))
 good=q.observed_bar.fillna(False)&q.price_eligible.fillna(False)&~q.source_invalid.fillna(True)&~q.synthetic_event_bar.fillna(True)
 s=q.loc[r['secondary_base']:r['observation_end'],'close'].where(good)
 peaks.append({'sector':r['sid'],'frozen_peak':r['main_peak'],'recomputed_peak':str(s.idxmax().date()),'peak_match':str(s.idxmax().date())==r['main_peak'],'max_close_raw_difference':float((q.close-q.raw_close).abs().max())})
P=pd.DataFrame(peaks)
print('RAW_ENDPOINTS',len(A),'missing',int(A.original_raw.isna().sum()),'maxdiff',A['diff'].abs().max(),'mismatch_n',int((A['diff'].abs()>1e-8).sum()))
print('ADJ_IDENTITY_MAXERR',max(adjusterrors))
print('PEAKS',P.to_dict('records'))
print('SWITCHES',len(S),'newmissing',int(S.new_provider_current_raw.isna().sum()),'oldoverlapmissing',int(S.new_provider_prev_raw.isna().sum()),'newmaxdiff',S.new_raw_diff.abs().max(),'overlapmaxdiff',S.overlap_prev_diff.abs().max())
print('SWITCH_DIFFS');print(S[S.overlap_prev_diff.abs()>1e-8].to_string(index=False))
print('SWITCH_LARGEST');print(S.reindex(S.adj_change_pct.abs().sort_values(ascending=False).index).head(10).to_string(index=False))
print('RAW_SUMMARY');print(V.groupby(['industry','window']).agg(n=('symbol','size'),raw_median=('raw_return_pct','median'),adjusted_median=('return_pct','median'),raw_positive=('raw_return_pct',lambda x:int((x>0).sum()))).to_string())
qa={'raw_endpoint_checks':len(A),'raw_endpoint_missing':int(A.original_raw.isna().sum()),'raw_max_abs_difference':float(A['diff'].abs().max()),'adjusted_identity_max_abs_error':max(adjusterrors),'industry_peak_dates_all_match':bool(P.peak_match.all()),'source_switch_n':len(S),'source_switch_new_price_missing':int(S.new_provider_current_raw.isna().sum()),'source_switch_overlap_missing':int(S.new_provider_prev_raw.isna().sum()),'source_switch_current_maxdiff':float(S.new_raw_diff.abs().max()),'source_switch_overlap_maxdiff':float(S.overlap_prev_diff.abs().max()),'scope':'separate raw-data path and exact dates; not independent exchange certification or PIT corporate-action audit'}
import sys
if '--save' in sys.argv:
 A.to_csv(O/'RAW_ENDPOINT_SOURCE_CHECK.csv',index=False);S.to_csv(O/'RAW_SOURCE_SEAMS.csv',index=False);V.to_csv(O/'RAW_VS_ADJUSTED_MEMBER_RETURNS.csv',index=False);P.to_csv(O/'INDEPENDENT_PEAK_DATE_CHECK.csv',index=False);json.dump(qa,open(O/'RAW_SOURCE_QA.json','w'),ensure_ascii=False,indent=2)
