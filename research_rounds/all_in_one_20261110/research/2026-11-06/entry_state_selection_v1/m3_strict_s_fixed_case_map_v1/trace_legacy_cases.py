import pathlib,json,hashlib,pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'m3_strict_s_fixed_case_map_v1';P=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';L=R/'m3_ab_shared_probe_v1/indexed_execution_v1/cohort_2024_924'
D=pd.read_csv(O/'FIXED_20_CASES.csv');K=pd.read_parquet(P/'COMMON_K_COMPARISON.parquet');K.day=K.day.astype(str)
MR=pd.read_parquet(P/'RIGHT3.parquet');MK=pd.read_parquet(P/'KNOWN3.parquet');MU=pd.read_parquet(P/'MU5.parquet')
E=pd.read_csv(R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv')
DEC=json.load(open(L/'DECISIONS.json'));RA=json.load(open(L/'RANKING_AUDIT.json'))
H={x['sid']:x for x in json.load(open(R/'account_comparison_continuous_v1/inputs/H1_MANIFEST.json'))}
rows=[];details=[];sources={}
for p in [O/'FIXED_20_CASES.csv',P/'COMMON_K_COMPARISON.parquet',P/'RIGHT3.parquet',P/'KNOWN3.parquet',P/'MU5.parquet',R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv',L/'DECISIONS.json',L/'RANKING_AUDIT.json']:
 sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
for c in D.to_dict('records'):
 t=c['signal_close_date'];day=pd.Timestamp(t);st=c['symbol'];sector=c['sector']
 k=K[(K.day==t)&(K.sector==sector)]
 scoped=('2024-09-02'<=t<='2024-12-31') or (sector=='URFI881121' and '2026-01-01'<=t<='2026-06-30')
 e=E[(E.day==t)&(E.sid==st)] if scoped else E.head(0)
 decisions=[d for d in DEC if str(d.get('day',''))[:10]==t and d.get('sid')==st]
 ranks=[d for d in RA if str(d.get('day',''))[:10]==t and d.get('sid')==st]
 r={**c,'M3_source_available':day in MR.index,'stock_M3':bool(MR.at[day,st]) if day in MR.index else None,'stock_M3_known':bool(MK.at[day,st]) if day in MK.index else None,'legacy_birth_window_covers_case':scoped,'legacy_event_type':'|'.join(e.event_type.tolist()) if scoped else 'SOURCE_WINDOW_NOT_COVERED','legacy_no_new_birth':bool(len(e)==0) if scoped else None,'legacy_shared_account_covers_birth_window':'2024-09-02'<=t<='2024-12-31','legacy_decision':'|'.join(d.get('decision','') for d in decisions),'legacy_queue_rank':'|'.join(str(d.get('queue_rank','')) for d in decisions),'legacy_original_feasible_rank':'|'.join(str(d.get('original_feasible_rank','')) for d in ranks),'B0_new_signal_status':'PENDING_OWNER_PREFLIGHT','B1_new_signal_status':'PENDING_OWNER_PREFLIGHT'}
 if len(k):
  kr=k.iloc[0];r.update({'sector_N':int(kr.N),'sector_common_known_K':int(kr.K),'sector_unknown_U':int(kr.U),'sector_M3_n':int(kr.M3_n),'sector_M3_delta3':float(kr.M3_delta3),'sector_M3_candidate':int(kr.M3_candidate)})
 if day in MU.index:
  loc=MU.index.get_loc(day);d3=MU.index[max(0,loc-2):loc+1]
  r['mu5_last3_dates']='|'.join(x.strftime('%Y-%m-%d') for x in d3)
  r['mu5_last3_values']='|'.join(str(MU.at[x,st]) for x in d3)
 if len(e):
  er=e.iloc[0];r.update({'legacy_previous_sector_state':er.previous_sector_state,'legacy_previous_stock_state':er.previous_stock_state,'legacy_I_qualified':er.I_qualified,'legacy_PVR_known':er.PVR_known,'legacy_PVR_state':er.PVR_state,'legacy_PVR_score':er.PVR_score})
 factp=next(p for p in H[st]['input_identity'] if '/facts/' in p or '/full-facts/' in p)
 f=pd.read_parquet(factp);sources[factp]=hashlib.sha256(pathlib.Path(factp).read_bytes()).hexdigest();assert sources[factp]==H[st]['input_identity'][factp]
 if day in f.index:
  for col in ['e0_target','e0_floor','i_target','i_floor','e0_ready','g_grade','g_ready','close','raw_close','factor']:
   r['old_fact_'+col]=f.at[day,col]
 r['source_clock_limit']='Only stored values at signal CLOSE; derived histories <=t, but current membership/adjustment NON-PIT'
 rows.append(r);details.append({'case_id':c['case_id'],'legacy_decisions':decisions,'legacy_ranking':ranks})
Q=pd.DataFrame(rows);Q.to_csv(O/'LEGACY_20_POINT_SNAPSHOT.csv',index=False)
json.dump(details,open(O/'LEGACY_ACCOUNT_CASE_DETAILS.json','w'),ensure_ascii=False,indent=2)
json.dump(sources,open(O/'SNAPSHOT_SOURCE_HASHES.json','w'),ensure_ascii=False,indent=2)
for p,h in sources.items():assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h
qa={'n_cases':len(Q),'M3_known_date_cases':int(Q.M3_source_available.sum()),'missing_M3_date_cases':Q.loc[~Q.M3_source_available,'case_id'].tolist(),'legacy_birth_source_covers':int(Q.legacy_birth_window_covers_case.sum()),'legacy_shared_birth_window_covers':int(Q.legacy_shared_account_covers_birth_window.sum()),'new_B0_B1_computed':False,'new_funds_or_economics_computed':False,'sources_unchanged':True}
json.dump(qa,open(O/'SNAPSHOT_QA.json','w'),ensure_ascii=False,indent=2)
print(qa)
print(Q[['case_id','symbol','signal_close_date','stock_M3','sector_M3_candidate','sector_M3_n','sector_common_known_K','legacy_birth_window_covers_case','legacy_event_type','legacy_decision']].to_string(index=False))
