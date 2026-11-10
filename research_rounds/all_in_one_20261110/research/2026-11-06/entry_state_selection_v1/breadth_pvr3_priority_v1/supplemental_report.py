"""Complete feasible-candidate denominator and actual-lot attribution; not a portfolio."""
from pathlib import Path
from decimal import Decimal as D
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
z=pd.read_csv(O/'rounds/ALL_SHADOW_ROUNDS.csv',low_memory=False);q=pd.read_csv(O/'EVALUATION_INPUT.csv',low_memory=False);s=pd.read_csv(O/'SEALED_CLOSE_SELECTED.csv',low_memory=False)
assert len(z)==len(q)==33162
keys=['window','arm','event_type'];diag=z[z.ranking_strategy.eq('ALL_FEASIBLE_DIAGNOSTIC')].copy();selected=z[~z.ranking_strategy.eq('ALL_FEASIBLE_DIAGNOSTIC')].copy();assert len(diag)==22196 and len(selected)==10966
assert not z.duplicated(['ranking_strategy','event_id','sid']).any()
identity=['ranking_strategy','event_id','sid']
assert set(map(tuple,z[identity].to_numpy()))==set(map(tuple,q[identity].to_numpy()))
assert set(map(tuple,selected[identity].to_numpy()))==set(map(tuple,s[identity].to_numpy()))
assert json.load(open(O/'QA.json'))['shared_original_baseline_rows']==5483
# Cash/fee/inventory reconciliation covers all candidate and selected rows, including unknown paths.
recon=[];legs=[]
for r in z[z.entry_status.eq('CONDITIONAL_OPEN_PROXY')].itertuples():
 coreq=int(r.entry_q);addq=0;core=-D(str(r.entry_q))*D(str(r.entry_price))-D(str(r.entry_fee));add=D(0);fees=D(str(r.entry_fee));spent=-core
 for a in json.loads(r.actions):
  qty=int(a['q']);p=D(a['price']);f=D(a['fee']);fees+=f
  if a['side']=='buy_add':add-=qty*p+f;addq+=qty;spent+=qty*p+f
  elif a['side']=='sell_add':assert qty==addq;add+=qty*p-f;addq=0
  else:
   assert a['side']=='sell_all' and qty==coreq+addq
   fc=f*D(coreq)/D(qty);fa=f-fc;core+=coreq*p-fc;add+=addq*p-fa;coreq=0;addq=0
 cf=core+add;assert abs(float(cf)-r.cashflow_to_date)<1e-7;assert abs(float(fees)-r.fees_to_date)<1e-7;assert coreq+addq==int(r.core_qty+r.add_qty)
 if r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND':
  assert coreq==addq==0;assert abs(float(cf)-r.net_pnl)<1e-7;assert abs(float(cf/spent)-r.net_return_on_buy_cash)<1e-10
  if r.ranking_strategy!='ALL_FEASIBLE_DIAGNOSTIC':legs.append(dict(ranking_strategy=r.ranking_strategy,event_id=r.event_id,sid=r.sid,window=r.window,arm=r.arm,event_type=r.event_type,core_net_pnl=float(core),add_net_pnl=float(add),round_net_pnl=float(cf),did_add=int(r.adds),sale_fees_allocated_pro_rata=True))
 recon.append(dict(ranking_strategy=r.ranking_strategy,event_id=r.event_id,sid=r.sid,cashflow_error=float(cf)-r.cashflow_to_date,fee_error=float(fees)-r.fees_to_date,inventory_equal=True))
pd.DataFrame(recon).to_csv(O/'ALL_FEASIBLE_AND_SELECTED_CASHFLOW_QA.csv',index=False);legs=pd.DataFrame(legs);legs.to_csv(O/'CLOSED_INITIAL_ADD_ATTRIBUTION.csv',index=False)
# All selected identities must equal their independently evaluated feasible shadow economics.
economic=['status','entry_status','entry_q','entry_price','entry_fee','entry_risk','exit_day','exit_price','net_pnl','net_return_on_buy_cash','all_fees','adds','actions','cashflow_to_date','fees_to_date']
j=selected.merge(diag,on=['event_id','sid'],suffixes=('_selected','_all'),validate='many_to_one');assert len(j)==len(selected)
for col in economic:
 a=j[col+'_selected'];b=j[col+'_all']
 if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-8,equal_nan=True)
 else:assert a.fillna('NA').equals(b.fillna('NA')),col
