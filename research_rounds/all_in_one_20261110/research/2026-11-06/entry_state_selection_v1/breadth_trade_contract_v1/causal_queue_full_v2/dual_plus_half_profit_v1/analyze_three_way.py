from pathlib import Path
from decimal import Decimal as D
import pandas as pd,numpy as np,json,hashlib
P=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/breadth_trade_contract_v1/causal_queue_full_v2/dual_plus_half_profit_v1')
C=P.parent/'dual_budget_ablation_v1'
frames={k:pd.read_csv(path)for k,path in [('original',C/'baseline/ALL_SHADOW_ROUNDS.csv'),('dual',C/'dual/ALL_SHADOW_ROUNDS.csv'),('uhalf',P/'uhalf/ALL_SHADOW_ROUNDS.csv')]}
frames={k:v[v.arm.eq('M3')].reset_index(drop=True)for k,v in frames.items()}
b=frames['original'];d=frames['dual'];n=frames['uhalf'];assert len(b)==len(d)==len(n)==3715
invariants=['event_id','sid','entry_status','status','entry_day','entry_price','entry_q','entry_fee','entry_risk','floor_raw','exit_day','exit_price','exit_reason','unknown_day']
for v in [d,n]:pd.testing.assert_frame_equal(b[invariants],v[invariants],check_exact=True,check_dtype=False)
ads=[];layers=[];summary=[]
for label,v in frames.items():
 for r in v.itertuples():
  aa=json.loads(r.add_admission_details)if isinstance(r.add_admission_details,str)else[]
  for a in aa:
   if label=='uhalf':ads.append(dict(event_id=r.event_id,sid=r.sid,window=r.window,arm=r.arm,event_type=r.event_type,**a))
  actions=json.loads(r.actions)if isinstance(r.actions,str)else[];buy=next((x for x in actions if x['side']=='buy_add'),None)
  if buy:
   ex=next((x for x in actions if x['side']in('sell_add','sell_all')),None);cost=D(buy['q'])*D(buy['price'])+D(buy['fee']);pn=None
   if ex:pn=D(buy['q'])*D(ex['price'])-D(ex['fee'])*D(buy['q'])/D(ex['q'])-cost
   adm=next(x for x in aa if x['q']>0)
   layers.append(dict(policy=label,event_id=r.event_id,sid=r.sid,window=r.window,event_type=r.event_type,q=buy['q'],cost=float(cost),planned_loss=adm['add_risk'],entry_U=adm['round_net_before'],closed=ex is not None,layer_net=None if pn is None else float(pn),exit_day=None if ex is None else ex['day'],realized_loss_exceeds_plan=False if pn is None else -pn>D(str(adm['add_risk']))+D('1e-7'),realized_loss_exceeds_entry_Uhalf=False if pn is None else -pn>D(str(adm['round_net_before']))/2+D('1e-7')))
 for key,g in v.groupby(['window','event_type']):
  c=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];w=c[c.net_pnl.gt(0)];l=c[c.net_pnl.le(0)];ent=g.entry_status.eq('CONDITIONAL_OPEN_PROXY')
  summary.append(dict(window=key[0],event_type=key[1],policy=label,selected=len(g),entered=int(ent.sum()),closed=len(c),unknown_entered=int((ent&~g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')&~g.status.str.startswith('OPEN_')).sum()),open=int(g.status.str.startswith('OPEN_').sum()),not_entered=int((~ent).sum()),wins=len(w),win_rate=len(w)/len(c)if len(c)else np.nan,payoff=w.net_pnl.mean()/(-l.net_pnl.mean())if len(w)and len(l)else np.nan,mean_pnl=c.net_pnl.mean(),equal_weight_return=c.net_return_on_buy_cash.mean(),money_weighted_event_ratio=c.net_pnl.sum()/c.total_buy_cash.sum()if c.total_buy_cash.sum()>0 else np.nan,mean_buy_cash=c.total_buy_cash.mean(),adds_all_entered=int(g['adds'].fillna(0).gt(0).sum()),adds_closed=int(c['adds'].fillna(0).gt(0).sum()),mean_added_cash_when_added=g.loc[g['adds'].fillna(0).gt(0),'add_buy_cash'].mean(),loss_over_3000=int(c.net_pnl.lt(-3000).sum()),worst_pnl=c.net_pnl.min(),mean_max_giveback=g.max_old_protection_giveback.mean(),max_giveback=g.max_old_protection_giveback.max(),post_admission_principal_over_3000=int(g.max_principal_debt_at_protection.gt(3000+1e-8).sum())))
ad=pd.DataFrame(ads);filled=ad[ad.q.gt(0)]
assert filled.post_principal.le(3000+1e-8).all()and filled.post_giveback.le(6000+1e-8).all()and filled.add_risk.le(filled.half_profit_budget+1e-8).all()
ad.to_csv(P/'ALL_ADD_ADMISSIONS.csv',index=False);pd.DataFrame(layers).to_csv(P/'ALL_ADD_LAYER_RESULTS.csv',index=False);pd.DataFrame(summary).to_csv(P/'THREE_WAY_GROUPS.csv',index=False)
pair=b[['event_id','sid','name','window','event_type','day','status']].copy()
for label,v in frames.items():
 for col in ['net_pnl','net_return_on_buy_cash','total_buy_cash','adds','added_quantity','max_old_protection_giveback','actions']:pair[col+'_'+label]=v[col]
pair['delta_vs_original']=pair.net_pnl_uhalf-pair.net_pnl_original;pair['delta_vs_dual']=pair.net_pnl_uhalf-pair.net_pnl_dual;pair.to_csv(P/'ALL_THREE_WAY_ROUNDS.csv',index=False)
coh=[]
for key,g in pair.groupby(['window','event_type']):
 c=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')]
 for name,z in [('original_winners',c[c.net_pnl_original.gt(0)]),('original_losers',c[c.net_pnl_original.le(0)]),('original_return_ge30pct',c[c.net_return_on_buy_cash_original.ge(.3)]),('original_top5pct_PnL',c[c.net_pnl_original.ge(c.net_pnl_original.quantile(.95))])]:
  for control in ['original','dual']:
   delta=z.net_pnl_uhalf-z['net_pnl_'+control]
   coh.append(dict(window=key[0],event_type=key[1],cohort=name,control=control,n=len(z),control_adds=int(z['adds_'+control].gt(0).sum()),uhalf_adds=int(z.adds_uhalf.gt(0).sum()),improved=int(delta.gt(1e-7).sum()),hurt=int(delta.lt(-1e-7).sum()),mean_delta=delta.mean(),mean_buy_cash_control=z['total_buy_cash_'+control].mean(),mean_buy_cash_uhalf=z.total_buy_cash_uhalf.mean(),winner_to_loss=int((z['net_pnl_'+control].gt(0)&z.net_pnl_uhalf.le(0)).sum()),loss_to_win=int((z['net_pnl_'+control].le(0)&z.net_pnl_uhalf.gt(0)).sum())))
pd.DataFrame(coh).to_csv(P/'BASELINE_COHORTS.csv',index=False)
for col,name in [('net_pnl_uhalf','WORST_UHALF'),('delta_vs_original','MOST_HURT_VS_ORIGINAL'),('delta_vs_dual','MOST_HURT_VS_DUAL')]:pair.sort_values(col).head(20).to_csv(P/(name+'.csv'),index=False)
(P/'FINAL_QA.json').write_text(json.dumps(dict(rows=3715,entry_exit_status_exact=True,new_checks=len(ad),new_actual_adds=len(filled),three_budget_checks_pass=True,account_runs=0,parameter_scans=0,warning='Fixed M3 turnover-ranked events, not shared account. All caps are admission-only.'),indent=2))
print(pd.DataFrame(summary).query("event_type=='FALSE_TO_TRUE'").to_string(index=False));print('COHORTS',pd.DataFrame(coh).query("event_type=='FALSE_TO_TRUE'").to_string(index=False));print('LAYER',pd.DataFrame(layers).query("event_type=='FALSE_TO_TRUE'").groupby(['window','policy']).agg(adds=('q','count'),closed=('closed','sum'),negative=('layer_net',lambda x:int(x.lt(0).sum())),mean_net=('layer_net','mean'),exceed_plan=('realized_loss_exceeds_plan','sum'),exceed_Uhalf=('realized_loss_exceeds_entry_Uhalf','sum')).to_string())
