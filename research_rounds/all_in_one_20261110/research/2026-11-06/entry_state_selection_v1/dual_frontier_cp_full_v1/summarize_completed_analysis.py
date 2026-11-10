"""Read-only computation over completed research, new summary files only."""
from pathlib import Path
import json,sys,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
sys.path.insert(0,str(O));import replay_signals as r
rr=pd.read_parquet(O/'FIXED_I_ROOT_COMPARISON.parquet')
ev=pd.read_parquet(O/'EVENTS_QUALIFIED.parquet')
known=rr[~rr.unknown_birth&~rr.birth_before_2022].copy()
periods=[('ALL_KNOWN_2022_PLUS',known)]+[(str(y),g) for y,g in known.groupby('year')]+[('2024_924',known[known.I_root.between('2024-09-24','2024-10-31')]),('2026Q1',known[known.I_root.between('2026-01-01','2026-03-31')]),('2026Q1_semiconductor',known[known.I_root.between('2026-01-01','2026-03-31')&known.sector.eq('URFI881121')])]
rootcounts=[];paths=[];timing=[]
for period,g in periods:
 for domain in ['signal','qualified']:
  a=g['old_'+domain+'_count'].gt(0);b=g['new_'+domain+'_count'].gt(0)
  v=dict(period=period,domain=domain,roots=len(g),old_any=int(a.sum()),new_any=int(b.sum()),both_any=int((a&b).sum()),old_only_any=int((a&~b).sum()),new_only_any=int((~a&b).sum()),neither=int((~a&~b).sum()),mature60=int(g.complete60.sum()),big60=int(g.big60.sum()))
  for h in [5,20,60]:
   aa=g['old_'+domain+'_lag'].between(0,h-1);bb=g['new_'+domain+'_lag'].between(0,h-1);big=g.big60
   v.update({f'big_old_by{h}':int((aa&big).sum()),f'big_new_by{h}':int((bb&big).sum()),f'big_lost_by{h}':int((aa&~bb&big).sum()),f'big_added_by{h}':int((~aa&bb&big).sum())})
  rootcounts.append(v)
  lag=g.loc[a&b,'new_'+domain+'_lag']-g.loc[a&b,'old_'+domain+'_lag']
  timing.append(dict(period=period,domain=domain,comparison='first_receipt_same_known_native_root',n=len(lag),new_earlier=int(lag.lt(0).sum()),same=int(lag.eq(0).sum()),new_later=int(lag.gt(0).sum()),lag_mean=float(lag.mean()),lag_median=float(lag.median()),lag_p90=float(lag.quantile(.9)),lag_min=float(lag.min()),lag_max=float(lag.max())))
  groups=[('both',a&b),('old_only',a&~b),('new_only',~a&b),('neither',~a&~b)]
  for group,mask in groups:
   gg=g[mask]
   for h in [5,20,60]:
    z=gg[gg['complete'+str(h)]]
    paths.append(dict(period=period,domain=domain,group=group,horizon=h,roots=len(gg),complete=len(z),incomplete=len(gg)-len(z),positive_price_fraction=float(z['ret'+str(h)].gt(0).mean()) if len(z) else np.nan,mean_price_return=float(z['ret'+str(h)].mean()),median_price_return=float(z['ret'+str(h)].median()),mean_close_mfe=float(z['mfe'+str(h)].mean()),median_close_mfe=float(z['mfe'+str(h)].median()),mean_close_mae=float(z['mae'+str(h)].mean()),median_close_mae=float(z['mae'+str(h)].median())))
