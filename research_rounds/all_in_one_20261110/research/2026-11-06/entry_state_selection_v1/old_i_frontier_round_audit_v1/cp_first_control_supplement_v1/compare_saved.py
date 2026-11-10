"""Exploratory controls of frozen original AB outcomes, never a strategy simulation."""
from pathlib import Path
import json,hashlib,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent;H={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p):
 p=Path(p);h=sha(p)
 if str(p) in H:assert H[str(p)]==h
 H[str(p)]=h;return p
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def out(n,x):assert not (O/n).exists();x.to_csv(O/n,index=False)
def read(p):return pd.read_csv(src(p),float_precision='round_trip',low_memory=False)
src(__file__);src(O/'PROTOCOL.json')
seal=json.loads(src(B/'FINAL_OUTPUT_HASHES.json').read_text())
for n in ['ALL_REGISTERED_ROUNDS_ATTRIBUTED.csv','ALL_AB_DECISIONS_WITH_OUTCOME_CLASS.csv','SIGNAL_STATE_PRELABEL.csv','PROTOCOL.json','FEATURE_SEAL.json']:
 assert sha(src(B/n))==seal[n]
z=read(B/'ALL_REGISTERED_ROUNDS_ATTRIBUTED.csv');d=read(B/'ALL_AB_DECISIONS_WITH_OUTCOME_CLASS.csv')
assert z.sector.notna().all() and d.sector.notna().all()
assert d.groupby('sector').industry.nunique().max()==1 and d.groupby('industry').sector.nunique().max()==1
z['signal_month']=z.signal_day.str[:7];d['signal_month']=d.day.str[:7]
assert z.loc[z.cp_group.eq('CP_FIRST_IN_I'),'cp_receipt'].all()
assert z.loc[z.cp_group.eq('CP_FIRST_IN_I'),'cp_known_ordinal'].eq(1).all()
assert d.loc[d.cp_group.eq('CP_FIRST_IN_I'),'cp_receipt'].all()
assert d.loc[d.cp_group.eq('CP_FIRST_IN_I'),'cp_known_ordinal'].eq(1).all()
assert z[z.full_outcome_usable].entry_risk.gt(0).all()
GROUPS=['CP_FIRST_IN_I','CP_REPEAT_IN_I','NO_CP_TODAY','CP_TRACE_OR_EPOCH_UNKNOWN']
TERMS=sorted(z.financial_path_group.unique())
def metric(g):
 c=g[g.full_outcome_usable];w=c[c.net_pnl>0];l=c[c.net_pnl<0];n=len(c)
 counts=g.groupby('signal_day').size();maxn=int(counts.max()) if len(counts) else 0
 m=dict(registered=len(g),actual_buys=int(g.had_actual_proxy_initial_buy.sum()),not_bought=int((~g.had_actual_proxy_initial_buy).sum()),usable_closed=n,W=len(w),L=len(l),zero=int(c.net_pnl.eq(0).sum()),win_rate=len(w)/n if n else None,mean_net=c.net_pnl.mean(),mean_win=w.net_pnl.mean(),mean_loss=l.net_pnl.mean(),payoff=w.net_pnl.mean()/abs(l.net_pnl.mean()) if len(w) and len(l) else None,net_sum=c.net_pnl.sum(),mean_full_return=c.net_return_on_buy_cash.mean(),mean_initial_R=c.full_net_R_initial_risk.mean(),tail_ge30=int(c.net_return_on_buy_cash.ge(.3).sum()),tail_gt3R=int(c.full_net_R_initial_risk.gt(3).sum()),tail_ge30_rate=float(c.net_return_on_buy_cash.ge(.3).mean()) if n else None,tail_gt3R_rate=float(c.full_net_R_initial_risk.gt(3).mean()) if n else None,n_dates=g.signal_day.nunique(),n_industries=g.sector.nunique(),n_stocks=g.sid.nunique(),max_day_registered=maxn,max_day_registered_share=maxn/len(g) if len(g) else None,max_day_dates='|'.join(counts[counts.eq(maxn)].index) if len(counts) else None,execution_unknown=int(g.status.str.contains('UNKNOWN').sum()),closed_financial_unknown=int(g.financial_path_group.eq('CLOSED_FINANCIAL_COVERAGE_UNKNOWN').sum()))
 for t in TERMS:m['terminal_'+t]=int(g.financial_path_group.eq(t).sum())
 assert sum(m['terminal_'+t] for t in TERMS)==len(g)
 return m
pooled=[];monthly=[]
for year in [2022,2024]:
 zy=z[z.year.eq(year)]
 for cp in GROUPS:
  g=zy[zy.cp_group.eq(cp)];m=metric(g);m['share_of_all_registered']=len(g)/len(zy)
  pooled.append(dict(year=year,cp_group=cp,**m))
 for mon in range(1,13) if year==2022 else range(9,13):
  month=f'{year}-{mon:02d}'
  for cp in GROUPS:
   monthly.append(dict(year=year,signal_month=month,cp_group=cp,**metric(zy[zy.signal_month.eq(month)&zy.cp_group.eq(cp)])))
