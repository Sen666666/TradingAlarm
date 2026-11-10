"""Additional fixed descriptive counts from completed frozen analysis, no new gates."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
d=pd.read_parquet(O/'DAILY_STATES_WITH_PRICE_LABELS.parquet');s=pd.read_parquet(O/'SPELLS_AND_FIRST_DAY_PRICE_LABELS.parquet')
# Spell counts and active-day mass are different; show long-run tail and censoring.
mass=[]
for (win,ch),g in s.groupby(['study_window','channel']):
 c=g[g.complete_uncensored_spell];den=int(c.active_common_sessions.sum());allmass=int(g.active_common_sessions.sum())
 z={'study_window':win,'channel':ch,'observed_spells':len(g),'all_observed_active_days':allmass,'complete_spells':len(c),'complete_active_days':den,
  'complete_duration_mean':float(c.active_common_sessions.mean()),'complete_duration_p90':float(c.active_common_sessions.quantile(.9)),
  'complete_duration_p95':float(c.active_common_sessions.quantile(.95)),'complete_duration_max':int(c.active_common_sessions.max()),
  'censored_active_day_mass':allmass-den,'censored_active_day_fraction':(allmass-den)/allmass if allmass else np.nan}
 for h in [1,3,5]:
  q=c[c.active_common_sessions.le(h)];z[f'short_le{h}_spell_count']=len(q);z[f'short_le{h}_complete_spell_fraction']=len(q)/len(c) if len(c) else np.nan
  z[f'short_le{h}_active_day_mass']=int(q.active_common_sessions.sum());z[f'short_le{h}_complete_active_day_fraction']=float(q.active_common_sessions.sum()/den) if den else np.nan
 mass.append(z)
m=pd.DataFrame(mass);m.to_csv(O/'DURATION_TAIL_AND_ACTIVE_DAY_MASS.csv',index=False)
# Current failed conjuncts at observed exits; this is not a sequential first-rejection explanation.
ex=[]
for ch in ['CONT','START']:
 g=d[d[ch+'_prevsession'].eq(True)&d[ch].eq(False)]
 for r in g.itertuples():
  if ch=='CONT':a=not(r.rs_ind20>0);b=not(5*r.N_above20_t>=3*r.N_U_t);an='R20_not_positive';bn='B_below_60pct'
  else:a=not(5*r.R5_midrank_integer_numerator>=8*r.N_R5_known);b=not(r.N_above20_t>r.N_above20_tminus5);an='pR5_below_80pct';bn='paired_B_change_not_positive'
  assert a or b
  ex.append({'date':r.date,'study_window':r.study_window,'channel':ch,'sector_id_static':r.sector_id_static,'industry_static':r.industry_static,
   'gate_A_name':an,'gate_A_false':bool(a),'gate_B_name':bn,'gate_B_false':bool(b),'failed_gate_pattern':'BOTH' if a and b else 'A_ONLY' if a else 'B_ONLY',
   'UNION_still_true':bool(r.UNION),'U_joiners1':r.U_joiners1,'U_leavers1':r.U_leavers1,'U_changed_same_day':bool(r.U_joiners1+r.U_leavers1>0),
   'rs_ind20':r.rs_ind20,'p_rs5':r.p_rs5,'B_now':r.B_now,'dB5_paired':r.dB5_paired,
   'scope':'Known opportunity-channel exit, not stock sale; U-change association does not identify composition-caused exit.'})
e=pd.DataFrame(ex);e.to_csv(O/'KNOWN_CHANNEL_EXITS_CURRENT_FAILED_GATES.csv',index=False)
e.groupby(['study_window','channel','failed_gate_pattern']).agg(exits=('date','size'),union_still_true=('UNION_still_true','sum'),U_changed_same_day=('U_changed_same_day','sum')).reset_index().to_csv(O/'EXIT_GATE_PATTERNS_BY_WINDOW.csv',index=False)
dc=pd.read_parquet(O/'DAILY_COUNTS_TRANSITIONS_JACCARD.parquet')
dc.groupby(['month','channel']).agg(days=('date','size'),mean_active=('active','mean'),median_active=('active','median'),known_entries=('known_entries','sum'),known_exits=('known_exits','sum'),mean_jaccard=('jaccard_known_pair','mean'),unknown_current=('unknown_current','sum')).reset_index().to_csv(O/'TRANSITIONS_BY_MONTH.csv',index=False)
# Short licenses are not a binary truth label; keep all frozen 1/3/5 by 5/20 intersections.
c=pd.read_parquet(O/'SHORT_LICENSE_X_FUTURE_NONPOSITIVE.parquet');out=[]
for keys,g in c.groupby(['study_window','channel','short_horizon','path_horizon','path_type']):
 z=dict(zip(['study_window','channel','short_horizon','path_horizon','path_type'],keys));n=int(g.complete_spell_price_valid_denominator.iloc[0]);short=int(g.loc[g.short_license,'count'].sum());joint=int(g.loc[g.short_license&g.final_nonpositive,'count'].sum());long=n-short;badlong=int(g.loc[~g.short_license&g.final_nonpositive,'count'].sum())
 z.update(complete_spell_price_valid_denominator=n,short_license_count=short,short_and_path_nonpositive_count=joint,
  joint_fraction_of_complete_spells=joint/n if n else np.nan,path_nonpositive_among_short=joint/short if short else np.nan,
  path_nonpositive_among_long=badlong/long if long else np.nan)
 out.append(z)
q=pd.DataFrame(out);q.to_csv(O/'SHORT_LICENSE_PATH_CROSSTAB_SUMMARY.csv',index=False)
print(m[['study_window','channel','short_le5_complete_spell_fraction','short_le5_complete_active_day_fraction','complete_duration_p90','complete_duration_max','censored_active_day_fraction']].to_string(index=False))
print(q[(q.short_horizon==5)&(q.path_horizon==20)&(q.path_type=='rel')].to_string(index=False))
