"""One frozen PVR3-priority incremental ranking diagnostic, not an account."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;R=O.parent;B=R/'breadth_entry_rank_comparison_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
start=time.monotonic();assert not (O/'SELECTION_SEAL.json').exists()
protocol=dict(created_utc=str(pd.Timestamp.now(tz='UTC')),one_selection_one_evaluation=True,development_diagnostic_not_OOS=True,already_seen='Prior PVR/H1/amount results and related histories have repeatedly been examined. New idea is not unseen OOS, no threshold tuning and no historical winner promotion.',windows=[['2022','2022-01-01','2022-12-31',None],['2024_924','2024-09-01','2024-12-31',None],['2026H1_SEMI','2026-01-01','2026-06-30','URFI881121']],arms=['PVR_DESC','PVR3_PRIORITY'],stock_feature='S_i(t)=1 iff original PVR>=60 on t,t-1,t-2 common market sessions, all3 finite valid observed rows, identical segment/source_kind/source_path. Any unknown => -1; known and any below60 =>0. Reuse original frozen STOCK_DAILY state; no recomputed smoothing or threshold.',ranking='Baseline current PVR descending, then sid. Increment: retain unknown-PVR3 exact baseline slots; reorder known slots by (PVR3=true first, current PVR descending, sid ascending). Known false still fills; no new hard gate, no waiting for persistence. Current inherited common domain already requires known PVR3 so unknown slots are not present.',candidate_eligibility='Exact prior common domain and exact t-close feasibility reused for every event. M3 candidate stock=canonical mu5>0 for3 dates AND both-known. PVR3 candidate stock=PVR3=true AND both-known. Hence PVR3 priority is predetermined identical control; event labels are not interchangeable. Same original industry event dates, same K, same I/price/lot/risk/capacity.',selection='For each event scan entire queue, choose first2 original CLOSE_PASS. Freeze before new forward outcomes. Equal per-event counts verified against prior PVR baseline. No next-open backfill.',execution='Unchanged prior simulate.py economics:1.2m reference NAV,2% initial,one profitable freshCP add capped2%,slot4%,.25% plan loss,next open +/-5bp,dated lot/fees,T+1,I exit/add protection. Plan loss is not worst-loss guarantee. Independent conditional shadows only.',all_candidates='Evaluate all22196 inherited common-known CLOSE_PASS event-stock identities with exact same economics for a complete eligible tail-opportunity denominator. These are diagnostic independent possibilities, not simultaneously bought positions. Other6362 candidates remain explicitly in eligibility ledger and are not assigned fake outcomes.',tail='Predeclared descriptive strong capture: closed fee-net return on cumulative buy cash>=30%, same prior report cutoff. Report selected count / all feasible complete-tail count; unknown/open never labeled loser or non-tail. Also tail opportunities missed/gained vs baseline. Not whole-market capture or future predictive criterion.',nonaccount_limits='Fixed1709 future stock pool/90 sectors NON-PIT. Historical orderability UNKNOWN. Raw-source changes, missing paths and corporate action/factor changes UNKNOWN; June30 unclosed OPEN. Keep quick-launch untouched and outside this experiment. No shared capital/ACT/account run; original cash screen diagnostic only and after2026-05-15 UNKNOWN.',no_threshold_sweep=True,no_accounts=True)
save('PROTOCOL.json',protocol)
oldseal=json.load(open(B/'SELECTION_SEAL.json'));assert all(sha(p)==h for p,h in oldseal['hashes'].items());assert all(sha(p)==h for p,h in oldseal['source_hashes'].items())
sources={str(p):sha(p) for p in [Path(__file__),O/'simulate.py',O/'report.py',B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',B/'SEALED_CLOSE_SELECTED.csv',B/'SELECTION_SEAL.json',B/'simulate.py',R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet']}
c=pd.read_csv(B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',parse_dates=['day'],low_memory=False);assert len(c)==28558
pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet')[['sid','day','state','score']]
j=c.merge(pv,on=['sid','day'],validate='many_to_one');assert j.PVR_state.eq(j.state).all();np.testing.assert_allclose(j.PVR_score,j.score,rtol=1e-12,atol=1e-10)
c.to_csv(O/'ALL_CANDIDATES_COMMON_DOMAIN.csv',index=False)
queues=[]
for strategy in ['PVR_DESC','PVR3_PRIORITY']:
 z=c.copy();z['ranking_strategy']=strategy;z['rank']=np.nan;z['selected_close_frozen']=False
 for event,g in z.groupby('event_id',sort=False):
  v=g[g.ranking_common_known].sort_values(['PVR_score','sid'],ascending=[False,True],kind='stable');idx=list(v.index)
  if strategy=='PVR3_PRIORITY':
   known=v.PVR_state.ge(0);slots=np.flatnonzero(known.to_numpy());priority=v[known].sort_values(['PVR_state','PVR_score','sid'],ascending=[False,False,True],kind='stable').index.tolist()
   for p,i in zip(slots,priority):idx[p]=i
  z.loc[idx,'rank']=range(1,len(idx)+1);v=z.loc[idx];passed=v[v.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE')];z.loc[passed.head(2).index,'selected_close_frozen']=True
 queues.append(z)
q=pd.concat(queues,ignore_index=True);q.to_csv(O/'ALL_RANKED_CLOSE_QUEUES.csv',index=False);s=q[q.selected_close_frozen].copy();s.to_csv(O/'SEALED_CLOSE_SELECTED.csv',index=False)
old=pd.read_csv(B/'SEALED_CLOSE_SELECTED.csv');old=old[old.ranking_strategy.eq('PVR_DESC')];now=s[s.ranking_strategy.eq('PVR_DESC')]
cols=['event_id','sid','rank'];pd.testing.assert_frame_equal(now[cols].sort_values(cols[:2]).reset_index(drop=True),old[cols].sort_values(cols[:2]).reset_index(drop=True),check_dtype=False)
counts=s.groupby(['event_id','ranking_strategy']).size().unstack();assert counts.nunique(axis=1).eq(1).all()
changes=[]
for (w,a,t),g in s.groupby(['window','arm','event_type']):
 aa=g[g.ranking_strategy.eq('PVR_DESC')];bb=g[g.ranking_strategy.eq('PVR3_PRIORITY')];x=set(map(tuple,aa[['event_id','sid']].to_numpy()));y=set(map(tuple,bb[['event_id','sid']].to_numpy()));changes.append(dict(window=w,arm=a,event_type=t,selected_per_strategy=len(x),shared=len(x&y),removed=len(x-y),added=len(y-x),changed_events=len({e for e,i in x^y})))
changes=pd.DataFrame(changes);assert changes.loc[changes.arm.eq('PVR3'),'changed_events'].eq(0).all();changes.to_csv(O/'SELECTION_CHANGES.csv',index=False)
d=q[q.ranking_strategy.eq('PVR_DESC') & q.ranking_common_known & q.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE')].copy();d['ranking_strategy']='ALL_FEASIBLE_DIAGNOSTIC';d['selected_close_frozen']=False;assert len(d)==22196
pd.concat([s,d],ignore_index=True).to_csv(O/'EVALUATION_INPUT.csv',index=False)
coverage=c.groupby(['window','arm','event_type']).agg(candidate_rows=('sid','size'),common_known=('ranking_common_known','sum'),persistent_true=('PVR_state',lambda x:int(x.eq(1).sum())),persistence_unknown=('PVR_state',lambda x:int(x.lt(0).sum()))).reset_index();coverage.to_csv(O/'COVERAGE.csv',index=False)
assert all(sha(p)==h for p,h in sources.items())
files=['PROTOCOL.json','ALL_CANDIDATES_COMMON_DOMAIN.csv','ALL_RANKED_CLOSE_QUEUES.csv','SEALED_CLOSE_SELECTED.csv','SELECTION_CHANGES.csv','EVALUATION_INPUT.csv','COVERAGE.csv']
save('SELECTION_SEAL.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),hashes={str(O/n):sha(O/n) for n in files},source_hashes=sources,all_candidates=len(c),common_known=int(c.ranking_common_known.sum()),selected=len(s),diagnostic_feasible=len(d),all_evaluation_rows=len(s)+len(d),unknown_fixed_slots=int((c.ranking_common_known & c.PVR_state.lt(0)).sum()),old_baseline_selections_exact=True,per_event_K_unchanged=True,PVR3_control_exact=True,new_forward_outcomes_not_loaded_before_seal=True,seconds=time.monotonic()-start))
print(changes.to_string(index=False));print('SEALED',len(s),len(d),flush=True)
