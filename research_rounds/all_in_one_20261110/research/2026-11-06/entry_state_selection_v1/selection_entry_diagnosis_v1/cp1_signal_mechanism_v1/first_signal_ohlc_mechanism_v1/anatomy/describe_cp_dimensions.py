import json,math,hashlib
from pathlib import Path
import pandas as pd,numpy as np
O=Path(__file__).parent
freeze=dict(scope='Only pre-existing SIGNAL_DAY_ANATOMY.csv. Original fresh CP only; no new source reading, strategies, ranks, accounts or parameter scans.',mechanism='u_abs=abs(tanh(original r/original s)); original m=1+0.5*u_abs*tanh(log(raw_amount/B)); T=sqrt(5)*scale; D and K original displacement and credit.',classes=['D<=K: displacement is the smaller evidence leg, equal values included','D/T>=2: algebraic loss of K veto because m in [0.5,1.5] implies K>=0.5D; 2 is a proved bound, not an optimized threshold','f/r<1 by >1e-12 absolute f-vs-r tolerance: part of current rise recovered old frontier; no simulated filter'],outcomes='Original closed/round_pnl only; all rows/open separately. PVR 2022 closed_in_entry_year 692/130 cross-check remains fixed.',strata=['account','entry year','win/loss/open','2022 closed_in_entry_year'])
(O/'DIMENSIONAL_FREEZE.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2))
d=pd.read_csv(O/'SIGNAL_DAY_ANATOMY.csv')
f=d[d.fresh_cp].copy()
f['T']=np.sqrt(5)*f.cp_scale
f['D_over_T']=f.cp_displacement/f['T']
f['K_over_T']=f.cp_credit/f['T']
f['K_over_D']=f.cp_credit/f.cp_displacement
f['u_abs']=np.tanh(f.cp_r/f.cp_s).abs()
f['v']=np.tanh(np.log(f.raw_amount/f.cp_B))
f['m_rebuilt']=1+.5*f.u_abs*f.v
f['m_error']=(f.m_rebuilt-f.cp_m).abs()
f['D_controls']=f.cp_displacement.le(f.cp_credit)
f['D_K_near_equal']=(f.cp_displacement-f.cp_credit).abs().le(1e-12)
f['K_cannot_veto']=f.D_over_T.ge(2)
f['recover_old_frontier']=f.cp_delta_frontier.lt(f.cp_r-1e-12)
f['K_lower_bound_error']=np.maximum(0,.5*f.cp_displacement-f.cp_credit)
f['K_upper_bound_error']=np.maximum(0,f.cp_credit-1.5*f.cp_displacement)
assert f[['cp_displacement','cp_credit','cp_scale','cp_r','cp_s','cp_m','cp_B','raw_amount']].notna().all().all()
assert f.K_lower_bound_error.max()<1e-12 and f.K_upper_bound_error.max()<1e-12
assert f.m_error.max()<1e-12
rows=[];iq=[]
for ac,a in d.groupby('account'):
 for scope,whole in [('all_first_entries',a),('2022_closed_in_entry_year',a[(a.year==2022)&a.closed_in_entry_year])]:
  for year,allg in [('ALL',whole)]+list(whole.groupby('year')):
   sub=f.loc[f.row_id.isin(allg.row_id)]
   for outcome,t in [('all',sub),('closed',sub[sub.closed]),('win',sub[sub.outcome=='win']),('loss',sub[sub.outcome=='loss']),('open',sub[sub.outcome=='open'])]:
    totalwins=int((allg.outcome=='win').sum());totallosses=int((allg.outcome=='loss').sum())
    for condition in ['all_fresh','D_controls','K_cannot_veto','recover_old_frontier']:
     selected=t if condition=='all_fresh' else t[t[condition]]
     wins=int((selected.outcome=='win').sum());losses=int((selected.outcome=='loss').sum())
     rows.append(dict(account=ac,scope=scope,year=year,outcome=outcome,condition=condition,fresh_denominator=len(t),n=len(selected),share_of_fresh_outcome=len(selected)/len(t) if len(t) else np.nan,wins=wins,losses=losses,open=int((selected.outcome=='open').sum()),whole_first_wins=totalwins,whole_first_losses=totallosses,whole_winner_coverage=wins/totalwins if totalwins else np.nan,whole_loser_coverage=losses/totallosses if totallosses else np.nan))
    for feature in ['u_abs','fresh_frontier_share','cp_m','D_over_T','K_over_T','K_over_D']:
     v=t[feature].replace([np.inf,-np.inf],np.nan).dropna();qs=v.quantile([.25,.5,.75]) if len(v) else pd.Series([np.nan]*3,index=[.25,.5,.75])
     iq.append(dict(account=ac,scope=scope,year=year,outcome=outcome,feature=feature,n=len(t),known_n=len(v),q25=qs.loc[.25],median=qs.loc[.5],q75=qs.loc[.75],iqr=qs.loc[.75]-qs.loc[.25]))
out=pd.DataFrame(rows);cont=pd.DataFrame(iq)
out.to_csv(O/'DIMENSIONAL_COVERAGE.csv',index=False,float_format='%.17g')
cont.to_csv(O/'DIMENSIONAL_CONTINUOUS_IQR.csv',index=False,float_format='%.17g')
f[['row_id','account','sid','signal_day','year','outcome','T','D_over_T','K_over_T','K_over_D','u_abs','v','m_rebuilt','m_error','D_controls','D_K_near_equal','K_cannot_veto','recover_old_frontier']].to_csv(O/'DIMENSIONAL_POINT_AUDIT.csv',index=False,float_format='%.17g')
meta=dict(fresh_points=len(f),m_max_abs_error=float(f.m_error.max()),D_K_near_equal=int(f.D_K_near_equal.sum()),all_original_m_bounds_hold=bool(f.cp_m.between(.5,1.5).all()),max_K_below_half_D=float(f.K_lower_bound_error.max()),max_K_above_1p5D=float(f.K_upper_bound_error.max()),all_D_K_original_thresholds_pass=bool((f.D_over_T.ge(1-1e-12)&f.K_over_T.ge(1-1e-12)).all()),all_K_cannot_veto_points_K_pass=bool(f[f.K_cannot_veto].K_over_T.ge(1-1e-12).all()),input_sha256=hashlib.sha256((O/'SIGNAL_DAY_ANATOMY.csv').read_bytes()).hexdigest(),new_source_reads=0,account_runs=0,ranking_runs=0,parameter_scans=0)
(O/'DIMENSIONAL_QUALITY.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
print('QUALITY',json.dumps(meta),flush=True)
print('PVR ALL COUNTS');print(out[(out.account=='PVR')&(out.year=='ALL')].to_string(index=False))
print('PVR BY YEAR COUNTS');print(out[(out.account=='PVR')&(out.scope=='all_first_entries')&(out.year!='ALL')&out.outcome.isin(['closed','win','loss'])].to_string(index=False))
print('PVR IQR');print(cont[(cont.account=='PVR')&(cont.scope=='all_first_entries')&cont.outcome.isin(['win','loss'])].to_string(index=False))