all_summary=[];capture=[];changes=[];tail_changes=[];marginal=[]
for key,g in diag.groupby(keys):
 k=dict(zip(keys,key));done=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];tail=done[done.net_return_on_buy_cash.ge(.3)];entry=g[g.entry_status.eq('CONDITIONAL_OPEN_PROXY')];tailids=set(map(tuple,tail[['event_id','sid']].to_numpy()))
 all_summary.append(k|dict(all_feasible=len(g),conditional_entries=len(entry),closed=len(done),open=int(g.status.eq('OPEN_CENSORED_AT_2026_06_30').sum()),unknown_after_entry=int((g.entry_status.eq('CONDITIONAL_OPEN_PROXY')&~g.status.isin(['COMPLETE_CONDITIONAL_STOCK_ROUND','OPEN_CENSORED_AT_2026_06_30'])).sum()),unknown_before_entry=int((~g.entry_status.eq('CONDITIONAL_OPEN_PROXY')&~g.status.isin(['NEXT_OPEN_BELOW_PROTECTION','MINIMUM_LOT_NOT_FUNDED'])).sum()),known_reject=int(g.status.isin(['NEXT_OPEN_BELOW_PROTECTION','MINIMUM_LOT_NOT_FUNDED']).sum()),closed_positive=int(done.net_pnl.gt(0).sum()),closed_tail_ge30pct=len(tail),not_all_market=True))
 st=selected[(selected.window==key[0])&(selected.arm==key[1])&(selected.event_type==key[2])];sets={a:set(map(tuple,v[['event_id','sid']].to_numpy())) for a,v in st.groupby('ranking_strategy')}
 for strategy,ids in sets.items():
  captured=tailids&ids;capture.append(k|dict(ranking_strategy=strategy,selected=len(ids),all_feasible_closed_tails=len(tailids),captured_closed_tails=len(captured),capture_fraction=len(captured)/len(tailids) if tailids else np.nan,missed_closed_tails=len(tailids-ids),selected_complete=int(st[st.ranking_strategy.eq(strategy)].status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND').sum()),unknown_open_not_classified=True))
 base=sets['PVR_DESC'];new=sets['PVR3_PRIORITY']
 for kind,ids in [('REMOVED',base-new),('ADDED',new-base)]:
  x=g[g.apply(lambda r:(r.event_id,r.sid) in ids,axis=1)].copy();x['change']=kind;changes.append(x)
  closed=x[x.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];won=closed[closed.net_pnl.gt(0)];lost=closed[closed.net_pnl.lt(0)]
  marginal.append(k|dict(change=kind,total=len(x),closed=len(closed),not_complete=len(x)-len(closed),known_reject=int(x.status.isin(['NEXT_OPEN_BELOW_PROTECTION','MINIMUM_LOT_NOT_FUNDED']).sum()),unknown_or_open=int((~x.status.isin(['COMPLETE_CONDITIONAL_STOCK_ROUND','NEXT_OPEN_BELOW_PROTECTION','MINIMUM_LOT_NOT_FUNDED'])).sum()),wins=len(won),net_winrate=len(won)/len(closed) if len(closed) else np.nan,mean_net_cny=closed.net_pnl.mean(),mean_win_cny=won.net_pnl.mean(),mean_loss_cny=-lost.net_pnl.mean(),closed_tail_ge30pct=int(closed.net_return_on_buy_cash.ge(.3).sum()),mean_closed_return=closed.net_return_on_buy_cash.mean()))
  tail_changes.append(k|dict(change=kind,closed_tail_change=len(ids&tailids)))
pd.DataFrame(all_summary).to_csv(O/'ALL_FEASIBLE_OUTCOME_COUNTS.csv',index=False);pd.DataFrame(capture).to_csv(O/'STRONG_CAPTURE_COMPLETE_CANDIDATE_DOMAIN.csv',index=False);pd.concat(changes,ignore_index=True).to_csv(O/'ALL_SWAPPED_ROUNDS.csv',index=False);pd.DataFrame(marginal).to_csv(O/'SWAP_OUTCOME_SUMMARY.csv',index=False)
summary=pd.read_csv(O/'FULL_COMPARISON.csv');extra=[]
for key,g in selected.groupby(keys+['ranking_strategy']):
 k=dict(zip(keys+['ranking_strategy'],key));closed=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];tail=closed[closed.net_return_on_buy_cash.ge(.3)];ordinary=closed[closed.net_return_on_buy_cash.lt(.3)];e=g[g.entry_status.eq('CONDITIONAL_OPEN_PROXY')];f=e.original_resource_screen.fillna('');leg=legs[(legs.window==key[0])&(legs.arm==key[1])&(legs.event_type==key[2])&(legs.ranking_strategy==key[3])];add=leg[leg.did_add.eq(1)]
 extra.append(k|dict(mean_closed_net_cny=closed.net_pnl.mean(),mean_closed_tail_net_cny=tail.net_pnl.mean(),mean_closed_ordinary_net_cny=ordinary.net_pnl.mean(),cash_or_reserve_rejected=int(f.str.contains('cash_or_original_10pct_reserve',regex=False).sum()),all_old_resource_necessary_screen_pass=int(f.eq('NECESSARY_SCREEN_ONLY_NOT_FULL_ADMISSION').sum()),old_resources_unknown=int(f.eq('UNKNOWN_AFTER_ACCOUNT_END').sum()),closed_rounds_with_add=len(add),mean_core_net_cny=leg.core_net_pnl.mean(),mean_add_net_among_closed_added=add.add_net_pnl.mean(),add_leg_net_wins=int(add.add_net_pnl.gt(0).sum()),add_leg_net_losses=int(add.add_net_pnl.lt(0).sum()),same_round_add_fee_attribution_pro_rata=True,no_account=True))
fin=summary.merge(pd.DataFrame(extra),on=keys+['ranking_strategy'],validate='one_to_one');fin.to_csv(O/'FINANCIAL_DETAIL.csv',index=False)
# Per-event selection and eligibility, old baseline and PVR3-invariance were already checked at sealing.
seal=json.load(open(O/'SELECTION_SEAL.json'));assert all(sha(p)==h for p,h in seal['hashes'].items());assert all(sha(p)==h for p,h in seal['source_hashes'].items())
save('SUPPLEMENT_QA.json',dict(all_evaluation_rows=len(z),all_feasible_candidates=len(diag),selected_rounds=len(selected),reconciled_conditional_entries=len(recon),all_selected_economics_equal_all_feasible=True,closed_core_add_total_equals_round=True,all_source_and_selection_hashes_unchanged=True,script_hash=sha(Path(__file__)),no_new_economic_run=True,no_accounts=True))
save('FINAL_OUTPUT_HASHES.json',{str(p):sha(p) for p in O.rglob('*') if p.is_file() and p.name!='FINAL_OUTPUT_HASHES.json'})
cols=keys+['ranking_strategy','selected','conditional_entries','closed','unknown_path_after_entry','net_winrate','win_loss_cny_ratio','mean_closed_net_cny','closed_winners_ge30pct','added_all_entries','mean_initial_cash','mean_added_cash_among_added']
print(fin[fin.event_type.eq('FALSE_TO_TRUE')][cols].to_string(index=False));print('CAPTURE');print(pd.DataFrame(capture).query("event_type=='FALSE_TO_TRUE'").to_string(index=False));print('SWAPS');print(pd.DataFrame(marginal).query("event_type=='FALSE_TO_TRUE'").to_string(index=False));print('QA',json.dumps(json.load(open(O/'SUPPLEMENT_QA.json'))))
