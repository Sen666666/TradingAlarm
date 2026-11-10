from pathlib import Path
import json,time,hashlib,resource,collections
import pandas as pd,numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'m3_ab_shared_probe_v1/daily_gap_inventory_v1'
t0=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def csv(n,x):
 with (O/n).open('x') as f:pd.DataFrame(x).to_csv(f,index=False)
ev=pd.read_csv(O/'CANDIDATE_EVENT_STATIC_CHECKS.csv');ev=ev[~ev.static_close_check.isin(['I_INELIGIBLE','PVR_UNKNOWN'])]
gaps=pd.read_csv(O/'MISSING_ROW_RUNS_V2.csv')
u=pd.read_csv(O/'STOCK_UNIVERSE_V2.csv').set_index('sid')
problems=pd.read_csv(O/'DAILY_ISSUES_V2.csv')
panel=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
cal=pd.DatetimeIndex(sorted(pd.read_parquet(panel,columns=['day']).day.unique()));cal=cal[(cal>='2022-01-01')&(cal<='2026-06-30')]
end=cal[-1];refs={str(panel):sha(panel)}
rows=[];matched=collections.Counter();firstmatched=collections.Counter();facts_count=0
for sid,e in ev.groupby('sid',sort=True):
 gg=gaps[gaps.sid.eq(sid)].sort_values('gap_start')
 if gg.empty:
  for r in e.to_dict('records'):rows.append(dict(event_id=r['event_id'],sid=sid,next_common_open=r['next_common_open'],status='NO_MISSING_RUN_IN_WIDE_DOMAIN',first_gap_id='',all_pre_I_exit_gap_ids=''))
  continue
 fp=u.loc[sid,'facts_path'];assert sha(fp)==u.loc[sid,'facts_sha256'];refs[fp]=sha(fp)
 f=pd.read_parquet(fp,columns=['i_target'])
 falses=f.index[f.i_target.isin([False,0])]
 facts_count+=1
 for r in e.to_dict('records'):
  entry=pd.Timestamp(r['next_common_open']);i=falses.searchsorted(entry)
  firstfalse=falses[i] if i<len(falses) and falses[i]<=end else None
  j=cal.searchsorted(firstfalse,side='right') if firstfalse is not None else len(cal)
  exitday=cal[j] if j<len(cal) else end
  hits=gg[(pd.to_datetime(gg.gap_end)>=entry)&(pd.to_datetime(gg.gap_start)<=exitday)]
  ids=list(hits.gap_id)
  if ids:
   firstmatched[ids[0]]+=1
   for x in ids:matched[x]+=1
  rows.append(dict(event_id=r['event_id'],sid=sid,next_common_open=r['next_common_open'],original_fixed_budget_close_check=r['static_close_check'],first_observed_I_false_close='' if firstfalse is None else str(firstfalse.date()),hypothetical_exit_next_common_open=str(exitday.date()),status='GAP_AT_OR_BEFORE_FIRST_OBSERVED_I_EXIT' if ids else 'NO_GAP_BEFORE_FIRST_OBSERVED_I_EXIT',first_gap_id=ids[0] if ids else '',all_pre_I_exit_gap_ids=';'.join(ids)))
csv('I_EXIT_GAP_PRIORITY_EVENTS.csv',rows)
q=gaps.copy();q['I_PVR_candidate_envelopes_intersecting_gap']=q.gap_id.map(matched).fillna(0).astype(int);q['I_PVR_candidates_first_gap']=q.gap_id.map(firstmatched).fillna(0).astype(int)
csv('I_EXIT_GAP_PRIORITY_RUNS.csv',q.to_dict('records'))
invalid=[]
for sid,d in problems[problems.issue.eq('INVALID_OPEN')][['sid','day']].drop_duplicates().itertuples(index=False,name=None):
 p=u.loc[sid,'signal_path'];refs[p]=sha(p);assert refs[p]==u.loc[sid,'signal_sha256']
 f=pd.read_parquet(p);r=f.loc[pd.Timestamp(d)]
 cols=['raw_open','raw_close','adjustment_factor','source_kind','source_path','segment_id','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar','quality_status']
 dd={c:r[c] for c in cols if c in r};dd.update(sid=sid,day=d,signal_path=p,signal_sha256=refs[p])
 valid=f.index[(pd.to_numeric(f.raw_open,errors='coerce')>0)&(pd.to_numeric(f.raw_close,errors='coerce')>0)&f.observed_bar.isin([True,1])&f.price_eligible.isin([True,1])&f.volume_eligible.isin([True,1])&f.source_invalid.isin([False,0])&f.synthetic_event_bar.isin([False,0])&(f.index<=end)]
 pre=valid[valid<pd.Timestamp(d)];nxt=valid[valid>pd.Timestamp(d)]
 dd['previous_valid_day']=str(pre[-1].date()) if len(pre) else '';dd['next_valid_day']=str(nxt[0].date()) if len(nxt) else ''
 dd['classification']='EXPLICIT_SYNTHETIC_EVENT_BAR_NOT_OBSERVED_QUOTE' if bool(r.synthetic_event_bar) else 'OTHER_INVALID_EXISTING_ROW_NOT_PROOF_OF_HALT'
 invalid.append(dd)
