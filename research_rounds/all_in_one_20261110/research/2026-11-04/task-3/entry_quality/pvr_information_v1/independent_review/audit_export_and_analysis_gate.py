"""Thin existing-output gate; two real symbols only, zero labels/accounts."""
from pathlib import Path
import hashlib,importlib.util,json,signal,time,io
import numpy as np,pandas as pd
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent;P=O.parent;XDIR=P/'export'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 started=time.monotonic();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('thin audit60s')));signal.setitimer(signal.ITIMER_REAL,60)
 X=module('pvr_export_thin_gate',XDIR/'export_features.py');mf=load(XDIR/'FEATURE_MANIFEST_PRE_LABEL.json');stop=load(XDIR/'EXPORT_STOPPED.json');seal=load(XDIR/'COMPLETED_EXPORT_SEAL_AUDIT.json')
 assert mf['status']=='COMPLETE_PURE_FEATURE_EXPORT_BEFORE_ANY_LABEL_OR_PNL'
 assert mf['no_future_labels'] and mf['no_original_PnL_imported'] and mf['new_accounts']==0
 assert stop['progress']['stage']=='seal_pre_label_manifest' and stop['progress']['completed_stocks']==1709 and stop['progress']['completed_industries']==90
 assert stop['counts']['empty_signal_symbols']==0
 assert mf['counts']['empty_stock_full_history_signals']==mf['counts']['empty_industry_full_history_signals']==0
 assert mf['counts']['ranklog_queries_checked']==133713 and mf['counts']['ranklog_ready_bitexact']==133542 and mf['counts']['ranklog_UNKNOWN_exact']==171
 source={};footers={}
 for n,width in [('features.parquet',49),('reference_quotes.parquet',8)]:
  p=XDIR/n;f=pq.ParquetFile(p);assert f.metadata.num_rows==1654312 and f.num_row_groups==1709 and len(f.schema_arrow)==width
  assert all(f.metadata.row_group(i).num_rows==968 for i in range(1709))
  h=sha(p);assert mf['outputs'][n]['sha256']==h;source[str(p)]=h
  footers[n]=dict(rows=f.metadata.num_rows,rowgroups=f.num_row_groups,columns=width,all_groups_rows=968)
 sm=load(X.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');im=load(X.W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json');meta=load('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
 ids=[r['symbol']for r in sm];industries={r['series']:r for r in im};pf=pq.ParquetFile(XDIR/'features.parquet');qf=pq.ParquetFile(XDIR/'reference_quotes.parquet')
 dates=pd.DatetimeIndex(sum([mf['calendars'][w]for w in ['2022_2024','strong']],[]));windows=sum([[w]*len(mf['calendars'][w])for w in ['2022_2024','strong']],[])
 samples=[]
 for sid in ['000620.SZ','301319.SZ']:
  rec=sm[ids.index(sid)];sector=meta[sid]['sector_id'];sig=X.read_signal(rec,source);g=X.read_signal(industries[sector],source);full=X.API.compute_features(sig);gf=X.API.compute_features(g)
  expected,eq=X.build_stock(sid,sector,sig,full,dates,windows,g,gf);actual=pf.read_row_group(ids.index(sid)).to_pandas();aq=qf.read_row_group(ids.index(sid)).to_pandas()
  # Check serialization/reindexing of every49+8 columns, not a whole-export rerun.
  normalized=X.pa.Table.from_pandas(expected,schema=X.feature_schema(),preserve_index=False,safe=True).to_pandas()
  normalized_q=X.pa.Table.from_pandas(eq,schema=X.QUOTE_SCHEMA,preserve_index=False,safe=True).to_pandas()
  for k in normalized.columns:
   if X.feature_schema().field(k).type==X.pa.bool_():normalized[k]=normalized[k].astype('boolean');actual[k]=actual[k].astype('boolean')
  pd.testing.assert_frame_equal(normalized[actual.columns],actual,check_dtype=False,check_exact=True)
  pd.testing.assert_frame_equal(normalized_q[aq.columns],aq,check_dtype=False,check_exact=True)
  scalar=0
  for _,r in actual.loc[actual.relative_return20_status.eq('KNOWN')].iloc[::73].iterrows():
   a=pd.Timestamp(r.return20_anchor_day);t=pd.Timestamp(r.day);assert pd.Timestamp(r.aligned_sector_anchor_day)==a
   native=float(g.loc[t,'close'])/float(g.loc[a,'close'])-1
   assert np.isclose(native,r.aligned_sector_return_on_stock20_interval,atol=1e-14,rtol=1e-13)
   assert np.isclose(r.return20-native,r.relative_return20,atol=1e-14,rtol=1e-13);scalar+=1
  samples.append(dict(sid=sid,sector=sector,feature_cells=968*49,quote_cells=968*8,independent_sector_anchor_checks=scalar))
 # Separate full-history nonempty source files from no observations in these windows.
 absent=mf['empty_source_domain_census']['no_stock_source_row_on_968_export_dates'];assert len(absent)==22
 for sid in absent:
  r=pf.read_row_group(ids.index(sid),columns=['stock_source_row_present','pvr_status']).to_pandas();assert not r.stock_source_row_present.any() and r.pvr_status.eq('NO_EXACT_SOURCE_OBSERVATION').all()
 primary=load(O/'PRIMARY_MOTHER_AND_EVENT_AUDIT.json');clock=load(O/'LABEL_CLOCK_FLAGS_V2_SMALL_AUDIT.json');prefix=load(O/'PRE_LABEL_CLARIFICATION_AND_SMALL_PREFIX_ACCEPTANCE.json')
 assert primary['status'].startswith('PASS') and clock['status'].startswith('PASS') and prefix['status'].startswith('PASS')
 fix=load(P/'analysis/TECHNICAL_PARSE_FIX_AND_RETRY_FREEZE.json');assert fix['status'].startswith('PASS')
 assert fix['main_sha256']==sha(P/'analysis/analyze_information.py') and fix['label_clock_sha256']==sha(P/'analysis/label_clock.py')
 examples=load(P/'analysis/PRELABEL_PVR_PARSE_DIAGNOSIS.json')[0]['examples']
 for r in examples:
  text=json.dumps({'original_PVR':r['score']})+'\n';parsed=pd.read_json(io.StringIO(text),lines=True,precise_float=True).iloc[0].original_PVR
  assert np.float64(parsed).view(np.uint64)==np.float64(json.loads(text)['original_PVR']).view(np.uint64)
 for p in [Path(__file__),XDIR/'FEATURE_MANIFEST_PRE_LABEL.json',XDIR/'COMPLETED_EXPORT_SEAL_AUDIT.json',XDIR/'EXPORT_STOPPED.json',XDIR/'export_features.py',P/'feature_design/features.py',P/'analysis/analyze_information.py',P/'analysis/analyze_information_pre_parse_fix.py.txt',P/'analysis/TECHNICAL_PARSE_FIX_AND_RETRY_FREEZE.json',P/'analysis/PRELABEL_PVR_PARSE_DIAGNOSIS.json',P/'analysis/label_clock.py',P/'analysis/ANALYSIS_SCHEMA.json',O/'PRIMARY_MOTHER_AND_EVENT_AUDIT.json',O/'LABEL_CLOCK_SMALL_AUDIT.json',O/'LABEL_CLOCK_FLAGS_V2_SMALL_AUDIT.json',O/'PRE_LABEL_CLARIFICATION_AND_SMALL_PREFIX_ACCEPTANCE.json']:
  source[str(p)]=sha(p)
 assert sha(P/'analysis/label_clock.py')==clock['source_sha256'][str(P/'analysis/label_clock.py')]
 z=dict(status='PASS_PURE_EXPORT_AND_STATIC_ANALYSIS_RUN_GATE_WITH_LIMITS',footers=footers,sampled_serialized_features=samples,primary_audit=primary['status'],label_clock_audit=clock['status'],label_clock_scope=dict(synthetic_families=10,real_keys=36),
  export_seal_finding=dict(original_assertion='empty_signal_symbols==22',actual_full_history_empty_stock_signals=0,actual_full_history_empty_industry_signals=0,failure_stage='after writers closed and numeric checks completed; terminal acceptance assertion only',old_source_stopped_and_parquets_preserved=True,window_no_source_stock_symbols=22,window_UNKNOWN_rows_retained=21296,distinction='Window-absent stocks are separately evidenced; they do not make the original sig.empty assertion valid. No22 empty industry assertion is supported.'),
  static_review=dict(features_t_CLOSE_only=True,whole_PRIMARY_quantiles_before_labels=True,roles_inherit_primary_bins=True,same_day_known_PVR_quartile_contrasts=True,day_equal_with_pair_coverage=True,per_window_horizons_no_crosswindow_shift=True,annual_groups_do_not_retruncate=True,next_OPEN_gap_separate=True,original3436_fixed177_post303_retained_without_h60_filter=True,PNL_and_short_holding_posterior_only=True,no_financial_imports_or_fusion=True),
  parser_fix=dict(current_main_sha=fix['main_sha256'],patch_scope='precise_float=True and separate existing-safe --out only; unified diff independently reviewed',bitexact_assertion_preserved=True,independent_scalar_examples=len(examples),whole133542_diagnosis_reused=True,old_failed_v1_preserved=True),
  source_sha256=source,elapsed_seconds=time.monotonic()-started,remaining_execution_blocks=[],technical_note='First own sample comparison compared pandas nullable boolean NA with serialized None; normalized both through the frozen Arrow schema and common nullable boolean dtype before exact comparison. No producer/source/Parquet change or tolerance change.',
  limits=['Gate permits only the separately authorized bounded descriptive analysis; it is not an endorsement of any score/fusion/trading policy.','Full-source and full-row quote/score export validation is reused from completed producer sidecar; own serialized feature audit covers2 symbols/1936 stock-days, all columns; no second full export.','All-primary source/role/clock/firstseen audit is separate and full; label scalar audit is10 synthetic families and36 real keys, not all future labels.','No exchange halt certification; endpoint labels with interior missing retain flags; max/min60 requires a complete future path.','Pairs are descriptive dependent observations, not independent trials or a new-account return. UNKNOWN, sparse paired coverage and current-snapshot source limits remain.'],new_accounts=0,new_full_exports=0,new_full_label_tables=0)
 (O/'COMPLETED_EXPORT_AND_ANALYSIS_GATE_AUDIT.json').write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n');signal.setitimer(signal.ITIMER_REAL,0);print(z['status'],round(z['elapsed_seconds'],2),sha(O/'COMPLETED_EXPORT_AND_ANALYSIS_GATE_AUDIT.json'))
if __name__=='__main__':main()
