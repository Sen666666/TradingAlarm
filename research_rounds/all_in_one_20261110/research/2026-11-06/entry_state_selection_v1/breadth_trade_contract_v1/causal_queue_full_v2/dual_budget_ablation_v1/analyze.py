from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
P=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/breadth_trade_contract_v1/causal_queue_full_v2/dual_budget_ablation_v1')
def save(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=True))
orig=pd.read_csv(P.parent/'rounds_clockfixed/ALL_SHADOW_ROUNDS.csv');b=pd.read_csv(P/'baseline/ALL_SHADOW_ROUNDS.csv')
pd.testing.assert_frame_equal(orig,b[orig.columns],check_dtype=False,check_exact=True)
save('BASELINE_EQUIVALENCE.json',dict(rows=len(orig),all_original_fields_exact=True,fields=list(orig.columns),original_sha256=hashlib.sha256((P.parent/'rounds_clockfixed/ALL_SHADOW_ROUNDS.csv').read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256((P/'baseline/ALL_SHADOW_ROUNDS.csv').read_bytes()).hexdigest()))
if not(P/'dual/ALL_SHADOW_ROUNDS.csv').exists():print('BASELINE_EXACT_PASS',len(orig));raise SystemExit
n=pd.read_csv(P/'dual/ALL_SHADOW_ROUNDS.csv')
keys=['event_id','sid'];assert b[keys].equals(n[keys])
invariants=['entry_status','status','entry_day','entry_price','entry_q','entry_fee','entry_risk','floor_raw','exit_day','exit_price','exit_reason','unknown_day']
pd.testing.assert_frame_equal(b[invariants],n[invariants],check_dtype=False,check_exact=True)
ad=[]
for r in n.itertuples():
 for a in json.loads(r.add_admission_details if isinstance(r.add_admission_details,str) else "[]"):
  a.update(event_id=r.event_id,sid=r.sid,window=r.window,arm=r.arm,event_type=r.event_type);ad.append(a)
ad=pd.DataFrame(ad);filled=ad[ad.q.gt(0)]
assert filled.post_principal.le(3000+1e-8).all()and filled.post_giveback.le(6000+1e-8).all()
assert filled.round_net_before.gt(0).all()
ad.to_csv(P/'ALL_ADD_ADMISSIONS.csv',index=False)
summary=[]
for key,gg in n.groupby(['window','arm','event_type']):
 win,arm,typ=key;indices=gg.index
 for label,g in [('baseline',b.loc[indices]),('dual',gg)]:
  c=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];w=c[c.net_pnl.gt(0)];l=c[c.net_pnl.le(0)];entered=g.entry_status.eq('CONDITIONAL_OPEN_PROXY')
  summary.append(dict(window=win,arm=arm,event_type=typ,policy=label,selected=len(g),entered=int(entered.sum()),not_entered=int((~entered).sum()),unknown_entered=int((entered & ~g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND') & ~g.status.str.startswith('OPEN_')).sum()),closed=len(c),open=int(g.status.str.startswith('OPEN_').sum()),unknown_or_rejected=int((~g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')&~g.status.str.startswith('OPEN_')).sum()),closed_wins=len(w),win_rate=len(w)/len(c)if len(c)else np.nan,payoff_ratio=w.net_pnl.mean()/(-l.net_pnl.mean())if len(w)and len(l)else np.nan,average_win=w.net_pnl.mean(),average_loss=l.net_pnl.mean(),mean_return_on_buy_cash=c.net_return_on_buy_cash.mean(),adds_any_entered=int(g['adds'].fillna(0).gt(0).sum()),mean_entry_cash=(g.entry_gross+g.entry_fee).mean(),mean_buy_cash_closed=c.total_buy_cash.mean(),mean_added_cash_all_entered=g.loc[entered,'add_buy_cash'].mean(),mean_added_cash_when_added=g.loc[g['adds'].fillna(0).gt(0),'add_buy_cash'].mean(),closed_losses_over_3000=int(c.net_pnl.lt(-3000).sum()),closed_losses_over_entry_risk=int(c.net_pnl.lt(-c.entry_risk).sum()),worst_pnl=c.net_pnl.min(),max_old_protection_giveback=g.max_old_protection_giveback.max(),mean_max_giveback=g.max_old_protection_giveback.mean(),rounds_max_giveback_gt6000=int(g.max_old_protection_giveback.gt(6000).sum()),mean_max_inventory_fraction=g.max_inventory_reference_fraction.mean(),max_inventory_fraction=g.max_inventory_reference_fraction.max()))
