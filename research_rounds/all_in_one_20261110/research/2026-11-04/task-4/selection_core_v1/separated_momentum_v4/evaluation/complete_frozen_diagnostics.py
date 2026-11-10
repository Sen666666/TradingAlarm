"""Frozen duration, P/T attribution and all90 fixed-window source-event diagnostics."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from reuse_v3_helpers import load_frozen_helpers
from evaluate_v4_core import METHODS,MAIN
O=Path(__file__).resolve().parent;V4=O.parent;H=load_frozen_helpers();sha={}
def bind(p):p=Path(p);sha[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def save(name,f):f.to_parquet(O/(name+'.parquet'),index=False);f.to_csv(O/(name+'.csv'),index=False)
def b(v):return None if pd.isna(v) else bool(v)
def first(g,mask):return str(g.loc[mask,'date'].iloc[0]) if mask.any() else None
d=pd.read_parquet(bind(O/'PUBLIC_STATE_AND_LABEL_PANEL.parquet')).sort_values(['sector_id_static','date']).reset_index(drop=True)
assert len(d)==97650 and d.groupby('date').size().eq(90).all()
# Paired-comparable reporting views; the original continuous public states remain untouched.
spells=[];stats=[]
for method,col in METHODS.items():
 view=d[['date','sector_id_static','study_window',col]].copy();view.loc[~d.computed_day90known,col]=pd.NA
 s=H.observed_true_runs(view,col);s['method']=method;spells.append(s)
 for grouping,n in [('study_window',None),('start_year',4),('start_month',7)]:
  periods=sorted(d.study_window.unique()) if n is None else sorted(d.date.str[:n].unique())
  for period in periods:
   g=s[s.study_window.eq(period)] if n is None else s[s.start.str[:n].eq(period)]
   c=g[g.complete_uncensored];mass=int(c.length.sum());z={'grouping':grouping,'period':period,'method':method,'observed_runs':len(g),'left_censored':int(g.left_censored.sum()),'right_censored':int(g.right_censored.sum()),'complete_uncensored_runs':len(c),'all_observed_selected_days':int(g.length.sum()),'complete_selected_days':mass}
   for key,value in H.distribution(c.length).items():z['duration_'+key]=value
   z['duration_max']=int(c.length.max()) if len(c) else np.nan
   for h in [1,3,5]:
    q=c[c.length.le(h)];z[f'duration_le{h}_run_fraction']=len(q)/len(c) if len(c) else np.nan;z[f'duration_le{h}_complete_day_fraction']=float(q.length.sum()/mass) if mass else np.nan
   if n is None:assert int(g.length.sum())==int(view.loc[view.study_window.eq(period),col].eq(True).sum())
   stats.append(z)
save('DAILY_LIST_RUNS_WITH_ADMINISTRATIVE_CENSORING',pd.concat(spells,ignore_index=True));save('LIST_DURATION_PHASE_START_YEAR_MONTH',pd.DataFrame(stats))
turn=pd.read_parquet(bind(O/'DAILY_AND_TRUE_WEEKEND_TURNOVER.parquet'));ts=[]
for grouping,n in [('year',4),('month',7)]:
 turn[grouping]=turn.date.str[:n]
 for keys,g in turn.groupby([grouping,'method','frequency']):
  period,method,freq=keys;z={'grouping':grouping,'period':period,'method':method,'frequency':freq,'snapshots':len(g),'known_pairs':int(g.pair_known.sum()),'entries':float(g.entered.sum()),'exits':float(g.left.sum())}
  for value in ['symmetric_turnover','jaccard']:
   for key,v in H.distribution(g[value]).items():z[value+'_'+key]=v
  ts.append(z)
save('TURNOVER_NATURAL_YEAR_MONTH',pd.DataFrame(ts))
tail=pd.read_parquet(bind(O/'ALL90_FUTURE_TAIL_EVALUATION_ONLY.parquet'))
d=d.merge(tail[['date','sector_id_static','REL_MFE20_PRIMARY_tail']],on=['date','sector_id_static'],validate='one_to_one')
mask=d.UNION_selected.eq(True)&d.computed_day90known
mode=pd.Series('UNKNOWN',index=d.index,dtype=object);mode.loc[d.P_mature.eq(True)&d.T_selected.eq(False)]='P_ONLY';mode.loc[d.P_mature.eq(False)&d.T_selected.eq(True)]='T_ONLY';mode.loc[d.P_mature.eq(True)&d.T_selected.eq(True)]='BOTH'
assert mode.loc[mask].isin(['P_ONLY','T_ONLY','BOTH']).all()
at=[]
for grouping in ['study_window','year','month']:
 for period in sorted(d[grouping].unique()):
  for name in ['P_ONLY','T_ONLY','BOTH']:
   q=d[mask&mode.eq(name)&d[grouping].eq(period)];valid=q.label_valid20.eq(True);rel=q.loc[valid,'final20_rel_log'].dropna();ab=q.loc[valid,'final20_abs_log'].dropna()
   at.append({'grouping':grouping,'period':period,'existing_T_union_group':name,'industry_days':len(q),'signal_days':q.date.nunique(),'label20_known':int(valid.sum()),'final20_relative_mean':float(rel.mean()) if len(rel) else np.nan,
    'absolute_final20_nonpositive_count':int(ab.le(0).sum()),'absolute_final20_nonpositive_rate':float(ab.le(0).mean()) if len(ab) else np.nan,'primary_tail_hits':int(q.REL_MFE20_PRIMARY_tail.sum()),'not_an_independent_confirmation_or_new_strategy':True})
save('P_ONLY_T_ONLY_BOTH_EXISTING_UNION_ATTRIBUTION',pd.DataFrame(at))
events=['P_state_event','P_known_new_maturity','P_known_exit','P_unknown_to_true','P_unknown_to_false','P_input_missing_counter_break','possible_states_before','possible_states_after','P_prevpublic']
save('P_REAL_SOURCE_STATE_EVENTS_UNCHANGED',d[['date','sector_id_static','P_score','P_order','P_mature']+events])
# Derive carry from the complete source series before clipping the predeclared windows.
POLICIES=[('P','P_mature'),('T','T_selected'),('union','UNION_selected'),('H1_N4','main_H1_selected'),
          ('v3_native','v3_native_UNION_selected'),('H1_N3_old','v3_H1_sameN3_selected'),('D_N4','main_D_selected')]
for tag,col in POLICIES:d['derived_previous_'+tag]=d.groupby('sector_id_static',sort=False)[col].shift()
windows=[('2024_924','2024-09-24','2024-12-31'),('2026H1','2026-01-01','2026-06-30')];wr=[]
for win,start,end in windows:
 for sector,g in d[d.date.ge(start)&d.date.le(end)].groupby('sector_id_static',sort=True):
  g=g.sort_values('date');head=g.iloc[0];z={'window':win,'sector_id_static':sector,'first_session':head.date,'last_session':g.date.iloc[-1],'sessions':len(g),'P_states_before_first_close':head.possible_states_before}
  if 'industry_static' in g:z['industry_static']=head.industry_static
  for tag,col in POLICIES:
   st=g[col];prev=g['derived_previous_'+tag];n=int(st.eq(True).sum());un=int(st.isna().sum());v=first(g,st.eq(True))
   z.update({tag+'_first_observed_true':v,tag+'_selected_days':n,tag+'_unknown_days':un,tag+'_no_observed_true':n==0,tag+'_never_selected_certain':n==0 and un==0,
    tag+'_prev_session_true_at_window_head':b(head['derived_previous_'+tag]),tag+'_window_first_close_true':b(head[col]),
    tag+'_continued_true_from_prev_at_first_close':b(head['derived_previous_'+tag]) is True and b(head[col]) is True,
    tag+'_administrative_window_head_true':b(head[col]) is True,tag+'_first_known_false_to_true':first(g,prev.eq(False)&st.eq(True)),
    tag+'_known_false_to_true_count':int((prev.eq(False)&st.eq(True)).sum()),tag+'_unknown_to_true_count':int((prev.isna()&st.eq(True)).sum()),
    tag+'_first_known_true_to_false':first(g,prev.eq(True)&st.eq(False)),tag+'_known_true_to_false_count':int((prev.eq(True)&st.eq(False)).sum())})
  z['P_first_real_source_new_maturity']=first(g,g.P_known_new_maturity.eq(True));z['P_real_source_new_maturity_count']=int(g.P_known_new_maturity.eq(True).sum());z['P_first_real_source_exit']=first(g,g.P_known_exit.eq(True));z['P_real_source_exit_count']=int(g.P_known_exit.eq(True).sum())
  z['P_source_first_close_event']=str(head.P_state_event);z['P_source_new_maturity_at_first_close']=b(head.P_known_new_maturity)
  z['P_raw_top5_first_observed']=first(g,g.P_known.eq(True)&g.P_order.le(5));z['P_raw_top5_days']=int((g.P_known.eq(True)&g.P_order.le(5)).sum())
  wr.append(z)
fw=pd.DataFrame(wr);assert len(fw)==180;save('FIXED_TWO_WINDOWS_ALL90_FIRST_CARRY_MISSING',fw)
# Preserve producer's display table verbatim; compare stable counts/dates, not ambiguous carry naming.
prodpath=V4/'ranking/FIXED_WINDOWS_ALL90.csv';prod=pd.read_csv(bind(prodpath),dtype={'sector_id_static':str});prod.to_csv(O/'PRODUCER_FIXED_WINDOWS_ORIGINAL.csv',index=False)
j=fw.merge(prod,on=['window','sector_id_static'],validate='one_to_one',suffixes=('_eval','_producer'))
for tag in ['P','T','union']:
 assert j[tag+'_selected_days_eval'].equals(j[tag+'_selected_days_producer'])
 assert j[tag+'_unknown_days_eval'].equals(j[tag+'_unknown_days_producer'])
 # Source first-observed field, not the source real-new-maturity field.
 a=j[tag+'_first_observed_true'].fillna('NONE');bb=j[tag+'_first_observed_selected'].fillna('NONE');assert a.equals(bb)
assert j.P_real_source_new_maturity_count.equals(j.P_true_new_maturities)
assert j.P_real_source_exit_count.equals(j.P_true_removals)
focal_ids=set(prod.loc[prod.industry_static.isin(['半导体','通信设备','软件开发']),'sector_id_static'])
assert focal_ids=={'URFI881121','URFI881129','URFI881272'}
focal=fw[fw.sector_id_static.isin(focal_ids)];save('PREDECLARED_FOCAL_FIRSTS_NOT_FUTURE_SELECTED',focal)
# Jan15 and924 clocks include source states, not raw rank-only inference.
shots=d[d.date.isin(['2024-09-24','2026-01-15']) & d.sector_id_static.isin(focal_ids)]
save('PREDECLARED_FOCAL_SOURCE_STATE_SNAPSHOTS',shots)
bind(__file__);(O/'SUPPLEMENT_SOURCE_SHA256.json').write_text(json.dumps(sha,indent=2)+'\n')
(O/'SUPPLEMENT_RUN_STATUS.json').write_text(json.dumps({'status':'FROZEN_DURATION_ATTRIBUTION_FOCAL_COMPLETE','fixed_windows_all_industries':len(fw),'producer_counts_and_first_dates_exact':True,'core_state_or_score_reruns':0,'metadata_revision_note_kept':True},indent=2)+'\n')
print('SUPPLEMENT_COMPLETE: source first/carry semantics separate; producer180 counts and dates exact.')