pool=pd.DataFrame(pooled);out('CP_POOLED_COMPLETE_METRICS.csv',pool);out('CP_SIGNAL_MONTH_COMPLETE_METRICS.csv',pd.DataFrame(monthly))
out('TERMINAL_BUCKET_BY_ACTUAL_BUY.csv',z.groupby(['year','cp_group','financial_path_group','had_actual_proxy_initial_buy'],dropna=False).size().rename('registered').reset_index())
# Coexistence determined from all registrations, not from surviving outcome rows.
DIFF_METRICS=['mean_net','win_rate','mean_full_return','mean_initial_R','tail_ge30_rate','tail_gt3R_rate']
cells=[];summaries=[];matched_members=[]
for year in [2022,2024]:
 zy=z[z.year.eq(year)]
 for comp in ['CP_REPEAT_IN_I','NO_CP_TODAY']:
  pair='CP_FIRST_IN_I__VS__'+comp
  for unit,fields in [('DATE',['signal_day']),('DATE_INDUSTRY',['signal_day','sector'])]:
   both=zy[zy.cp_group.isin(['CP_FIRST_IN_I',comp])]
   allmember=[];eligiblemember=[];one=[]
   for key,g in both.groupby(fields,sort=True,dropna=False):
    if not isinstance(key,tuple):key=(key,)
    if g.cp_group.nunique()!=2:continue
    a=g[g.cp_group.eq('CP_FIRST_IN_I')];b=g[g.cp_group.eq(comp)];ma=metric(a);mb=metric(b);eligible=ma['usable_closed']>0 and mb['usable_closed']>0
    cr=dict(year=year,comparison=pair,comparator=comp,unit=unit,**dict(zip(fields,key)),industry='|'.join(sorted(g.industry.unique())),outcome_eligible=eligible)
    cr.update({'first_'+k:v for k,v in ma.items()});cr.update({'comp_'+k:v for k,v in mb.items()})
    for k in DIFF_METRICS:cr['diff_'+k]=ma[k]-mb[k] if eligible else None
    cells.append(cr);one.append(cr);allmember.extend(g.index.tolist())
    if eligible:eligiblemember.extend(g.index.tolist())
    for ix in g.index:
     matched_members.append(dict(year=year,comparison=pair,unit=unit,round_id=z.loc[ix,'round_id'],signal_day=z.loc[ix,'signal_day'],sector=z.loc[ix,'sector'],cp_group=z.loc[ix,'cp_group'],outcome_eligible_cell=eligible,full_outcome_usable=bool(z.loc[ix,'full_outcome_usable']),financial_path_group=z.loc[ix,'financial_path_group'],had_actual_proxy_initial_buy=bool(z.loc[ix,'had_actual_proxy_initial_buy'])))
   ag=z.loc[allmember];eg=z.loc[eligiblemember];v=pd.DataFrame(one);valid=v[v.outcome_eligible] if len(v) else pd.DataFrame()
   sr=dict(year=year,comparison=pair,comparator=comp,unit=unit,coexisting_cells=len(v),outcome_eligible_cells=len(valid),cells_missing_one_or_both_outcome_groups=len(v)-len(valid),coexisting_dates=ag.signal_day.nunique(),coexisting_industries=ag.sector.nunique(),coexisting_stocks=ag.sid.nunique(),eligible_dates=eg.signal_day.nunique(),eligible_industries=eg.sector.nunique(),eligible_stocks=eg.sid.nunique())
   for prefix,gg in [('coexisting',ag),('outcome_eligible',eg)]:
    for label,grp in [('first','CP_FIRST_IN_I'),('comp',comp)]:
     mm=metric(gg[gg.cp_group.eq(grp)]);sr.update({prefix+'_'+label+'_'+k:vv for k,vv in mm.items()})
   # Largest date weight for industry-cell EW: some dates contribute multiple equally weighted industries.
   if len(valid):
    cc=valid.groupby('signal_day').size();sr['eligible_max_day_cell_count']=int(cc.max());sr['eligible_max_day_cell_weight_share']=float(cc.max()/len(valid));sr['eligible_max_day_cell_dates']='|'.join(cc[cc.eq(cc.max())].index)
   else:sr.update(eligible_max_day_cell_count=0,eligible_max_day_cell_weight_share=None,eligible_max_day_cell_dates=None)
   sr['first_registered_coverage_fraction']=len(ag[ag.cp_group.eq('CP_FIRST_IN_I')])/len(zy[zy.cp_group.eq('CP_FIRST_IN_I')])
   for k in DIFF_METRICS:
    sr['equal_weight_first_'+k]=valid['first_'+k].mean() if len(valid) else None
    sr['equal_weight_comp_'+k]=valid['comp_'+k].mean() if len(valid) else None
    sr['equal_weight_diff_'+k]=valid['diff_'+k].mean() if len(valid) else None
   summaries.append(sr)
