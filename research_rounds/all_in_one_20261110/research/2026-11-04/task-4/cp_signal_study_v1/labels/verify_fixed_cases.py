"""Small independent direct-slice arithmetic/source audit; no full label rerun."""
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
L=pd.read_parquet(O/'LABELS.parquet');B=pd.read_csv(O/'SOURCE_BINDINGS.csv',dtype={'sid':str}).set_index('sid')
cases=[('first_original_event',L.sort_values(['date','sid']).iloc[0]),
 ('holiday_crossing_hytera',L[(L.sid=='002583.SZ')&(L.date=='2024-09-30')].iloc[0]),
 ('first_june30_signal',L[L.date=='2026-06-30'].sort_values('sid').iloc[0]),
 ('longest_span_boundary_audit',L.sort_values(['calendar_span_days','date','sid'],ascending=[False,True,True]).iloc[0]),
 ('first_all_future_closes_below_signal',L[(L.mfe20_log==0)&(L.future_max20_log_unclipped<0)].sort_values(['date','sid']).iloc[0]),
 ('first_existing_source_row_skipped',L[L.skipped_source_rows>0].sort_values(['date','sid']).iloc[0]),
 ('first_missing_next_common_session',L[~L.next_session_source_row_present].sort_values(['date','sid']).iloc[0])]
result=[]
for why,r in cases:
 path=Path(B.loc[r.sid,'prepared_signal_ref']);f=pd.read_parquet(path).loc[:'2026-10-22'];t=pd.Timestamp(r.date);base=f.loc[t]
 future=f.loc[f.index>t].copy();boundary=future.segment_id.ne(base.segment_id)
 if boundary.any():future=future.loc[future.index<future.index[boundary][0]]
 mask=(future.observed_bar.eq(True)&future.price_eligible.eq(True)&future.synthetic_event_bar.eq(False)&future.source_invalid.eq(False)&future.close.gt(0)&np.isfinite(future.close)&future.volume.gt(0)&np.isfinite(future.volume))
 target=future.loc[mask].head(20)
 assert len(target)==20 and target.index[-1].strftime('%Y-%m-%d')==r.label_end
 vals=[math.log(float(v)/float(base.close)) for v in target.close]
 independently={'mfe20_log':max([0.]+vals),'mae20_log':min([0.]+vals),'final20_log':vals[-1]}
 err={k:float(r[k])-v for k,v in independently.items()};assert max(abs(v) for v in err.values())<1e-12
 result.append({'case_selection':why,'sid':r.sid,'date':r.date,'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
  'signal_close':float(base.close),'label_end':r.label_end,'calendar_span_days':int(r.calendar_span_days),
  'future_dates':[x.strftime('%Y-%m-%d') for x in target.index],'future_close':target.close.tolist(),
  'independent_loglabels':independently,'stored_minus_independent':err,'next_session_source_row_present':bool(r.next_session_source_row_present),
  'scope':'Boundary/arithmetic audit only; cases selected to inspect source mechanics, not feature selection or performance.'})
checks=[]
for sid,g in L[L.nonoverlap20].groupby('sid'):
 g=g.sort_values('date');assert (g.date.iloc[1:].to_numpy()>g.label_end.iloc[:-1].to_numpy()).all()
assert len(L)==99031 and L.label_valid.all() and L.actual_days.eq(20).all()
output={'sample_cases':result,'global_invariants':{'events':len(L),'all_valid_complete20':True,'nonoverlap_no_shared_followup_intervals':True,
 'canonical_ID_missing_retained':int(L.canonical_receipt_id.isna().sum())},'new_full_label_runs':0,'new_features_or_models_or_accounts':0}
(O/'FIXED_CASE_ARITHMETIC_AUDIT.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'cases':len(result),'max_abs_difference':max(abs(v) for r in result for v in r['stored_minus_independent'].values()),'global_invariants':output['global_invariants']},indent=2))
