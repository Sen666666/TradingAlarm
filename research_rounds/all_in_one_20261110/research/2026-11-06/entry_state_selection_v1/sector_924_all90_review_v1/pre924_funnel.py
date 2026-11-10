"""Read-only prior-to-924 all-sector state and original account candidate funnel."""
from pathlib import Path
import json,hashlib
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent
P=R/'m3_ab_shared_probe_v1/tech407_admission_mask_ablation_v1/run_all1709_once'
S=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
Q=R/'m3_ab_shared_probe_v1/daily_924_account_readout_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
paths=[Path(__file__),S,P/'DECISIONS.json',P/'ACTIONS.json',P/'SOURCE_ROUNDS.json',Q/'DAILY_SECTOR_POSITIONS.csv',Q/'DAILY_ACCOUNT.csv',O/'DAILY_STATE_PRICE_AND_INDUSTRY_POSITION.csv',O/'ALL_90_SECTOR_REVIEW.csv',O/'ALL_TRUE_RUNS_WITH_FIXED_HORIZONS.csv']
hashes={str(p):sha(p) for p in paths}
d=pd.read_parquet(S).sort_values(['sector','day']);d['previous_state']=d.groupby('sector').M3_candidate.shift();d['day']=d.day.dt.strftime('%Y-%m-%d');cal=sorted(d.day.unique());nextday=dict(zip(cal[:-1],cal[1:]));w=d[d.day.between('2024-09-02','2024-09-23')].copy();assert len(w)==90*14
E=pd.DataFrame(json.loads((P/'DECISIONS.json').read_text()));E['day']=E.day.str[:10];E=E[E.day.between('2024-09-02','2024-09-23')].copy()
A=pd.DataFrame(json.loads((P/'ACTIONS.json').read_text()));RR=pd.DataFrame(json.loads((P/'SOURCE_ROUNDS.json').read_text())).set_index('round_id');A['sector']=A.round_id.map(RR.sector)
pr=pd.read_csv(O/'DAILY_STATE_PRICE_AND_INDUSTRY_POSITION.csv');pr['day']=pr.day.str[:10];pr=pr.set_index(['day','sector'])
future=pd.read_csv(O/'ALL_90_SECTOR_REVIEW.csv').set_index('sector');future['posthoc_0923_1008_rank']=future.return_0923_1008_pct.rank(ascending=False,method='min')
rows=[];queues=[]
for day,dd in w.groupby('day'):
 e=E[E.day.eq(day)].copy();selected=e[e.selected].sort_values(['PVR_score','sid'],ascending=[False,True]).copy();selected['derived_same_day_INIT_queue_order']=range(1,len(selected)+1);selected['next_common_OPEN']=nextday[day]
 assert set(selected.sector)<=set(dd[dd.M3_candidate.eq(1)].sector)
 queues.append(selected)
 for z in dd.itertuples():
  x=e[e.sector.eq(z.sector)];q=selected[selected.sector.eq(z.sector)];f=A[A.day.eq(nextday[day])&A.side.eq('buy_core')&A.round_id.isin(q.round_id)]
  at=pr.loc[(day,z.sector)];end=pr.loc[('2024-09-23',z.sector)]
  row=dict(day=day,sector=z.sector,industry=z.sector_name,previous_state=z.previous_state,state=int(z.M3_candidate),n=int(z.M3_n),K=int(z.K),N=int(z.N),U=int(z.U),delta3=int(z.M3_delta3),next_common_OPEN=nextday[day],A_births=int(x.event_type.eq('A_SECTOR_BIRTH').sum()),B_births=int(x.event_type.eq('B_STOCK_BIRTH_DURING_SECTOR').sum()),I_and_PVR_known=int((x.I_qualified&x.PVR_known).sum()),blocked_held=int(x.decision.eq('BLOCKED_HELD').sum()),blocked_unknown=int(x.decision.eq('BLOCKED_UNKNOWN').sum()),close_PASS=int(x.close_check.eq('PASS').sum()),close_minlot_or_risk_reject=int(x.close_check.eq('MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE').sum()),selected_INIT_count=len(q),selected_INIT_queue_orders=','.join(map(str,q.derived_same_day_INIT_queue_order)),next_OPEN_original_INIT_fills=len(f),actual_sector_weight_pct_NAV=float(at.actual_weight_pct_NAV),industry_close=float(at.industry_close),pre_924_ret_to_0923_pct=100*(end.industry_close/at.industry_close-1),posthoc_0923_1008_pct=float(future.loc[z.sector,'return_0923_1008_pct']),posthoc_0923_1008_rank=int(future.loc[z.sector,'posthoc_0923_1008_rank']))
  rows.append(row)
