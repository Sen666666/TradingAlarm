"""Predeclared reporting only. Never reruns execution or selection."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,importlib.util
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('frozen_scenario',O/'run_scenario.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
s.verify_seal()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
def metric(g):
 c=g[g.status.isin(['COMPLETE_CONDITIONAL_STOCK_ROUND','SCENARIO_CLOSED_NOT_FACT','CORE_ONLY_CLOSED_ALGEBRAIC'])];p=c.net_pnl;r=c.net_return_on_buy_cash
 return dict(permits=len(g),closed=len(c),wins=int((p>0).sum()),losses=int((p<0).sum()),zero=int((p==0).sum()),unknown=int(g.status.str.contains('UNKNOWN').sum()),censored=int(g.status.str.contains('CENSORED').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),win_rate_closed=float((p>0).mean()) if len(c) else None,mean_return_on_buy_cash=float(r.mean()) if len(c) else None,median_return_on_buy_cash=float(r.median()) if len(c) else None,mean_pnl_cny=float(p.mean()) if len(c) else None,median_pnl_cny=float(p.median()) if len(c) else None,p10_return=float(r.quantile(.1)) if len(c) else None,p90_return=float(r.quantile(.9)) if len(c) else None,wins_ge30pct=int((r>=.3).sum()),loss_pnl_beyond3000=int((p< -3000).sum()),mean_winning_pnl=float(p[p>0].mean()) if (p>0).any() else None,mean_losing_pnl=float(p[p<0].mean()) if (p<0).any() else None,status_counts=g.status.value_counts().to_dict())
old=s.old.copy();old['report_cohort']='OLD_CLOSED_OR_UNRESOLVED';old['original_round_id']=old.round_id
entry_ids=set(old[old.status=='FACTOR_AT_ENTRY_UNKNOWN'].round_id)
br=pd.read_csv(s.BR/'BRIDGED_ROUNDS.csv');br=br[br.round_id.isin(entry_ids)].copy();assert len(br)==10 and (br.status=='COMPLETE_CONDITIONAL_STOCK_ROUND').all();br['report_cohort']='TEN_ENTRY_FACTOR_BRIDGES';br['original_round_id']=br.round_id
baseline=pd.concat([old[~old.round_id.isin(entry_ids)],br],ignore_index=True);assert len(baseline)==2432 and baseline.round_id.nunique()==2432
# Algebraic core-only diagnostic, valid only for core untouched until the original I exit.
corebase=baseline.copy();coreaudit=[]
for idx,r in corebase.iterrows():
 if r.status!='COMPLETE_CONDITIONAL_STOCK_ROUND':continue
 ap=s.AS/'inputs-v1/actions'/(r.sid+'.json');entry=pd.Timestamp(r.entry_day);exit=pd.Timestamp(r.exit_day)
 if not ap.exists():corebase.loc[idx,'status']='CORE_BASELINE_ACTION_COVERAGE_UNKNOWN';corebase.loc[idx,['net_pnl','net_return_on_buy_cash']]=np.nan;continue
 hit=[x for x in json.loads(ap.read_text())['events'] if entry<pd.Timestamp(x['effective_date'])<=exit]
 if hit:corebase.loc[idx,'status']='CORE_BASELINE_HELD_ACTION_UNKNOWN';corebase.loc[idx,['net_pnl','net_return_on_buy_cash']]=np.nan;continue
 q=int(r.entry_q);px=D(str(r.exit_price));_,fs,par=s.getmeta(r.sid,exit);sf=s.fee(q,px,fs,'sell',par)
 spent=D(q)*D(str(r.entry_price))+D(str(r.entry_fee));pnl=D(q)*px-sf-spent
 corebase.loc[idx,'status']='CORE_ONLY_CLOSED_ALGEBRAIC';corebase.loc[idx,'net_pnl']=float(pnl);corebase.loc[idx,'net_return_on_buy_cash']=float(pnl/spent);corebase.loc[idx,'total_buy_cash']=float(spent)
 coreaudit.append(dict(original_round_id=r.round_id,sid=r.sid,entry_day=r.entry_day,exit_day=r.exit_day,core_q=q,core_entry_price=r.entry_price,core_entry_fee=r.entry_fee,core_exit_price=r.exit_price,core_standalone_sell_fee=float(sf),net_pnl=float(pnl),buy_cash=float(spent),corporate_action_interval_count=0,rights_source=str(ap),rights_source_sha256=s.sha(ap)))
full=pd.read_csv(O/'full/ROUNDS.csv');assert len(full)==804 and full.groupby('mode').size().to_dict()=={'CORE_ONLY':402,'FULL_CORE_PLUS_ADD':402}
sets={m:g.copy() for m,g in full.groupby('mode')};targetids=set(s.target.round_id);assert all(set(g.original_round_id)==targetids for g in sets.values())
merged={}
for mode,g in sets.items():
 base=baseline if mode=='FULL_CORE_PLUS_ADD' else corebase
 new=g.copy();new['round_id']=new.original_round_id;new['report_cohort']='RECOVERED_402_NET80_SCENARIO'
 z=pd.concat([base[~base.round_id.isin(targetids)],new],ignore_index=True);assert len(z)==2432 and z.round_id.nunique()==2432
 z['birth_quarter']=pd.to_datetime(z.signal_day).dt.quarter;z['mode']=mode;merged[mode]=z
# Common closed comparison prevents comparing different closure denominators.
closed_status=['COMPLETE_CONDITIONAL_STOCK_ROUND','SCENARIO_CLOSED_NOT_FACT','CORE_ONLY_CLOSED_ALGEBRAIC']
x=merged['FULL_CORE_PLUS_ADD'].set_index('round_id');y=merged['CORE_ONLY'].set_index('round_id');common=set(x[x.status.isin(closed_status)].index)&set(y[y.status.isin(closed_status)].index)
x=x.loc[sorted(common)];y=y.loc[sorted(common)];pairs=pd.DataFrame({'round_id':x.index,'full_pnl':x.net_pnl.values,'core_pnl':y.net_pnl.values,'pnl_delta_add_mode':(x.net_pnl-y.net_pnl).values,'full_win':(x.net_pnl>0).values,'core_win':(y.net_pnl>0).values,'cohort':x.report_cohort.values})
q2=old[old.status.str.contains('UNKNOWN')&(pd.to_datetime(old.signal_day).dt.quarter==2)];cash=s.public_table
coverage=dict(q2_birth_unknown_permits=len(q2),held_cash_first_interruption_permits=len(cash),held_cash_distinct_stocks=cash.sid.nunique(),held_cash_distinct_sid_ex_dates=len(cash[['sid','status_day']].drop_duplicates()),intersection=len(set(q2.round_id)&set(cash.round_id)),q2_only=len(set(q2.round_id)-set(cash.round_id)),cash_only=len(set(cash.round_id)-set(q2.round_id)),cash_birth_quarter=pd.to_datetime(cash.merge(old[['round_id','signal_day']],on='round_id').signal_day).dt.quarter.value_counts().sort_index().to_dict(),cash_ex_year=pd.to_datetime(cash.status_day).dt.year.value_counts().sort_index().to_dict())
by=[]
for mode,z in merged.items():
 for field in ['report_cohort','birth_quarter','event_type']:
  for val,g in z.groupby(field):by.append(dict(mode=mode,group_field=field,group_value=val,**metric(g)))
 for (co,q),g in z.groupby(['report_cohort','birth_quarter']):by.append(dict(mode=mode,group_field='cohort_and_birth_quarter',group_value=f'{co}|Q{q}',**metric(g)))
summary={'scope':'Fixed original 2432 permits; bounded 402-path NET80 scenario continuation; no reselection, no full shared-account strategy, no PIT or actual-tax claim.','old_full':metric(old),'after_ten_entry_bridges_full':metric(baseline),'before402_core_only_algebraic':metric(corebase),'core_baseline_action_unknown':corebase[corebase.status.str.startswith('CORE_BASELINE')].round_id.tolist(),'recovered402':{m:metric(g) for m,g in sets.items()},'after402_fixed_permits':{m:metric(g) for m,g in merged.items()},'common_closed':{'count':len(common),'full':metric(x),'core':metric(y),'core_win_full_loss':int((pairs.core_win&~pairs.full_win).sum()),'core_loss_full_win':int((~pairs.core_win&pairs.full_win).sum()),'pnl_delta_full_minus_core_sum':float(pairs.pnl_delta_add_mode.sum()),'pnl_delta_note':'Independent-permit sum, not account return. Buy-cash denominators differ.'},'two_426_sets':coverage,'remaining_original_non402':baseline[baseline.status.str.contains('UNKNOWN')&~baseline.round_id.isin(targetids)].status.value_counts().to_dict(),'sources_unchanged':True}
# Only full scenario can be overlaid on the original full-mode evidence. All unknown are unknown, not losses.
z=merged['FULL_CORE_PLUS_ADD'];m=metric(z);den=m['closed']+m['unknown']+m['censored'];summary['full_extreme_identification_bounds_if_all_remaining_eventually_close']={'denominator_excludes_nofill':den,'lower_win_rate':m['wins']/den,'upper_win_rate':(m['wins']+m['unknown']+m['censored'])/den,'not_forecast':True}
s.verify_seal();out=O/'report';out.mkdir(exist_ok=False)
pd.DataFrame(coreaudit).to_csv(out/'BASELINE_CORE_ONLY_AUDIT.csv',index=False);corebase.to_csv(out/'BASELINE_CORE_ONLY.csv',index=False)
for mode,z in merged.items():z.to_csv(out/(mode+'_FIXED_PERMITS.csv'),index=False)
pairs.to_csv(out/'COMMON_CLOSED_PAIRS.csv',index=False);pd.DataFrame(by).to_csv(out/'DISTRIBUTION_GROUPS.csv',index=False);save(out/'SUMMARY.json',summary);save(out/'OUTPUT_HASHES.json',{p.name:s.sha(p) for p in out.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'});print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
