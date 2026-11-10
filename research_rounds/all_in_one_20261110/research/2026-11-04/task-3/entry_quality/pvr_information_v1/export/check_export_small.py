"""Exporter schema and date-alignment small checks; no label/financial run."""
from pathlib import Path
import importlib.util,json,time,hashlib
import numpy as np,pandas as pd,pyarrow as pa
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('export_pvr_features_small',O/'export_features.py');X=importlib.util.module_from_spec(spec);spec.loader.exec_module(X)
def main():
 start=time.monotonic();src={};sm=X.load(X.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json',src);im=X.load(X.W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json',src);meta=X.load('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json',src);m=next(x for x in sm if x['symbol']=='000001.SZ');sector=meta['000001.SZ']['sector_id'];ind=next(x for x in im if x['series']==sector);dates,windows,cals=X.calendars(src)
 a=X.read_signal(m,src);b=X.read_signal(ind,src);t=time.monotonic();af=X.API.compute_features(a);bf=X.API.compute_features(b);compute=time.monotonic()-t;f,q=X.build_stock('000001.SZ',sector,a,af,dates,windows,b,bf)
 ft=pa.Table.from_pandas(f,schema=X.feature_schema(),preserve_index=False,safe=True);qt=pa.Table.from_pandas(q,schema=X.QUOTE_SCHEMA,preserve_index=False,safe=True);assert ft.num_rows==qt.num_rows==968;assert len(ft.schema)==49 and len(qt.schema)==8
 queries,qcounts=X.ranklog_queries(src);counter=__import__('collections').Counter();X.check_scores('000001.SZ',f,queries,counter)
 # A missing industry observation creates a genuinely different own20 anchor.
 idx=pd.bdate_range('2020-01-01',periods=130);sig=pd.DataFrame(dict(open=np.exp(np.arange(130)*.005),close=np.exp(np.arange(130)*.005),high=np.exp(np.arange(130)*.005)*1.01,low=np.exp(np.arange(130)*.005)*.99,amount=np.full(130,1000.),segment_id=np.zeros(130,dtype=int),observed_bar=True,synthetic_event_bar=False),index=idx)
 ss=X.API.compute_features(sig);gsig=sig.drop(idx[-10]);gg=X.API.compute_features(gsig);last=pd.DatetimeIndex([idx[-1]]);s0,_=X.standardized(ss,last);aligned,relative,status=X.aligned_sector(s0,gsig,gg,last)
 anchor=s0.return20_anchor_day.iloc[0];expected=gsig.loc[last[0],'close']/gsig.loc[anchor,'close']-1;own=gg.loc[last[0],'return20'];assert expected!=own and aligned[0]==expected and relative[0]==s0.return20.iloc[0]-expected and status.iloc[0]=='KNOWN'
 # A missing exact stock anchor must be UNKNOWN, never nearest-date fill.
 bad=gsig.drop(anchor);badf=X.API.compute_features(bad);al,re,st=X.aligned_sector(s0,bad,badf,last);assert np.isnan(al[0])and np.isnan(re[0])and st.iloc[0]=='UNKNOWN_SECTOR_NO_EXACT_ENDPOINT'
 # Present invalid industry row creates a new preparation block; endpoints
 # cannot be bridged merely because both price observations are positive.
 blocked=gsig.copy();blocked.loc[idx[-5],'amount']=0;blockf=X.API.compute_features(blocked);al,re,st=X.aligned_sector(s0,blocked,blockf,last);assert np.isnan(al[0])and st.iloc[0]=='UNKNOWN_SECTOR_BLOCK_TRANSITION'
 # Completely absent stock history still produces every requested grid row.
 empty=a.iloc[:0];ef=X.API.compute_features(empty);fe,qe=X.build_stock('EMPTY',sector,empty,ef,dates,windows,b,bf);assert len(fe)==len(qe)==968 and not fe.stock_source_row_present.any()and fe.pvr_status.eq('NO_EXACT_SOURCE_OBSERVATION').all()and not qe.valid.any()and not qe.observed.any();pa.Table.from_pandas(fe,schema=X.feature_schema(),preserve_index=False,safe=True)
 result=dict(status='PASS_SMALL_SCHEMA_EXACT_ANCHOR_AND_EMPTY_GRID',feature_source_sha256=X.sha(X.F),exporter_sha256=X.sha(O/'export_features.py'),features_columns=len(ft.schema),quote_columns=len(qt.schema),real_sample_stock='000001.SZ',real_sample_sector=sector,real_sample_stock_rows=len(a),real_sample_sector_rows=len(b),stock_plus_industry_compute_seconds=compute,real_sample_ranklog_checks=dict(counter),aligned_interval_counterexample=dict(stock_anchor=str(anchor.date()),aligned_sector_return=expected,independent_sector_own20_return=own),missing_anchor_UNKNOWN=True,industry_block_transition_UNKNOWN=True,empty_symbol_full_grid=True,no_labels=True,no_accounts=True,elapsed_seconds=time.monotonic()-start,source_sha256=src)
 X.save(O/'SMALL_SAMPLE_EXPORT_CHECKS.json',result);X.save(O/'OUTPUT_SCHEMA.json',X.schema_description());print(json.dumps({k:result[k]for k in ['status','features_columns','quote_columns','stock_plus_industry_compute_seconds','real_sample_ranklog_checks','elapsed_seconds']},ensure_ascii=False))
if __name__=='__main__':main()
