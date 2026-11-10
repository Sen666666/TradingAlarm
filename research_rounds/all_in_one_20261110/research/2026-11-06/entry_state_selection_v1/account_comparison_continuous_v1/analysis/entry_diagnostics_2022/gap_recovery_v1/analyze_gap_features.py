from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).resolve().parent;P=O.parent
keys=['account','sid','round_id']
a=pd.read_csv(P/'ENTRY_ANCHORS.csv');f=pd.read_csv(P/'ENTRY_FEATURES.csv');p=pd.read_csv(P/'ENTRY_PATH_LABELS.csv');p=p[p['mode'].eq('fixed_future_label')]
f=f.merge(a[keys+['signal_to_open_gap','fixed_day20_fee_anchor_return']],on=keys,validate='one_to_one').merge(p[keys+['day20_MFE','day20_return','day20_MAE']],on=keys,validate='one_to_one')
g=f[f.signal_to_open_gap<0].copy();assert len(g)==379 and g.round_outcome.eq('WIN').sum()==56;g.to_csv(O/'GAP_FEATURES.csv',index=False)
w=g[g.round_outcome.eq('WIN')];cols=keys+['entry_quarter','first_role','execution_at','round_pnl','signal_to_open_gap','PVR_r','PVR_amount_ratio','PVR_score','day20_MFE','day20_return','fixed_day20_fee_anchor_return','signal_floor_risk_distance','execution_floor_risk_distance']
for col,label in [('round_pnl','PNL'),('day20_MFE','MFE20'),('day20_return','RETURN20')]:w.nlargest(10,col)[cols].to_csv(O/f'WINNERS_TOP10_{label}.csv',index=False)
nums=['signal_to_open_gap','signal_I_run_age_valid_bars','H1_score','H1_raw']+[f'H1_segment{i}_return' for i in range(1,5)]+['PVR_score','PVR_r','PVR_b','PVR_u','PVR_e','PVR_E','PVR_amount_ratio','signal_floor_risk_distance','execution_floor_risk_distance','extension_to_prior20_mean_close','extension20_log_sigma','day20_MFE','day20_return','fixed_day20_fee_anchor_return'];summ=[];num=[]
for dims in [[],['entry_quarter'],['entry_quarter','first_role']]:
 groups=[((),g)] if not dims else g.groupby(dims)
 for lab,z in groups:
  if not isinstance(lab,tuple):lab=(lab,)
  base=dict(zip(dims,lab));base['grouping']='+'.join(dims)or'ALL'
  for outcome,v in z.groupby('round_outcome'):
   summ.append(dict(**base,outcome=outcome,n=len(v),net_pnl=v.round_pnl.sum(),mean_pnl=v.round_pnl.mean(),median_pnl=v.round_pnl.median(),fixed20_positive=int(v.day20_return.gt(0).sum()),fixed20_MFE_positive=int(v.day20_MFE.gt(0).sum())))
   for col in nums:
    q=v[col];num.append(dict(**base,outcome=outcome,feature=col,n=len(v),known=q.notna().sum(),mean=q.mean(),median=q.median(),q25=q.quantile(.25),q75=q.quantile(.75)))
pd.DataFrame(summ).to_csv(O/'GAP_QUARTER_ROLE_OUTCOME.csv',index=False);pd.DataFrame(num).to_csv(O/'GAP_NUMERIC_DESCRIPTIVES.csv',index=False)
cat=[]
for col in ['industry_stage_name','industry_financial_level','first_buy_actual_pool','signal_above_prior20_high','signal_fresh_CP1']:
 for (quarter,role,value),z in g.groupby(['entry_quarter','first_role',col]):
  cat.append(dict(entry_quarter=quarter,first_role=role,feature=col,value=str(value),n=len(z),wins=int(z.round_outcome.eq('WIN').sum()),win_rate=z.round_outcome.eq('WIN').mean(),net_pnl=z.round_pnl.sum()))
pd.DataFrame(cat).to_csv(O/'GAP_CATEGORICAL_DESCRIPTIVES.csv',index=False)
res={'n':len(g),'wins':len(w),'losses':len(g)-len(w),'win_pnl':w.round_pnl.sum(),'loss_pnl':g.loc[g.round_outcome.eq('LOSS'),'round_pnl'].sum(),'net_pnl':g.round_pnl.sum(),'top10_winner_pnl_sum':w.nlargest(10,'round_pnl').round_pnl.sum(),'winner_fixed20_return_positive':int(w.day20_return.gt(0).sum()),'loser_fixed20_return_positive':int(g.loc[g.round_outcome.eq('LOSS'),'day20_return'].gt(0).sum()),'source_sha256':{str(P/n):hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ['ENTRY_FEATURES.csv','ENTRY_ANCHORS.csv','ENTRY_PATH_LABELS.csv']},'new_accounts':0,'parameter_searches':0}
(O/'FEATURE_SUMMARY.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2));print(pd.DataFrame(summ).to_string(index=False))