s=pd.DataFrame(summary);s.to_csv(P/'GROUP_COMPARISON.csv',index=False)
pair=b[['event_id','sid','window','arm','event_type','name','day','entry_day','status','entry_risk','net_pnl','net_return_on_buy_cash','total_buy_cash','adds','added_quantity','max_old_protection_giveback','max_inventory_reference_fraction','actions']].merge(n[['event_id','sid','net_pnl','net_return_on_buy_cash','total_buy_cash','adds','added_quantity','max_old_protection_giveback','max_inventory_reference_fraction','actions']],on=keys,suffixes=('_base','_dual'),validate='one_to_one')
pair['pnl_delta']=pair.net_pnl_dual-pair.net_pnl_base
pair['giveback_delta']=pair.max_old_protection_giveback_dual-pair.max_old_protection_giveback_base
pair['baseline_class']=np.where(pair.net_pnl_base.gt(0),'win',np.where(pair.net_pnl_base.le(0),'loss','not_closed'))
pair['add_actions_changed']=pair.actions_base.ne(pair.actions_dual)
pair.to_csv(P/'ALL_PAIRED_ROUNDS.csv',index=False)
coh=[]
for key,g in pair.groupby(['window','arm','event_type']):
 c=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')]
 for cohort,z in [('original_winners',c[c.net_pnl_base.gt(0)]),('original_losers',c[c.net_pnl_base.le(0)]),('original_return_ge30pct',c[c.net_return_on_buy_cash_base.ge(.3)]),('original_top5pct_pnl',c[c.net_pnl_base.ge(c.net_pnl_base.quantile(.95))])]:
  coh.append(dict(window=key[0],arm=key[1],event_type=key[2],cohort=cohort,n=len(z),base_added=int(z.adds_base.gt(0).sum()),dual_added=int(z.adds_dual.gt(0).sum()),changed=int(z.add_actions_changed.sum()),improved=int(z.pnl_delta.gt(1e-7).sum()),hurt=int(z.pnl_delta.lt(-1e-7).sum()),mean_pnl_delta=z.pnl_delta.mean(),sum_pnl_delta_NOT_ACCOUNT=z.pnl_delta.sum(),mean_giveback_delta=z.giveback_delta.mean(),mean_buy_cash_base=z.total_buy_cash_base.mean(),mean_buy_cash_dual=z.total_buy_cash_dual.mean(),winner_to_loss=int((z.net_pnl_base.gt(0)&z.net_pnl_dual.le(0)).sum()),loss_to_win=int((z.net_pnl_base.le(0)&z.net_pnl_dual.gt(0)).sum())))
pd.DataFrame(coh).to_csv(P/'BASELINE_COHORTS.csv',index=False)
pair.sort_values('net_pnl_dual').head(30).to_csv(P/'WORST_DUAL_ROUNDS.csv',index=False)
pair.sort_values('pnl_delta').head(30).to_csv(P/'MOST_HURT_ROUNDS.csv',index=False)
pair.sort_values('pnl_delta',ascending=False).head(30).to_csv(P/'MOST_HELPED_ROUNDS.csv',index=False)
save('FINAL_QA.json',dict(rows=len(n),baseline_exact=True,entry_exit_status_invariants_exact=True,add_open_evaluations=len(ad),filled_adds=len(filled),principal_cap_all_pass=True,giveback_cap_all_pass=True,profit_before_all_positive=True,full_account_runs=0,parameters_scanned=0,source_version='PREDECLARED.json',interpretation='Independent overlapping event shadows, not portfolio returns; historical resource/cash overlay is not an integrated account'))
print(s[s.event_type.eq('FALSE_TO_TRUE')].to_string(index=False))
print('COHORTS',pd.DataFrame(coh).query("event_type=='FALSE_TO_TRUE'").to_string(index=False))
print('WORST',pair.sort_values('net_pnl_dual').head(6)[['event_id','sid','name','net_pnl_base','net_pnl_dual','pnl_delta','max_old_protection_giveback_base','max_old_protection_giveback_dual']].to_string(index=False))
