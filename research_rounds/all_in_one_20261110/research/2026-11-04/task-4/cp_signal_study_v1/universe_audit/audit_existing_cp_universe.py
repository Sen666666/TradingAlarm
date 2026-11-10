"""Read saved CP flags/canonical receipts/prices only. No feature, label, model or account call."""
from pathlib import Path
import pandas as pd,numpy as np,json,time,hashlib,csv,collections
OUT=Path(__file__).resolve().parent
BASE=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
U=BASE/'universe-cp1-inputs-20261031'
BUNDLE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2')
CAN=[BASE/'2022-normal-reference-20261031/inputs/MANIFEST.json',BASE/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')]
START,END=pd.Timestamp('2022-01-01'),pd.Timestamp('2026-06-30')
begun=time.monotonic();sha={}
def js(p):
 p=Path(p);b=p.read_bytes();sha[str(p)]=hashlib.sha256(b).hexdigest();return json.loads(b)
def date(x):return None if pd.isna(x) else pd.Timestamp(x).strftime('%Y-%m-%d')
sm=js(U/'STOCK_MANIFEST.json');bundle=js(BUNDLE/'input-manifest.json');meta=js(BUNDLE/'metadata.json');ser={x['series_id']:x for x in bundle['series']};cms=[{x['sid']:x for x in js(p) if not x['industry']} for p in CAN]
events=[];cover=[];refs=[];errors=[];schema=collections.Counter();fieldpresent=collections.Counter();canon_only=[]
for n,x in enumerate(sm):
 sid=x['symbol'];paths=x['refs'];d=pd.read_parquet(paths['CP1'],columns=['receipt','ready']);f=pd.read_parquet(paths['facts']);rawp=Path(ser[sid]['raw']['path']);raw=pd.read_parquet(rawp);rawcols=set(raw.columns)
 schema['|'.join(sorted(rawcols))]+=1
 for k in ['open','volume','amount','price_eligible','source_invalid','observed_bar','synthetic_event_bar','suspend_status','is_suspended','is_trading','limit_up','limit_down','quality_status']:
  fieldpresent[k]+=int(k in rawcols)
 rdcol='trade_date' if 'trade_date' in rawcols else None
 raw.index=pd.to_datetime(raw[rdcol]) if rdcol else pd.to_datetime(raw.index);raw=raw.sort_index()
 for label,t in [('CP',d),('facts',f),('raw',raw)]:
  if not t.index.is_unique:errors.append({'sid':sid,'error':'duplicate_dates','table':label})
 flag=(d['receipt']==True);cut=d.loc[START:END];signal_dates=cut.index[cut['receipt']==True]
 canonical={}
 for k,c in enumerate(cms):
  if sid not in c:errors.append({'sid':sid,'error':'missing_canonical_manifest_sid','year':2022+k});continue
  r=c[sid];p=Path(r['output_path']);rr=js(p)
  # Existing native loader checks exact original_output mapping; permit full mapping path aliases only after key hashes match.
  source_cp_sha=x.get('output_sha256',{}).get(paths['CP1'])
  original_cp_shas=[r.get('original_output_sha256',{}).get(r['refs']['CP1'])]
  if source_cp_sha and source_cp_sha not in original_cp_shas:errors.append({'sid':sid,'error':'canonical_CP_source_hash_not_same','year':2022+k})
  if sha[str(p)]!=r['output_sha256']:errors.append({'sid':sid,'error':'canonical_output_hash_mismatch','year':2022+k})
  for rr0 in rr:
   dt=rr0['confirmed_day']
   if dt in canonical and canonical[dt][0]['receipt_id']!=rr0['receipt_id']:errors.append({'sid':sid,'date':dt,'error':'conflicting_canonical_ids'})
   canonical[dt]=(rr0,str(p),'saved_canonical_'+str(2022+k))
 p=Path(paths['receipts'])
 for rr in js(p):canonical[rr['confirmed_day']]=(rr,str(p),'manifest_refs_receipts')
 close=pd.to_numeric(raw['close'],errors='coerce');valid=np.isfinite(close.to_numpy(dtype=float))&(close.to_numpy(dtype=float)>0)
 for k,want in [('price_eligible',True),('observed_bar',True),('source_invalid',False),('synthetic_event_bar',False)]:
  if k in raw:valid&=raw[k].fillna(not want).eq(want).to_numpy()
 volume=pd.to_numeric(raw['volume'],errors='coerce') if 'volume' in raw else pd.Series(np.nan,index=raw.index)
 positive=valid&np.isfinite(volume.to_numpy(dtype=float))&(volume.to_numpy(dtype=float)>0)
 gooddates=raw.index[valid];positivedates=raw.index[positive]
 fc=pd.to_numeric(f['close'],errors='coerce');fvalid=np.isfinite(fc.to_numpy(dtype=float))&(fc.to_numpy(dtype=float)>0);fgood=f.index[fvalid]
 source={'source_ref_id':sid,'sid':sid,'CP1_ref':paths['CP1'],'CP1_manifest_sha256':x.get('output_sha256',{}).get(paths['CP1']),'CP1_input_ref':paths.get('CP1_input'),'facts_ref':paths['facts'],'facts_manifest_sha256':x.get('output_sha256',{}).get(paths['facts']),'manifest_receipts_ref':paths['receipts'],'raw_ref':str(rawp),'raw_bundle_sha256':ser[sid]['raw'].get('sha256'),'stock_manifest_ref':str(U/'STOCK_MANIFEST.json'),'static_metadata_ref':str(BUNDLE/'metadata.json'),'static_scope_date':bundle['scope_date'],'static_basis':bundle['research_basis'],'canonical_2022_ref':cms[0].get(sid,{}).get('output_path'),'canonical_2023_ref':cms[1].get(sid,{}).get('output_path'),'canonical_2024_ref':cms[2].get(sid,{}).get('output_path')};refs.append(source)
 c={'sid':sid,'manifest_status':x['status'],'CP_rows':len(d),'CP_first':date(d.index.min()),'CP_last':date(d.index.max()),'facts_rows':len(f),'facts_first':date(f.index.min()),'facts_last':date(f.index.max()),'raw_rows':len(raw),'raw_first':date(raw.index.min()),'raw_last':date(raw.index.max()),'scope_CP_count':len(signal_dates),'scope_CP_unready_count':int((cut.receipt.eq(True)&~cut.ready.eq(True)).sum()),'scope_facts_invalid_close_rows':int((~pd.Series(fvalid,index=f.index).loc[START:END]).sum()),'scope_raw_rows':len(raw.loc[START:END]),'scope_raw_invalid_or_unobserved_rows':int((~pd.Series(valid,index=raw.index).loc[START:END]).sum()),'scope_raw_volume_nonpositive_or_missing_rows':int((~pd.Series(np.isfinite(volume.to_numpy(dtype=float))&(volume.to_numpy(dtype=float)>0),index=raw.index).loc[START:END]).sum()),'original_CP_facts_index_equal':d.index.equals(f.index),'raw_columns':'|'.join(sorted(rawcols))};cover.append(c)
 for t in signal_dates:
  day=date(t);can=canonical.get(day);fr=f.loc[t] if t in f.index else None;rr=raw.loc[t] if t in raw.index else None
  e={'sid':sid,'date':day,'canonical_receipt_id':can[0]['receipt_id'] if can else '', 'canonical_receipt_status':can[2] if can else 'NOT_SAVED_IN_CHECKED_RECEIPT_EXPORTS','canonical_receipt_source_ref':can[1] if can else '', 'original_CP_flag':True,'original_CP_ready':bool(d.at[t,'ready']),'source_ref_id':sid,'sector_static':meta.get(sid,{}).get('sector_id'),'industry_static':meta.get(sid,{}).get('industry'),'static_mapping_scope_date':bundle['scope_date'],'mapping_PIT_verified':False,'segment':None if fr is None else int(fr['segment_id']),'canonical_source_segment':can[0].get('source_segment') if can else None,'facts_price_present':bool(fr is not None and pd.notna(fr['close']) and np.isfinite(fr['close']) and fr['close']>0),'facts_raw_close_present':bool(fr is not None and pd.notna(fr.get('raw_close')) and np.isfinite(fr['raw_close']) and fr['raw_close']>0),'raw_price_row_present':rr is not None,'raw_price_eligible_observed':bool(t in gooddates),'raw_positive_volume':bool(t in positivedates),'raw_open_positive_present':bool(rr is not None and pd.notna(rr.get('open')) and np.isfinite(rr['open']) and rr['open']>0),'future_saved_facts_valid_observations_capped20':min(20,len(fgood)-fgood.searchsorted(t,side='right')),'future_saved_raw_eligible_observations_capped20':min(20,len(gooddates)-gooddates.searchsorted(t,side='right')),'future_saved_raw_positive_volume_observations_capped20':min(20,len(positivedates)-positivedates.searchsorted(t,side='right')),'raw_last_available_date':c['raw_last'],'facts_last_available_date':c['facts_last'],'execution_proven':False}
  if can and can[0].get('source_segment')!=str(e['segment']):errors.append({'sid':sid,'date':day,'error':'canonical_source_segment_differs_facts'})
  events.append(e)
 for day,can in canonical.items():
  if '2022-01-01'<=day<='2026-06-30' and pd.Timestamp(day) not in signal_dates:canon_only.append({'sid':sid,'date':day,'receipt_id':can[0]['receipt_id'],'source':can[1]})
 if (n+1)%300==0:print('PROGRESS',n+1,'events',len(events),'seconds',round(time.monotonic()-begun,2),flush=True)
E=pd.DataFrame(events).sort_values(['date','sid']);C=pd.DataFrame(cover);R=pd.DataFrame(refs)
E.to_csv(OUT/'CP_EVENT_INDEX_2022_2026H1.csv',index=False);C.to_csv(OUT/'STOCK_PRICE_COVERAGE.csv',index=False);R.to_csv(OUT/'SOURCE_REFS.csv',index=False)
for by,fn in [('year','COUNTS_BY_YEAR.csv'),('month','COUNTS_BY_MONTH.csv')]:
 e=E.assign(period=E.date.str.slice(0,4 if by=='year' else 7));s=e.groupby('period').agg(CP_count=('sid','size'),distinct_stocks=('sid','nunique'),missing_canonical_ID=('canonical_receipt_id',lambda x:int(x.eq('').sum())),missing_facts_price=('facts_price_present',lambda x:int((~x).sum())),raw_price_unavailable_or_ineligible=('raw_price_eligible_observed',lambda x:int((~x).sum())),raw_positive_volume_unproven=('raw_positive_volume',lambda x:int((~x).sum())),facts_future_lt20=('future_saved_facts_valid_observations_capped20',lambda x:int((x<20).sum())),raw_future_lt20=('future_saved_raw_eligible_observations_capped20',lambda x:int((x<20).sum())),raw_positive_volume_future_lt20=('future_saved_raw_positive_volume_observations_capped20',lambda x:int((x<20).sum())));s.to_csv(OUT/fn)
summary={'stock_manifest_entries':len(sm),'status_counts':dict(collections.Counter(x['status'] for x in sm)),'events':len(E),'distinct_stocks_with_CP':int(E.sid.nunique()),'scope':['2022-01-01','2026-06-30'],'canonical_ID_missing':int(E.canonical_receipt_id.eq('').sum()),'scope_original_CP_unready_count':int((~E.original_CP_ready).sum()),'missing_facts_price_CP_events':int((~E.facts_price_present).sum()),'raw_price_ineligible_CP_events':int((~E.raw_price_eligible_observed).sum()),'raw_positive_volume_unproven_CP_events':int((~E.raw_positive_volume).sum()),'raw_open_unavailable_CP_events':int((~E.raw_open_positive_present).sum()),'facts_future_lt20_events':int((E.future_saved_facts_valid_observations_capped20<20).sum()),'raw_future_lt20_events':int((E.future_saved_raw_eligible_observations_capped20<20).sum()),'raw_positive_volume_future_lt20_events':int((E.future_saved_raw_positive_volume_observations_capped20<20).sum()),'source_raw_columns_present_in_n_stock_files':dict(fieldpresent),'source_raw_schema_groups':dict(schema),'CP_facts_index_mismatch_stocks':int((~C.original_CP_facts_index_equal).sum()),'canonical_only_without_original_CP_flag_count':len(canon_only),'error_count':len(errors),'account_runs':0,'numeric_models_recomputed':0,'new_features_computed':0,'labels_computed':0,'seconds':time.monotonic()-begun,'mapping_PIT_verified':False,'pool_PIT_verified':False,'static_scope_date':bundle['scope_date'],'static_research_basis':bundle['research_basis']}
(OUT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(OUT/'AUDIT_ERRORS.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2)+'\n');(OUT/'CANONICAL_ROWS_WITHOUT_CP_FLAG.json').write_text(json.dumps(canon_only,ensure_ascii=False,indent=2)+'\n');sha[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(OUT/'READ_SOURCE_SHA256.json').write_text(json.dumps(sha,ensure_ascii=False,indent=2)+'\n')
print('SUMMARY',json.dumps(summary,ensure_ascii=False),flush=True);print((OUT/'COUNTS_BY_YEAR.csv').read_text(),flush=True)
