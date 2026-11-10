"""Read-only 924 sector-level review, all original90 sectors. No trading consumers."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent
S=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
C=R/'industry_panorama_2019_2026_v1/full90_final_integration_v1/FINAL_CANONICAL_CYCLES_90.csv'
A=R/'m3_ab_shared_probe_v1/daily_924_account_readout_v1'
P=R/'m3_ab_shared_probe_v1/tech407_admission_mask_ablation_v1/run_all1709_once'
START=pd.Timestamp('2024-09-02');ANCHOR=pd.Timestamp('2024-09-24');END=pd.Timestamp('2024-10-31')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fmt(x):return str(pd.Timestamp(x).date()) if x is not None and pd.notna(x) else None
def out(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
src={str(p):sha(p) for p in [Path(__file__),O/'PROTOCOL.json',S,U,C,A/'DAILY_SECTOR_POSITIONS.csv',A/'DAILY_ACCOUNT.csv',P/'ACTIONS.json',P/'SOURCE_ROUNDS.json']}
d=pd.read_parquet(S).sort_values(['sector','day']);d.day=pd.to_datetime(d.day);assert d.sector.nunique()==90
im={x['series']:x for x in json.loads(U.read_text())};maps=pd.read_csv(C)
account=pd.read_csv(A/'DAILY_ACCOUNT.csv');sectorpos=pd.read_csv(A/'DAILY_SECTOR_POSITIONS.csv')
actions=pd.DataFrame(json.loads((P/'ACTIONS.json').read_text()));rr={x['round_id']:x for x in json.loads((P/'SOURCE_ROUNDS.json').read_text())}
actions['sector']=actions.round_id.map(lambda r:rr[r]['sector']);actions['industry']=actions.round_id.map(lambda r:rr[r]['industry'])
rows=[];trans=[];runs=[];daily=[];prices=[]
for sec,x0 in d.groupby('sector',sort=True):
 x=x0.set_index('day').copy();prev=x.M3_candidate.shift();x['previous_state']=prev
 m=im[sec];p=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));assert sha(p)==m['source_sha256'][str(p)];src[str(p)]=sha(p)
 z=pd.read_parquet(p);assert z.index.is_unique and z.index.is_monotonic_increasing;np.testing.assert_array_equal(z.close,z.raw_close);s=z.close
 name=x.sector_name.iloc[0];w=x.loc[START:END].copy();w['industry_close']=s.reindex(w.index);assert w.industry_close.notna().all()
 sp=sectorpos[sectorpos.sector.eq(sec)].set_index('day');w['actual_weight_pct_NAV']=[float(sp.loc[str(t.date()),'weight_pct_NAV']) if str(t.date()) in sp.index else 0. for t in w.index]
 w['actual_market_value']=[float(sp.loc[str(t.date()),'market_value']) if str(t.date()) in sp.index else 0. for t in w.index]
 w['day']=w.index;daily.append(w.reset_index(drop=True))
 for day,r in w[w.M3_candidate.ne(w.previous_state)].iterrows():
  trans.append(dict(sector=sec,industry=name,day=fmt(day),previous_state=r.previous_state,state=int(r.M3_candidate),n=int(r.M3_n),K=int(r.K),N=int(r.N),U=int(r.U),paired_K=int(r.common3_K),entered=int(r.M3_entered3),left=int(r.M3_left3),close=float(s[day])))
 # Complete TRUE runs overlapping the review; prior state context drawn only from past states.
 groups=x.M3_candidate.ne(prev).cumsum();true_runs=[]
 for _,g in x.groupby(groups):
  if g.M3_candidate.iloc[0]!=1 or g.index[-1]<START or g.index[0]>END:continue
  start,end=g.index[0],g.index[-1];first=g.iloc[0];end_visible=min(end,END);nexts=x[x.index>end_visible]
  q=dict(sector=sec,industry=name,start=fmt(start),visible_end=fmt(end_visible),actual_full_run_end_after_review_not_used=end>END,true_days_visible=int(((g.index>=START)&(g.index<=END)).sum()),first_previous_state=first.previous_state,n=int(first.M3_n),K=int(first.K),N=int(first.N),U=int(first.U),start_close=float(s[start]),first_nontrue=fmt(nexts.index[0]) if len(nexts) and nexts.index[0]<=END else None,first_nontrue_state=int(nexts.iloc[0].M3_candidate) if len(nexts) and nexts.index[0]<=END else None)
  for h in [5,20]:
   idx=s.index.get_loc(start);fwd=s.iloc[idx+1:idx+h+1];complete=len(fwd)==h and fwd.index[-1]<=END and fwd.notna().all()
   q[f'complete{h}_within_review']=bool(complete);q[f'ret{h}_pct']=float((fwd.iloc[-1]/s[start]-1)*100) if complete else None
   q[f'min_close{h}_pct']=float((fwd.min()/s[start]-1)*100) if complete else None;q[f'max_close{h}_pct']=float((fwd.max()/s[start]-1)*100) if complete else None
  true_runs.append(q);runs.append(q)
 if x.loc[ANCHOR,'M3_candidate']==1:
  relevant=next(q for q in true_runs if pd.Timestamp(q['start'])<=ANCHOR<=pd.Timestamp(q['visible_end']))
 else:relevant=next((q for q in true_runs if pd.Timestamp(q['start'])>=ANCHOR),None)
 bought=actions[actions.sector.eq(sec)&actions.side.eq('buy_core')&actions.day.between(str(START.date()),str(END.date()))]
 allact=actions[actions.sector.eq(sec)&actions.day.between(str(START.date()),str(END.date()))]
 mm=maps[maps.sector.eq(sec)&maps.start.le('2024-09-24')&maps.end.ge('2024-09-24')]
 cycle=mm.iloc[0] if len(mm)==1 else None
 q=dict(sector=sec,industry=name,research_N=int(w.N.iloc[0]),current_all_members=int(maps[maps.sector.eq(sec)].current_all_members.dropna().iloc[0]),state_0923=int(x.loc['2024-09-23','M3_candidate']),state_0924=int(x.loc[ANCHOR,'M3_candidate']),state_0926=int(x.loc['2024-09-26','M3_candidate']),state_0930=int(x.loc['2024-09-30','M3_candidate']),state_1008=int(x.loc['2024-10-08','M3_candidate']),state_1031=int(x.loc[END,'M3_candidate']),true_days=int(w.M3_candidate.eq(1).sum()),false_days=int(w.M3_candidate.eq(0).sum()),unknown_days=int(w.M3_candidate.eq(-1).sum()),true_runs_overlapping_review=len(true_runs),first_relevant_true=relevant['start'] if relevant else None,first_relevant_previous_state=relevant['first_previous_state'] if relevant else None,first_relevant_n=relevant['n'] if relevant else None,first_relevant_K=relevant['K'] if relevant else None,first_relevant_U=relevant['U'] if relevant else None,first_relevant_TRUE_days=relevant['true_days_visible'] if relevant else None,first_nontrue=relevant['first_nontrue'] if relevant else None,first_nontrue_state=relevant['first_nontrue_state'] if relevant else None,ret5_after_detection_pct=relevant['ret5_pct'] if relevant else None,ret20_after_detection_pct=relevant['ret20_pct'] if relevant else None,min20_after_detection_pct=relevant['min_close20_pct'] if relevant else None,max20_after_detection_pct=relevant['max_close20_pct'] if relevant else None,return_0923_1008_pct=100*(s.loc['2024-10-08']/s.loc['2024-09-23']-1),return_0923_1031_pct=100*(s.loc[END]/s.loc['2024-09-23']-1),first_account_buy=bought.day.min() if len(bought) else None,buy_core_actions=int((allact.side=='buy_core').sum()),buy_add_actions=int((allact.side=='buy_add').sum()),sell_actions=int(allact.side.str.startswith('sell').sum()),peak_account_weight_pct=float(w.actual_weight_pct_NAV.max()),peak_account_weight_day=fmt(w.actual_weight_pct_NAV.idxmax()) if w.actual_weight_pct_NAV.max()>0 else None,weight_0924_pct=float(w.loc[ANCHOR,'actual_weight_pct_NAV']),weight_1008_pct=float(w.loc['2024-10-08','actual_weight_pct_NAV']),weight_1031_pct=float(w.loc[END,'actual_weight_pct_NAV']),original_map_record=cycle.record_id if cycle is not None else None,original_map_start=cycle.start if cycle is not None else None,original_map_peak=cycle.end if cycle is not None else None,original_map_grade=cycle.unified_grade if cycle is not None else '当时无唯一上升周期覆盖，不重选',map_is_not_realtime_permission=True)
 if relevant:
  t=pd.Timestamp(relevant['start']);q['industry_E0_on_detection']=bool(x.loc[t,'sector_E0_valid']) if pd.notna(x.loc[t,'sector_E0_valid']) else None;q['original_industry_stage_on_detection']=x.loc[t,'sector_stage']
  q['price_change_from_0923_at_detection_pct']=100*(s[t]/s.loc['2024-09-23']-1)
  q['detection_to_1008_pct']=100*(s.loc['2024-10-08']/s[t]-1) if t<=pd.Timestamp('2024-10-08') else None
  q['next_common_open']=fmt(s.index[s.index.get_loc(t)+1])
 rows.append(q)
allrows=pd.DataFrame(rows);allrows.to_csv(O/'ALL_90_SECTOR_REVIEW.csv',index=False)
allruns=pd.DataFrame(runs);allruns.to_csv(O/'ALL_TRUE_RUNS_WITH_FIXED_HORIZONS.csv',index=False)
pd.DataFrame(trans).to_csv(O/'ALL_STATE_TRANSITIONS.csv',index=False)
panel=pd.concat(daily,ignore_index=True);panel.to_csv(O/'DAILY_STATE_PRICE_AND_INDUSTRY_POSITION.csv',index=False)
glob=panel.groupby('day').agg(true=('M3_candidate',lambda s:int(s.eq(1).sum())),false=('M3_candidate',lambda s:int(s.eq(0).sum())),unknown=('M3_candidate',lambda s:int(s.eq(-1).sum())),held_industries=('actual_weight_pct_NAV',lambda s:int(s.gt(0).sum())),all_stock_weight_pct_NAV=('actual_weight_pct_NAV','sum')).reset_index()
acc=account.set_index('day')
for z in glob.itertuples():assert abs(z.all_stock_weight_pct_NAV-float(acc.loc[fmt(z.day),'stock_weight_pct']))<1e-10
glob.to_csv(O/'DAILY_ALL90_STATE_AND_ACCOUNT.csv',index=False)
known=allrows.ret20_after_detection_pct.notna();summary=dict(sectors=90,review_days=37,detected_by_1031=int(allrows.first_relevant_true.notna().sum()),not_detected=allrows[allrows.first_relevant_true.isna()][['sector','industry']].to_dict('records'),false_to_true_relevant=int(allrows.first_relevant_previous_state.eq(0).sum()),unknown_to_true_relevant=int(allrows.first_relevant_previous_state.eq(-1).sum()),fixed20_known=int(known.sum()),fixed20_positive=int(allrows.loc[known,'ret20_after_detection_pct'].gt(0).sum()),fixed20_nonpositive=int(allrows.loc[known,'ret20_after_detection_pct'].le(0).sum()),all90_0923_1008_positive=int(allrows.return_0923_1008_pct.gt(0).sum()),median_0923_1008_pct=float(allrows.return_0923_1008_pct.median()),median_0923_1031_pct=float(allrows.return_0923_1031_pct.median()),actual_entered_by_1008=int(allrows.first_account_buy.le('2024-10-08').fillna(False).sum()),actual_entered_by_1031=int(allrows.first_account_buy.notna().sum()),no_account_runs=True,no_new_threshold=True,not_win_rate=True)
out('SUMMARY.json',summary);out('SOURCE_HASHES.json',src)
out('OUTPUT_SEAL.json',dict(outputs={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.csv','.json'] and p.name!='OUTPUT_SEAL.json'},sources_unchanged=all(sha(p)==h for p,h in src.items()),economic_runs=0))
print(json.dumps(summary,ensure_ascii=False,indent=2));print(glob[glob.day.isin(pd.to_datetime(['2024-09-23','2024-09-24','2024-09-25','2024-09-26','2024-09-27','2024-09-30','2024-10-08','2024-10-31']))].to_string(index=False))