panel=pd.DataFrame(rows);panel.to_csv(O/'PRE924_ALL90_DAILY_FUNNEL.csv',index=False)
queue=pd.concat(queues,ignore_index=True);queue.to_csv(O/'PRE924_ALL_SELECTED_INIT_QUEUE.csv',index=False)
summary=[]
for day,x in panel.groupby('day'):
 summary.append(dict(day=day,TRUE=int(x.state.eq(1).sum()),FALSE=int(x.state.eq(0).sum()),UNKNOWN=int(x.state.eq(-1).sum()),A=int(x.A_births.sum()),B=int(x.B_births.sum()),I_and_PVR_known=int(x.I_and_PVR_known.sum()),close_PASS=int(x.close_PASS.sum()),sectors_with_close_PASS=int(x.close_PASS.gt(0).sum()),selected_INITs=int(x.selected_INIT_count.sum()),sectors_with_selected_INITs=int(x.selected_INIT_count.gt(0).sum()),earliest_execution_day=nextday[day],original_next_OPEN_INITs=int(x.next_OPEN_original_INIT_fills.sum()),same_close_sectors_held=int(x.actual_sector_weight_pct_NAV.gt(0).sum()),same_close_total_stock_weight_pct=float(x.actual_sector_weight_pct_NAV.sum())))
pd.DataFrame(summary).to_csv(O/'PRE924_DAILY_TOTALS.csv',index=False)
# Every observed pre924 TRUE run, not only the successful run covering the rally.
runs=pd.read_csv(O/'ALL_TRUE_RUNS_WITH_FIXED_HORIZONS.csv');runs=runs[runs.start.between('2024-09-02','2024-09-23')].copy();runs['pre924_change_to_0923_pct']=[100*(pr.loc[('2024-09-23',z.sector),'industry_close']/z.start_close-1) for z in runs.itertuples()];runs.to_csv(O/'PRE924_ALL_TRUE_RUNS_WITH_OUTCOMES.csv',index=False)
meta=dict(sectors=90,days=14,rows=len(panel),all_A_B_births=len(E),selected_INITs=len(queue),TRUE_runs_started_in_window=len(runs),TRUE_runs_5day_complete=int(runs.complete5_within_review.sum()),TRUE_runs_5day_nonpositive=int(runs.ret5_pct.le(0).sum()),TRUE_runs_pre924_nonpositive=int(runs.pre924_change_to_0923_pct.le(0).sum()),sources_unchanged=all(sha(p)==h for p,h in hashes.items()),no_new_account=True,no_new_indicators=True,rank_definition='No independent industry ranking exists. Queue is derived from original selected INITs by descending PVR then sid; ADD/sells have their own priority. Future returns/rank are strictly descriptive, never used in this queue.',unknown='Original tri-state; NON-PIT fixed research members; K is common M3/PVR-known denominator, not full historical membership.',readout='Positive post-924 index return is not net strategy profit, signal precision or a guarantee the event could be traded. No hindsight price used to permit an OPEN.')
save('PRE924_SUMMARY.json',meta);save('PRE924_SOURCE_HASHES.json',hashes);save('PRE924_OUTPUT_SEAL.json',{p.name:sha(p) for p in O.glob('PRE924_*') if p.name!='PRE924_OUTPUT_SEAL.json'})
print(json.dumps(meta,ensure_ascii=False,indent=2));print(pd.DataFrame(summary).to_string(index=False))
