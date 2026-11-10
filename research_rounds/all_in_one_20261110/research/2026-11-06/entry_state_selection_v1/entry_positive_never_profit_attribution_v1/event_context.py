from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
paths=[Path(__file__),R/'breadth_single_day_dependency_v1/ALL_M3_RESULTS.csv',R/'entry_protection_migration_mechanism_v1/BASELINE_PATH_DIAGNOSTICS.csv',R/'entry_current_downside_unsaturation_v1/FEATURES_AND_SELECTIONS.csv',R/'breadth_trade_contract_v1/ALL_EVENTS.csv',R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet',R/'selection_entry_diagnosis_v1/MARKET_FIXED1709_WARM.csv',R/'breadth_pvr3_priority_v1/simulate.py',R/'breadth_pvr3_priority_v1/rounds/ALL_SHADOW_ROUNDS.csv']
hashes={str(p):sha(p) for p in paths}
p=pd.read_csv(paths[1],dtype={'window':str},low_memory=False);p=p[p.event_type.eq('FALSE_TO_TRUE')].copy()
b=pd.read_csv(paths[2],dtype={'window':str},low_memory=False)
f=pd.read_csv(paths[3],dtype={'window':str},low_memory=False)
p=p.merge(b[['event_id','sid','never_profitable','entry_risk','profitable_close_days','first_profitable_close','hold_days']],on=['event_id','sid'],how='left',validate='one_to_one')
p=p.merge(f[['event_id','sid','r']],on=['event_id','sid'],how='left',validate='one_to_one')
p['target_positive_never']=p.baseline_selected&p.never_profitable.eq(True)&p.r.gt(0)
p['true_win']=p.label.eq('W')&p.core_net.gt(0)
ev=pd.read_csv(paths[4],dtype={'window':str});ev=ev[ev.arm.eq('M3')&ev.event_type.eq('FALSE_TO_TRUE')]
panel=pd.read_parquet(paths[5]).copy();panel['day']=panel.day.dt.strftime('%Y-%m-%d')
mk=pd.read_csv(paths[6]).rename(columns={'Unnamed: 0':'day','breadth20':'market_B20','delta5':'market_B20_delta5','known_n':'market_B20_knownN','regime':'market_regime'})
market=[]
for day,g in panel.groupby('day'):
 assert g.N.sum()==1709
 market.append(dict(day=day,market_M3_known_share=g.M3_n.sum()/g.K.sum(),market_M3_diffusion3=(g.M3_entered3.sum()-g.M3_left3.sum())/g.common3_K.sum() if g.common3_K.sum()>0 else np.nan,market_M3_qualified_sectors=int(g.M3_candidate.eq(1).sum()),market_M3_unknown_sectors=int(g.M3_candidate.eq(-1).sum())))
market=pd.DataFrame(market)
rows=[]
for eid,g in p.groupby('event_id'):
 a=g.iloc[0];s=g[g.baseline_selected];cl=s[s.label.isin(['W','L'])];z=s[s.target_positive_never];allclosed=g.label.isin(['W','L']).all()
 ntrue=int(g.true_win.sum());nw=int(g.label.eq('W').sum())
 if allclosed and nw==0:cls='ALL_COMPLETE_NO_FULL_WIN'
 elif allclosed and ntrue==0:cls='ALL_COMPLETE_ONLY_ADD_RESCUED_WIN'
 elif allclosed:cls='ALL_COMPLETE_HAS_TRUE_WIN'
 elif ntrue>0:cls='INCOMPLETE_HAS_TRUE_WIN'
 else:cls='INCOMPLETE_NO_TRUE_WIN_YET'
 rows.append(dict(event_id=eid,window=a.window,day=a.day,sector=a.sector,industry=a.industry,event_class=cls,candidate_n=len(g),closed_candidate_n=int(g.label.isin(['W','L']).sum()),unknown_n=int(g.label.isin(['UNKNOWN','U']).sum()),no_entry_n=int(g.label.eq('NO_ENTRY').sum()),full_winner_n=nw,true_winner_n=ntrue,all_candidates_complete=allclosed,selected_n=len(s),selected_closed_n=len(cl),selected_win_n=int(cl.label.eq('W').sum()),selected_tail30_n=int(cl.tail30.sum()),selected_net_sum_NOT_ACCOUNT=cl.net_pnl.sum(),selected_loss_sum_NOT_ACCOUNT=cl.loc[cl.label.eq('L'),'net_pnl'].sum(),selected_mean_net=cl.net_pnl.mean(),selected_worst_net=cl.net_pnl.min(),selected_plan_loss_sum=cl.entry_risk.sum(),selected_loss_over_plan_n=int((cl.core_net.lt(-cl.entry_risk)).sum()),selected_add_n=int(cl.adds.gt(0).sum()),selected_mean_hold_days=cl.hold_days.mean(),selected_never_profitable_n=int(cl.never_profitable.eq(True).sum()),target_positive_never_n=len(z),target_positive_never_loss_sum_NOT_ACCOUNT=z.net_pnl.sum(),target_positive_never_max_loss=-z.net_pnl.min() if len(z) else np.nan))
e=pd.DataFrame(rows).merge(ev[['event_id','N','K','n','share','diffusion','sector_action','original_sector_permission']],on='event_id',validate='one_to_one')
e=e.merge(panel[['day','sector','sector_stage','sector_E0_valid','PVR3_candidate','M3_entered3','M3_left3','common3_K']],on=['day','sector'],validate='many_to_one').merge(market,on='day',validate='many_to_one').merge(mk,on='day',how='left',validate='many_to_one')
e['market_regime']=e.market_regime.fillna('UNKNOWN');e['candidate_count_band']=pd.cut(e.candidate_n,[0,1,2,5,np.inf],labels=['1','2','3_to_5','6plus'])
e.to_csv(O/'EVENT_CONTEXT_AND_COST.csv',index=False)
summary=[]
for scope,v in [('ALL_MAIN_EVENTS',e),('EVENTS_WITH_POSITIVE_NEVER_TARGET',e[e.target_positive_never_n.gt(0)])]:
 for (w,cls),g in v.groupby(['window','event_class']):
  summary.append(dict(scope=scope,window=w,event_class=cls,events=len(g),dates=g.day.nunique(),sectors=g.sector.nunique(),event_fraction=len(g)/len(v[v.window.eq(w)]),candidate_n_median=g.candidate_n.median(),selected_n=g.selected_n.sum(),selected_closed=g.selected_closed_n.sum(),selected_wins=g.selected_win_n.sum(),selected_tail30=g.selected_tail30_n.sum(),selected_closed_net_sum_NOT_ACCOUNT=g.selected_net_sum_NOT_ACCOUNT.sum(),selected_mean_net=g.selected_net_sum_NOT_ACCOUNT.sum()/g.selected_closed_n.sum() if g.selected_closed_n.sum() else np.nan,event_mean_net_sum=g.selected_net_sum_NOT_ACCOUNT.mean(),event_median_net_sum=g.selected_net_sum_NOT_ACCOUNT.median(),event_worst_net_sum=g.selected_net_sum_NOT_ACCOUNT.min(),target_positive_never_n=g.target_positive_never_n.sum(),target_positive_never_loss_sum_NOT_ACCOUNT=g.target_positive_never_loss_sum_NOT_ACCOUNT.sum(),selected_never_profitable_n=g.selected_never_profitable_n.sum(),selected_loss_over_plan_n=g.selected_loss_over_plan_n.sum(),selected_add_n=g.selected_add_n.sum()))
ss=pd.DataFrame(summary);ss.to_csv(O/'EVENT_CLASS_SUMMARY.csv',index=False)
features=['candidate_n','share','diffusion','M3_entered3','M3_left3','market_M3_known_share','market_M3_diffusion3','market_M3_qualified_sectors','market_B20','market_B20_delta5','sector_stage','selected_mean_hold_days']
desc=[]
for (w,cls),g in e.groupby(['window','event_class']):
 for col in features:
  z=g[col].dropna();desc.append(dict(window=w,event_class=cls,metric=col,n=len(z),min=z.min(),q25=z.quantile(.25),median=z.median(),q75=z.quantile(.75),max=z.max(),mean=z.mean(),date_equal_mean=g.groupby('day')[col].mean().mean()))
pd.DataFrame(desc).to_csv(O/'EVENT_FEATURE_DISTRIBUTION.csv',index=False)
strata=[]
for scope,v in [('ALL_MAIN_EVENTS',e),('EVENTS_WITH_POSITIVE_NEVER_TARGET',e[e.target_positive_never_n.gt(0)])]:
 for dim in ['market_regime','candidate_count_band','original_sector_permission']:
  for (w,level),g in v.groupby(['window',dim],observed=True):
   cl=g[g.all_candidates_complete]
   strata.append(dict(scope=scope,window=w,dimension=dim,value=str(level),events=len(g),all_complete=len(cl),complete_no_full_win=int(cl.event_class.eq('ALL_COMPLETE_NO_FULL_WIN').sum()),complete_only_add_rescued=int(cl.event_class.eq('ALL_COMPLETE_ONLY_ADD_RESCUED_WIN').sum()),complete_has_true_win=int(cl.event_class.eq('ALL_COMPLETE_HAS_TRUE_WIN').sum()),no_full_win_fraction_among_complete=cl.event_class.eq('ALL_COMPLETE_NO_FULL_WIN').mean(),selected_closed=g.selected_closed_n.sum(),selected_win=g.selected_win_n.sum(),selected_tail30=g.selected_tail30_n.sum(),selected_net_sum_NOT_ACCOUNT=g.selected_net_sum_NOT_ACCOUNT.sum(),target_positive_never_n=g.target_positive_never_n.sum()))
pd.DataFrame(strata).to_csv(O/'EVENT_CONTEXT_STRATA.csv',index=False)
e.groupby(['window','day','event_class']).agg(events=('event_id','size'),selected_closed=('selected_closed_n','sum'),selected_net_sum_NOT_ACCOUNT=('selected_net_sum_NOT_ACCOUNT','sum'),target_positive_never_n=('target_positive_never_n','sum')).to_csv(O/'EVENT_DAY_FREQUENCY.csv')
co=p[p.target_positive_never][['event_id','sid','window','day']].merge(e[['event_id','event_class','all_candidates_complete','full_winner_n','true_winner_n','unknown_n','no_entry_n']],on='event_id')
co.to_csv(O/'TARGET_COVERAGE_FINAL.csv',index=False)
never=b[b.never_profitable.eq(True)];assert never.adds.eq(0).all();assert never.profitable_close_days.eq(0).all();assert never.first_profitable_close.isna().all();assert np.allclose(never.core_net,never.net_pnl)
save('NEVER_PROFITABLE_DEFINITION_QA.json',dict(counts=never.groupby('window').size().to_dict(),positive_day_counts=p[p.target_positive_never].groupby('window').size().to_dict(),all_actual_adds_zero=True,all_profitable_close_days_zero=True,all_first_profitable_close_missing=True,all_core_net_equals_full_net=True,definition='At each valid held close from entry day through day before exit: total accumulated cashflow + remaining inventory * raw close * (1-0.0005) - dated hypothetical one-order sale fees; first strict positive value. Cashflow includes all executed buys/sells/fees. Entry-day positive marking does not mean sellable under T+1. Intraday high and exit-day closing price not checked.',target_scope='Complete original PVR-selected main FALSE_TO_TRUE rounds only. In this never-positive subset no add actually occurred, so full-round mark is initial-only; never apply this interpretation to the full population with adds.'))
assert all(sha(p)==h for p,h in hashes.items());save('EVENT_SOURCE_HASHES.json',hashes)
save('EVENT_QA.json',dict(events=len(e),main_candidate_rows=len(p),selected_rows=int(p.baseline_selected.sum()),target_rows=int(p.target_positive_never.sum()),all_source_hashes_unchanged=True,no_new_signal=True,no_new_ranking=True,no_new_economic_simulation=True,outcome_conditioned_groups=True,all_complete_requires_every_candidate_label_W_or_L=True,full_winner_and_corepositive_winner_separate=True,nonPIT_fixed_universe=True,overlapping_shadows_not_account=True))
print('EVENT_CLASSES\n',ss.to_string(index=False))
print('MARKET_STRATA\n',pd.DataFrame(strata).query("scope=='ALL_MAIN_EVENTS' and dimension=='market_regime'").to_string(index=False))
print('FEATURES\n',pd.DataFrame(desc).query("window!='2026H1_SEMI' and event_class.str.startswith('ALL_COMPLETE') and metric in ['candidate_n','share','diffusion','market_M3_known_share','market_M3_diffusion3','market_B20','market_B20_delta5']").to_string(index=False))