out('MATCHED_CELL_DETAILS.csv',pd.DataFrame(cells));out('MATCHED_CELL_MEMBERS.csv',pd.DataFrame(matched_members));ss=pd.DataFrame(summaries);out('EXACT_CONTROL_SUMMARY.csv',ss)
# Native original decision funnel and observed same date/industry selection capacity.
raw=[]
for year in [2022,2024]:
 p=R/'independent_channel_joint_economic_v1'/f'baseline_regression_{year}'/'DECISIONS.csv'
 x=read(p)[['event_id','PVR_score','queue_rank','selected_rank','close_check','close_q']];x['year']=year;raw.append(x)
d=d.merge(pd.concat(raw),on=['year','event_id'],validate='one_to_one')
d['is_feasible_original']=d.decision.isin(['SELECTED_PENDING','PASS_NOT_TOP2'])
d['is_selected_original']=d.decision.eq('SELECTED_PENDING')
d['is_first_CP']=d.cp_group.eq('CP_FIRST_IN_I')
slotrows=[]
for key,g in d.groupby(['year','day','sector']):
 first=g[g.is_first_CP]
 slotrows.append(dict(year=key[0],day=key[1],sector=key[2],industry=g.industry.iloc[0],all_birth_candidates=len(g),all_feasible_candidates=int(g.is_feasible_original.sum()),observed_selected_pending=int(g.is_selected_original.sum()),first_CP_candidates=len(first),first_CP_feasible=int(first.is_feasible_original.sum()),first_CP_selected=int(first.is_selected_original.sum()),first_CP_pass_not_top2=int(first.decision.eq('PASS_NOT_TOP2').sum()),nonfirst_CP_feasible=int((g.is_feasible_original&~g.is_first_CP).sum()),nonfirst_CP_selected=int((g.is_selected_original&~g.is_first_CP).sum()),selected_CP_groups='|'.join(g.loc[g.is_selected_original,'cp_group'])))
slots=pd.DataFrame(slotrows);assert slots.observed_selected_pending.le(2).all()
fd=d[d.is_first_CP].merge(slots,on=['year','day','sector','industry'],validate='many_to_one')
assert fd.loc[~fd.is_selected_original,'full_outcome_usable'].isna().all()
out('FIRST_CP_ALL_DECISIONS_WITH_SLOTS.csv',fd)
out('FIRST_CP_OBSERVED_DATE_INDUSTRY_SLOTS.csv',slots[slots.first_CP_candidates.gt(0)])
out('FIRST_CP_FUNNEL_COUNTS.csv',fd.groupby(['year','signal_month','decision','event_type'],dropna=False).size().rename('signals').reset_index())
out('FIRST_CP_FEASIBLE_SELECTED_SLOT_COUNTS.csv',fd[fd.is_feasible_original].groupby(['year','decision','observed_selected_pending','all_feasible_candidates','first_CP_feasible','first_CP_selected'],dropna=False).size().rename('signals').reset_index())
fsummary=[]
for year,g in fd.groupby('year'):
 gg=g[g.is_feasible_original];sel=g[g.is_selected_original];passs=g[g.decision.eq('PASS_NOT_TOP2')]
 fsummary.append(dict(year=year,all_first_CP_decisions=len(g),feasible=len(gg),selected=len(sel),pass_not_top2=len(passs),selection_rate_of_feasible=len(sel)/len(gg),n_dates=g.day.nunique(),n_industries=g.sector.nunique(),n_stocks=g.sid.nunique(),max_day_signals=int(g.groupby('day').size().max()),max_day_share=float(g.groupby('day').size().max()/len(g)),selected_mean_queue_rank=sel.queue_rank.mean(),pass_mean_queue_rank=passs.queue_rank.mean(),selected_mean_PVR=sel.PVR_score.mean(),pass_mean_PVR=passs.PVR_score.mean(),pass_not_top2_with_two_other_selected=int((passs.observed_selected_pending.eq(2)).sum()),unselected_assigned_PnL=False,decision_counts=g.decision.value_counts().to_dict()))
dump('FIRST_CP_FUNNEL_SUMMARY.json',fsummary)
assert all(sha(p)==h for p,h in H.items())
dump('SOURCE_HASHES.json',H)
dump('QA.json',dict(passed=True,original_output_hashes_unchanged=True,all_original_registered=len(z),all_original_decisions=len(d),pooled_registration_conserved=int(pool.registered.sum())==len(z),terminal_buckets_mutually_exclusive=True,actual_buy_is_separate_axis=True,CP_first_known_on_same_signal_day=True,matched_unit_not_relaxed=True,unselected_has_no_PnL=True,max_observed_selected_per_industry_date=int(slots.observed_selected_pending.max()),new_economics=0,new_consumers=0))
print(pool[['year','cp_group','registered','usable_closed','mean_net','mean_initial_R','win_rate','payoff','tail_ge30','tail_gt3R','max_day_registered_share']].to_string(index=False))
print(ss[['year','comparator','unit','coexisting_cells','outcome_eligible_cells','eligible_dates','eligible_industries','eligible_stocks','first_registered_coverage_fraction','equal_weight_diff_mean_net','equal_weight_diff_win_rate','equal_weight_diff_mean_initial_R','eligible_max_day_cell_weight_share']].to_string(index=False))
print(json.dumps(clean(fsummary),ensure_ascii=False),flush=True)
