"""Supplement only: fixed source clocks, new-root birth bypass and concentration. No economics."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,math
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'first_late_contraction_preflight_v1';H={}
def src(p):
 p=Path(p);H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def csv(p,**kw):return pd.read_csv(src(p),**kw)
def clean(v):
 if isinstance(v,dict):return {str(k):clean(a) for k,a in v.items()}
 if isinstance(v,(list,tuple)):return [clean(a) for a in v]
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,pd.Timestamp):return v.strftime('%Y-%m-%d')
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
n=csv(O/'STRICT_NEGATIVE_54.csv');nxt=csv(O/'STRICT_NEGATIVE_NEXT_OPPORTUNITY.csv')
m=csv(R/'late_frontier_entry_preflight_v1/MARKET_RECEIPT_BASE_FACTS.csv',low_memory=False)
sids=n.sid.unique().tolist()
d=pd.read_parquet(src(R/'independent_channel_full1709_preflight_v1/DAILY_STATES.parquet'),columns=['sid','day','window','identity','root_day','born','failed','root_unknown','active','receipt','new_frontier','blocked'],filters=[('sid','in',sids)])
d['day']=pd.to_datetime(d.day).dt.strftime('%Y-%m-%d');d['root_day']=pd.to_datetime(d.root_day).dt.strftime('%Y-%m-%d');d['year']=d.window.map({'2022':2022,'2024_924':2024})
cols=['sid','day','old_sector_known','old_sector_observed_today','old_sector_rs_ready_fresh','old_sector_up','old_e0_target','old_i_target','old_i_buy','old_PVR_known','old_AB_event_id','old_ab_I_PVR_qualified_permit','conditional_unstarted_target_feasible','conditional_unstarted_open_feasible','close_size_check','open_size_check','next_common_open_day','next_daily_one_price_fact']
ov=pd.read_parquet(src(R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'),columns=cols,filters=[('sid','in',sids)])
ov['day']=pd.to_datetime(ov.day).dt.strftime('%Y-%m-%d');oi=ov.set_index(['sid','day'])
nr=[];allnew=[]
for q in n.itertuples():
 same=d[d.year.eq(q.year)&d.sid.eq(q.sid)&d.identity.eq(q.identity)&d.root_day.eq(q.root_day)&d.day.gt(q.signal_day)].sort_values('day')
 fail=same[same.failed.eq(True)];unknown=same[same.root_unknown.eq(True)]
 rootbirth=m[m.year.eq(q.year)&m.sid.eq(q.sid)&m.born.eq(True)&m.receipt.eq(True)&m.new_frontier.eq(True)&m.day.gt(q.signal_day)&m.root_day.ne(q.root_day)].sort_values('day')
 rr=[]
 for a in rootbirth.itertuples():
  v=oi.loc[(q.sid,a.day)]
  row=dict(year=q.year,round_id=q.round_id,sid=q.sid,name=q.name,original_root_day=q.root_day,original_signal_day=q.signal_day,new_root_day=a.root_day,new_born_receipt_day=a.day,new_identity=a.identity,same_source_identity=a.identity==q.identity,receipt_id=a.receipt_id,narrow_contraction_rule='EXEMPT_NEW_ROOT_BIRTH',original_four_industry_known_true=all(v[c]==True for c in ['old_sector_known','old_sector_observed_today','old_sector_rs_ready_fresh','old_sector_up']),original_stock_entry_flags_true=all(v[c]==True for c in ['old_e0_target','old_i_target','old_i_buy']),old_PVR_known=v.old_PVR_known,same_stock_AB_market_permit=v.old_ab_I_PVR_qualified_permit,old_AB_event_id=v.old_AB_event_id,original_AB_valid_close=a.AB_valid_close,old_conditional_close_feasible=v.conditional_unstarted_target_feasible,old_conditional_open_feasible=v.conditional_unstarted_open_feasible,next_common_open_day=v.next_common_open_day,next_daily_one_price_fact=v.next_daily_one_price_fact,original_all_offer_results=a.all_offer_results,scope='SIGNAL_ONLY_NO_NEW_COMPETITION_OR_EXECUTION')
  allnew.append(row);rr.append(row)
 out=dict(year=q.year,round_id=q.round_id,sid=q.sid,name=q.name,original_root_day=q.root_day,original_signal_day=q.signal_day,same_root_first_fail_day=fail.day.iloc[0] if len(fail) else None,same_root_first_unknown_day=unknown.day.iloc[0] if len(unknown) else None,later_new_root_born_receipts=len(rr),first_later_new_root_born_day=rr[0]['new_born_receipt_day'] if rr else None)
 for c in ['same_source_identity','original_four_industry_known_true','original_stock_entry_flags_true','old_PVR_known','same_stock_AB_market_permit','original_AB_valid_close','old_conditional_close_feasible','old_conditional_open_feasible','next_common_open_day','next_daily_one_price_fact']:
  out['first_new_root_'+c]=rr[0][c] if rr else None
 nr.append(out)
new=pd.DataFrame(nr);new=new.merge(nxt[['round_id','first_not_robust_negative_day']],on='round_id',validate='one_to_one')
new['any_later_path_visible']=new.first_not_robust_negative_day.notna()|new.first_later_new_root_born_day.notna()
new['first_path_signal_day']=[min([str(a),str(b)]) if pd.notna(a) and pd.notna(b) else str(a) if pd.notna(a) else str(b) if pd.notna(b) else None for a,b in zip(new.first_not_robust_negative_day,new.first_later_new_root_born_day)]
new.to_csv(O/'STRICT_NEGATIVE_NEW_ROOT_PATH.csv',index=False);pd.DataFrame(allnew).to_csv(O/'LATER_NEW_ROOT_BIRTH_RECEIPTS.csv',index=False)
conc=[];summary=[]
for y,g in n.groupby('year'):
 h=new[new.year.eq(y)]
 conc.append(dict(year=y,actual_n=len(g),independent_stocks=g.sid.nunique(),signal_days=g.signal_day.nunique(),sectors=g.sector.nunique(),sector_signal_days=len(g[['sector','signal_day']].drop_duplicates()),max_same_signal_day=int(g.groupby('signal_day').size().max()),max_same_sector_signal_day=int(g.groupby(['sector','signal_day']).size().max())))
 summary.append(dict(year=y,strict_negative=len(g),same_root_nonnegative=int(h.first_not_robust_negative_day.notna().sum()),later_new_root_birth=int(h.first_later_new_root_born_day.notna().sum()),same_root_nonnegative_missing_but_new_birth=int((h.first_not_robust_negative_day.isna()&h.first_later_new_root_born_day.notna()).sum()),either_path=int(h.any_later_path_visible.sum()),neither_path_within_saved_window=int((~h.any_later_path_visible).sum()),same_root_fail_seen=int(h.same_root_first_fail_day.notna().sum()),same_root_unknown_seen=int(h.same_root_first_unknown_day.notna().sum())))
pd.DataFrame(conc).to_csv(O/'STRICT_NEGATIVE_CONCENTRATION.csv',index=False);dump('TWO_PATH_OPPORTUNITY_SUMMARY.json',summary)
# Fixed early cases: birth bypass and EVERY non-NEGATIVE direction bypass, irrespective of stock state.
fixed=pd.read_csv(O/'FIXED_EARLY_CASES.csv')
for ix,q in fixed.iterrows():
 if q['born']==True:note='EXEMPT_BIRTH'
 elif q['peer_delta1_robust']!='NEGATIVE':note='NO_CONTRACTION_VETO_'+q['peer_delta1_robust']
 elif q.get('participation') in ['REPEAT_PRICE','FIRST_PRICE_AFTER_AB']:note='EXEMPT_PRIOR_WINDOW_BUY'
 elif q['recomputed_prewindow_root']==True:note='PREWINDOW_HISTORY_UNKNOWN_OUTSIDE_STRICT_SCOPE'
 else:note='REQUIRES_CURRENT_UNSTARTED_PARENT_AND_FIRST_WINDOW_BUY_CHECK'
 fixed.at[ix,'narrow_scope_note']=note
fixed.to_csv(O/'FIXED_EARLY_CASES.csv',index=False)
# Exempt original late reentries are visible and must remain outside this narrow scope.
x=csv(R/'price_entry_right_breadth_diagnosis_v1/ALL_PRICE_ENTRY_FACTS.csv',low_memory=False)
ex=x[x.actual_buy&x.ticket.eq('CONTINUING_FRONTIER')&x.participation.isin(['REPEAT_PRICE','FIRST_PRICE_AFTER_AB'])]
ex.groupby(['year','participation','entry_root_relation']).size().rename('actual_n').reset_index().to_csv(O/'EXEMPT_ACTUAL_REENTRY_COUNTS.csv',index=False)
dump('SUPPLEMENT_SOURCE_HASHES.json',H)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in H.items())
dump('SUPPLEMENT_QA.json',dict(sources_unchanged=True,targeted_saved_daily_stocks=len(sids),economic_runs=0,consumer_imports=0,parameter_searches=0,raw_market_reloads=0,signal_only_no_counterfactual_fills=True))
print('CONCENTRATION',json.dumps(clean(conc),ensure_ascii=False));print('TWO_PATH',json.dumps(clean(summary),ensure_ascii=False));print('NO_SAME_ROOT_NONNEG',new[new.first_not_robust_negative_day.isna()][['year','sid','name','original_signal_day','same_root_first_fail_day','same_root_first_unknown_day','first_later_new_root_born_day','any_later_path_visible']].to_string(index=False));print('FIXED',fixed[fixed.sid.isin(['002583.SZ','688660.SH','300666.SZ'])][['sid','name','signal_day','root_day','born','peer_delta1_robust','narrow_scope_note']].to_string(index=False))