csv('INVALID_EXISTING_ROW_DETAILS.csv',invalid)
# Beyond-follow observations clarify censoring, not historical admissibility or suspension.
tails=[]
for r in gaps[gaps.gap_type.ne('INTERNAL_MISSING_ROWS')].to_dict('records'):
 p=u.loc[r['sid'],'signal_path'];f=pd.read_parquet(p);refs[p]=sha(p)
 later=f[f.index>end];valid=later[(pd.to_numeric(later.raw_open,errors='coerce')>0)&(pd.to_numeric(later.raw_close,errors='coerce')>0)&later.observed_bar.isin([True,1])&later.price_eligible.isin([True,1])&later.volume_eligible.isin([True,1])&later.source_invalid.isin([False,0])&later.synthetic_event_bar.isin([False,0])]
 tails.append(dict(gap_id=r['gap_id'],sid=r['sid'],first_valid_bar_after_follow_end=str(valid.index[0].date()) if len(valid) else '',raw_source_final_date=str(f.index[-1].date()),evidence_role='POST_WINDOW_SOURCE_DIAGNOSTIC_ONLY_NOT_PIT_OR_RESUMPTION_CERTIFICATION'))
csv('FOLLOW_END_BOUNDARY_DETAILS.csv',tails)
protected=json.loads((O/'PROTECTED_LEDGER_HASHES.json').read_text())
assert all(sha(p)==h for p,h in protected.items())
summary={'eligible_events':len(ev),'eligible_sids':ev.sid.nunique(),'only_gap_sid_facts_files_read':facts_count,'priority_gap_runs_intersecting_hypothetical_I_envelopes':len(matched),'priority_gap_runs_as_first_gap':len(firstmatched),'priority_gap_sids':q[q.I_PVR_candidate_envelopes_intersecting_gap.gt(0)].sid.nunique(),'priority_gap_stock_days':int(q[q.I_PVR_candidate_envelopes_intersecting_gap.gt(0)].missing_common_sessions.sum()),'priority_runs_by_start_year':q[q.I_PVR_candidate_envelopes_intersecting_gap.gt(0)].gap_start.str[:4].value_counts().to_dict(),'priority_runs_not_existing_registry_covered':int((q.I_PVR_candidate_envelopes_intersecting_gap.gt(0)&q.registry_covered_sessions.lt(q.missing_common_sessions)).sum()),'other_runs_not_proven_unreachable':len(gaps)-len(matched),'invalid_existing_row_count':len(invalid),'invalid_existing_row_classification':dict(collections.Counter(x['classification'] for x in invalid)),'elapsed_seconds':time.monotonic()-t0,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'source_read_bytes':sum(Path(p).stat().st_size for p in refs),'economic_accounts_run':0,'engine_imported':False,'unchanged_protected_ledger_files_verified':len(protected),'source_hashes':refs,'limitations':['This is a missing-gap search priority overlay, not a certified reachability envelope or an authorization to remove other runs.','Starts from ALL 9779 I/PVR-eligible events, including original fixed-budget minimum-lot/risk rejects. Shared Nd may differ.','Assumes each eligible event could establish CORE next OPEN and searches actual observed original I=false then next common OPEN. No prices or indicators are forward-filled.','If a missing interval precedes the first observed I exit, it remains listed; later observed I=false cannot hide that first interruption.','OPEN nofill, source/factor/metadata UNKNOWN and earlier other failures are not simulated. Frozen UNKNOWN may retain liability beyond an observed later I exit; therefore the remaining wide-domain runs are not proven unreachable.','Existing full wide inventory and actual executed responsibility overlay remain authoritative. The priority list does not change any source, strategy or sealed ledger.']}
save('I_EXIT_GAP_PRIORITY_RESULT.json',summary)
save('SUPPLEMENT_OUTPUT_SEAL.json',{p.name:sha(p) for p in O.iterdir() if p.is_file()})
print(json.dumps(summary,ensure_ascii=False,default=str),flush=True)
