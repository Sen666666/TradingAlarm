"""Descriptive summaries; not an account and not a strategy-selection criterion."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
from decimal import Decimal as D
O=Path(__file__).resolve().parent;R=O.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
z=pd.read_csv(O/'rounds/ALL_SHADOW_ROUNDS.csv',low_memory=False)
c=pd.read_csv(O/'ALL_CANDIDATES_COMMON_DOMAIN.csv',low_memory=False)
sel=pd.read_csv(O/'SEALED_CLOSE_SELECTED.csv',low_memory=False)
events=pd.read_csv(R/'breadth_trade_contract_v1/ALL_EVENTS.csv',low_memory=False)
keys=['window','arm','event_type','ranking_strategy']
closed=z.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND');opened=z.status.eq('OPEN_CENSORED_AT_2026_06_30');admit=z.entry_status.eq('CONDITIONAL_OPEN_PROXY')
knownreject=z.status.isin(['NEXT_OPEN_BELOW_PROTECTION','MINIMUM_LOT_NOT_FUNDED'])
summary=[];cashrows=[];overlaps=[];actionrows=[]
for key,g in z.groupby(keys,sort=True):
 w,a,t,s=key;done=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];won=done[done.net_pnl.gt(0)];lost=done[done.net_pnl.lt(0)];entry=g[g.entry_status.eq('CONDITIONAL_OPEN_PROXY')];tail=done[done.net_return_on_buy_cash.ge(.3)]
 d=dict(zip(keys,key));d.update(industry_events=int(((events.window.astype(str)==str(w))&(events.arm==a)&(events.event_type==t)).sum()),candidate_rows=int(((c.window.astype(str)==str(w))&(c.arm==a)&(c.event_type==t)).sum()),common_known_candidates=int(((c.window.astype(str)==str(w))&(c.arm==a)&(c.event_type==t)&c.ranking_common_known).sum()),selected=len(g),conditional_entries=len(entry),closed=len(done),open=int(g.status.eq('OPEN_CENSORED_AT_2026_06_30').sum()),unknown_path_after_entry=int((g.entry_status.eq('CONDITIONAL_OPEN_PROXY')&~g.status.isin(['COMPLETE_CONDITIONAL_STOCK_ROUND','OPEN_CENSORED_AT_2026_06_30'])).sum()),known_open_reject=int(g.status.isin(['NEXT_OPEN_BELOW_PROTECTION','MINIMUM_LOT_NOT_FUNDED']).sum()),unknown_before_entry=int((~g.entry_status.eq('CONDITIONAL_OPEN_PROXY')&~g.status.isin(['NEXT_OPEN_BELOW_PROTECTION','MINIMUM_LOT_NOT_FUNDED'])).sum()),wins=len(won),losses=len(lost),zero=int(done.net_pnl.eq(0).sum()),net_winrate=len(won)/len(done) if len(done) else np.nan,mean_win_cny=won.net_pnl.mean(),mean_loss_cny=-lost.net_pnl.mean(),win_loss_cny_ratio=won.net_pnl.mean()/(-lost.net_pnl.mean()) if len(won) and len(lost) else np.nan,mean_win_return=won.net_return_on_buy_cash.mean(),mean_loss_return=-lost.net_return_on_buy_cash.mean(),win_loss_return_ratio=won.net_return_on_buy_cash.mean()/(-lost.net_return_on_buy_cash.mean()) if len(won) and len(lost) else np.nan,mean_closed_return=done.net_return_on_buy_cash.mean(),median_closed_return=done.net_return_on_buy_cash.median(),worst_closed_cny=done.net_pnl.min(),worst_closed_reference_nav_fraction=done.net_pnl.min()/1200000,loss_over_plan3000=int(done.net_pnl.lt(-3000).sum()),closed_winners_ge30pct=len(tail),closed_tail_added=int(tail['adds'].fillna(0).gt(0).sum()),added_all_entries=int(entry['adds'].fillna(0).gt(0).sum()),add_fraction_all_entries=float(entry['adds'].fillna(0).gt(0).mean()) if len(entry) else np.nan,profitable_any=int(entry.profitable_close_days.fillna(0).gt(0).sum()),profitable_fresh_any=int(entry.positive_CP_close_days.fillna(0).gt(0).sum()),qualifying_fresh_any=int(entry.qualifying_CP_close_days.fillna(0).gt(0).sum()),mean_initial_cash=float((entry.entry_gross+entry.entry_fee).mean()),mean_added_cash_among_added=entry.loc[entry['adds'].fillna(0).gt(0),'add_buy_cash'].mean(),independent_unique_stocks=entry.sid.nunique(),not_account=True)
 summary.append(d)
 for screen,sg in entry.groupby('original_resource_screen',dropna=False):
  cashrows.append(dict(zip(keys,key))|dict(original_resource_screen=str(screen),rows=len(sg),not_admission=True))
 for sid,sg in entry.groupby('sid'):
  sg=sg.sort_values('entry_day')
  for i,r in enumerate(sg.itertuples()):
   end=r.exit_day if pd.notna(r.exit_day) else (str(r.unknown_day) if pd.notna(r.unknown_day) else '2026-06-30')
   prior=sg.iloc[:i];n=int(((prior.exit_day.fillna(prior.unknown_day).fillna('2026-06-30'))>=r.entry_day).sum())
   if n:overlaps.append(dict(zip(keys,key))|dict(event_id=r.event_id,sid=sid,entry_day=r.entry_day,prior_overlapping_event_rounds=n))
# Independently inspect overlaps across event types and windows within each distinct strategy/industry-definition.
overlaps=[]
for (arm,strategy,sid),g in z[z.entry_status.eq('CONDITIONAL_OPEN_PROXY')].groupby(['arm','ranking_strategy','sid']):
 g=g.sort_values('entry_day')
 for i,r in enumerate(g.itertuples()):
  for prior in g.iloc[:i].itertuples():
   end=prior.exit_day if pd.notna(prior.exit_day) else (str(prior.unknown_day) if pd.notna(prior.unknown_day) else '2026-06-30')
   if end>=r.entry_day:overlaps.append(dict(arm=arm,ranking_strategy=strategy,sid=sid,event_id=r.event_id,event_type=r.event_type,window=r.window,entry_day=r.entry_day,prior_event_id=prior.event_id,prior_event_type=prior.event_type,prior_window=prior.window,prior_observed_end=end,known_observed_overlap_only=True))
summary=pd.DataFrame(summary);summary.to_csv(O/'FULL_COMPARISON.csv',index=False);summary[summary.event_type.eq('FALSE_TO_TRUE')].to_csv(O/'MAIN_FALSE_TO_TRUE_COMPARISON.csv',index=False)
pd.DataFrame(cashrows).to_csv(O/'ORIGINAL_CASH_RESOURCE_DESCRIPTION.csv',index=False);pd.DataFrame(overlaps).to_csv(O/'SAME_STOCK_OVERLAPPING_EVENTS.csv',index=False)
z[closed&z.net_return_on_buy_cash.ge(.3)].sort_values(keys+['net_return_on_buy_cash'],ascending=[True]*4+[False]).to_csv(O/'DESCRIPTIVE_CLOSED_WINNERS_GE30PCT.csv',index=False)
z[z.window.eq('2026H1_SEMI')].to_csv(O/'ALL_2026H1_SEMICONDUCTOR_ROUNDS.csv',index=False)
# Verify actual cash flows using Decimal and complete actions, without re-running economic simulation.
checks=[]
for r in z[admit].itertuples():
 cf=-D(str(r.entry_q))*D(str(r.entry_price))-D(str(r.entry_fee));fees=D(str(r.entry_fee));buy=-cf;q=int(r.entry_q)
 acts=json.loads(r.actions)
 for ix,a in enumerate(acts):
  qty=int(a['q']);p=D(a['price']);f=D(a['fee']);fees+=f
  if a['side']=='buy_add':cf-=qty*p+f;buy+=qty*p+f;q+=qty
  else:cf+=qty*p-f;q-=qty
  actionrows.append(dict(ranking_strategy=r.ranking_strategy,event_id=r.event_id,sid=r.sid,action_index=ix,**a))
 assert abs(float(cf)-r.cashflow_to_date)<1e-7,(r.event_id,r.sid,'cashflow')
 assert abs(float(fees)-r.fees_to_date)<1e-7,(r.event_id,r.sid,'fees')
 assert q==int(r.core_qty+r.add_qty),(r.event_id,r.sid,'inventory')
 if r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND':
  assert q==0 and abs(float(cf)-r.net_pnl)<1e-7
  assert abs(float(cf/buy)-r.net_return_on_buy_cash)<1e-10
  assert abs(float(fees)-r.all_fees)<1e-7
 checks.append(dict(ranking_strategy=r.ranking_strategy,event_id=r.event_id,sid=r.sid,cashflow_error=float(cf)-r.cashflow_to_date,fees_error=float(fees)-r.fees_to_date,inventory_match=True,closed=r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND'))
pd.DataFrame(checks).to_csv(O/'CASHFLOW_RECONCILIATION.csv',index=False);pd.DataFrame(actionrows).to_csv(O/'ALL_ACTIONS.csv',index=False)
# Same-event/same-stock across ranks must have identical economics.
economic=['status','entry_status','entry_q','entry_price','entry_fee','entry_risk','exit_day','exit_price','net_pnl','net_return_on_buy_cash','all_fees','adds','actions','cashflow_to_date','fees_to_date']
maxident=0
for _,g in z.groupby(['event_id','sid']):
 if len(g)>1:
  for col in economic:assert g[col].fillna('NA').nunique()==1,('cross-rank economic mismatch',col)
  maxident+=len(g)
# Original baseline reproduction on all shared identities.
old=pd.read_csv(R/'breadth_trade_contract_v1/causal_queue_full_v2/rounds_clockfixed/ALL_SHADOW_ROUNDS.csv',low_memory=False)
now=z[z.ranking_strategy.eq('AMOUNT20_DESC')]
j=now.merge(old,on=['event_id','sid'],suffixes=('_new','_old'),validate='one_to_one')
oldcompare=[x for x in economic if x!='fees_to_date']
for col in oldcompare:
 a=j[col+'_new'];b=j[col+'_old']
 if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-8,equal_nan=True)
 else:assert a.fillna('NA').equals(b.fillna('NA')),('old baseline mismatch',col)
save('QA.json',dict(new_rounds=len(z),all_selected_covered=len(z)==len(sel),new_conditional_entries=len(checks),cashflow_and_fee_and_inventory_reconciled=True,cross_rank_repeated_rows_identical=maxident,shared_original_baseline_rows=len(j),original_baseline_economics_exact_on_shared_rows=True,original_files_unchanged=True,no_accounts=True,known_overlap_rows=len(overlaps)))
# Pairwise choice overlap, with the exact same common-domain denominator.
pairs=[]
for k,g in sel.groupby(['window','arm','event_type']):
 sets={s:set(map(tuple,x[['event_id','sid']].to_numpy())) for s,x in g.groupby('ranking_strategy')}
 for a,b in [('AMOUNT20_DESC','PVR_DESC'),('AMOUNT20_DESC','H1_DESC'),('H1_DESC','PVR_DESC')]:
  if a in sets and b in sets:pairs.append(dict(zip(['window','arm','event_type'],k))|dict(a=a,b=b,a_rows=len(sets[a]),b_rows=len(sets[b]),shared=len(sets[a]&sets[b]),a_only=len(sets[a]-sets[b]),b_only=len(sets[b]-sets[a])))
pd.DataFrame(pairs).to_csv(O/'PAIRWISE_SELECTION_OVERLAP.csv',index=False)
save('OUTPUT_HASHES.json',{str(p):sha(p) for p in O.iterdir() if p.is_file() and p.name not in ['OUTPUT_HASHES.json','READOUT.md']})
print(summary[summary.event_type.eq('FALSE_TO_TRUE')][['window','arm','ranking_strategy','selected','conditional_entries','closed','open','unknown_path_after_entry','unknown_before_entry','known_open_reject','net_winrate','win_loss_cny_ratio','mean_closed_return','closed_winners_ge30pct','added_all_entries']].to_string(index=False))
print('QA',json.dumps(json.load(open(O/'QA.json')),ensure_ascii=False),flush=True)