pd.DataFrame(rootcounts).to_csv(O/'KNOWN_2022_PLUS_ROOT_COUNTS.csv',index=False)
pd.DataFrame(timing).to_csv(O/'ROOT_FIRST_TIMING_SUMMARY.csv',index=False)
pd.DataFrame(paths).to_csv(O/'FIXED_ROOT_PRICE_PATH_SUMMARY.csv',index=False)
cases=json.loads((R/'lifecycle_ordered_damage_v1/FIXED_CASES_BEFORE_COMPUTE.json').read_text());out=[]
for c in cases:
 st=pd.read_parquet(O/'states'/(c['sid']+'.parquet'))
 t=st[st.day.eq(c['day'])].iloc[0]
 row=dict(c)
 for k in ['I_root','segment','qok','old_receipt','new_receipt','old_credit','new_credit','old_anchor','new_anchor','q','close']:
  row[k]=t[k]
 same=ev[ev.sid.eq(c['sid'])&ev.I_root.eq(t.I_root)&ev.segment.eq(t.segment)]
 row['new_earlier_signal_days']=';'.join(same[same.new_receipt&same.day.lt(c['day'])].day.tolist())
 row['new_earlier_qualified_days']=';'.join(same[same.new_receipt&same.prequalified&same.day.lt(c['day'])].day.tolist())
 row['new_later_signal_days']=';'.join(same[same.new_receipt&same.day.gt(c['day'])].day.tolist())
 row['core_not_dependent_on_cp']=c['original_role']=='core'
 out.append(row)
pd.DataFrame(out).to_csv(O/'FIXED19_CASE_COMPARISON.csv',index=False)
pairs=pd.read_parquet(O/'DESCRIPTIVE_EVENT_PAIRS.parquet')
pairsummary=dict(kind_counts=pairs.kind.value_counts().to_dict(),unmatched_pair_lags={})
for col in ['trading_lag','observation_lag','calendar_lag']:
 z=pairs.loc[pairs.kind.eq('paired_unmatched'),col]
 pairsummary['unmatched_pair_lags'][col]=dict(n=len(z),new_earlier=int(z.lt(0).sum()),new_later=int(z.gt(0).sum()),mean=z.mean(),median=z.median(),min=z.min(),max=z.max())
r.save('DESCRIPTIVE_PAIR_SUMMARY.json',pairsummary)
# Current content-addressed analysis inputs. This manifest was added after analysis.
# It does not retrospectively certify a pre-analysis hash freeze.
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
extra=[M/'STOCK_MANIFEST.json',M/'INDUSTRY_MANIFEST.json',Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/metadata.json'),R/'account_comparison_continuous_v1/run_1200000/pair/opportunities.jsonl.gz',R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv',R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',O/'I_ROOTS.parquet',O/'EVENTS.parquet',O/'EVENTS_QUALIFIED.parquet']
for z in json.loads((M/'INDUSTRY_MANIFEST.json').read_text()):extra.append(Path(z['refs']['state']))
for z in json.loads((M/'STOCK_MANIFEST.json').read_text()):extra.append(Path(next(p for p in z['source_sha256'] if p.endswith('/signal.parquet'))))
hashes={str(p):r.sha(p) for p in sorted(set(extra))}
prior=json.loads((O/'INPUT_SHA256.json').read_text());matched={p:prior[p]==h for p,h in hashes.items() if p in prior}
assert all(matched.values())
r.save('ANALYSIS_INPUT_SHA256_POSTRUN.json',dict(timing='POSTRUN current inputs; not a retrospective pre-analysis freeze',hashes=hashes,matching_preexisting_signal_input_hashes=len(matched),all_preexisting_matches=True))
r.save('SUMMARY_NOTES.json',dict(root_scope='Known native I births >=2022 only; excludes 1017 left-truncated pre2022 roots from this new summary.',price_path_scope='Prices anchored at next common OPEN after root birth, h common-session closing prices. Descriptive future price outcomes, not signal-executable returns or strategy performance. Incomplete paths excluded per horizon.',receipt_groups='Membership can occur after the price horizon; group price distributions are ex-post association, never prediction or backtest.',case_scope='19 frozen case windows, not 19 distinct stocks. CORE original first entries must not be removed because CP changes.',no_new_accounts=True,no_signal_rerun=True,no_parameters_changed=True))
print(pd.DataFrame(rootcounts).query("period=='ALL_KNOWN_2022_PLUS'").to_string(index=False))
print(pd.DataFrame(timing).query("period=='ALL_KNOWN_2022_PLUS'").to_string(index=False))
print(pd.DataFrame(paths).query("period=='ALL_KNOWN_2022_PLUS' and horizon==60").to_string(index=False))
print('SUMMARY_COMPLETE',len(hashes),'input hashes;',len(matched),'match signal freeze')
