from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
from decimal import Decimal as D
O=Path(__file__).resolve().parent;R=O.parent;B=R/'breadth_pvr3_priority_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
seal=json.load(open(O/'PAIR_SEAL.json'));assert all(sha(p)==h for p,h in seal['source_hashes'].items());assert all(sha(p)==h for p,h in seal['output_hashes'].items())
c=pd.read_csv(O/'FEATURES_AND_COVERAGE.csv',parse_dates=['day']);p=pd.read_csv(O/'SEALED_PAIRS.csv',parse_dates=['day'])
# Optional slot-level opportunity cost, fully pre-outcome deterministic: only paired slots with exactly one original selected.
c['MATCH_FRESH']=c.baseline_selected;c['MATCH_CONTINUING']=c.baseline_selected
for x in p.itertuples():
 f,s=x.fresh_index,x.continuing_index
 if c.at[f,'baseline_selected']!=c.at[s,'baseline_selected']:
  c.loc[[f,s],'MATCH_FRESH']=[True,False];c.loc[[f,s],'MATCH_CONTINUING']=[False,True]
for strategy in ['MATCH_FRESH','MATCH_CONTINUING']:
 assert c.groupby('event_id')[strategy].sum().equals(c.groupby('event_id').baseline_selected.sum())
c[['event_id','sid','baseline_selected','MATCH_FRESH','MATCH_CONTINUING']].to_csv(O/'SEALED_SLOT_DIAGNOSTIC.csv',index=False)
dump('SLOT_SEAL.json',dict(time=str(pd.Timestamp.now(tz='UTC')),no_future_labels_read_yet=True,rule='Only exactly-one-selected matched pairs choose fresh or continuing; all other baseline slots retained. Diagnostic opportunity cost, not a promoted ranker.',hash=sha(O/'SEALED_SLOT_DIAGNOSTIC.csv')))
# First forward-outcome load for this feature comparison.
z=pd.read_csv(B/'rounds/ALL_SHADOW_ROUNDS.csv',low_memory=False);z=z[z.ranking_strategy.eq('ALL_FEASIBLE_DIAGNOSTIC')];assert len(z)==22196
assert not z.duplicated(['event_id','sid']).any()
cols=['event_id','sid','status','entry_status','entry_day','exit_day','unknown_day','net_pnl','net_return_on_buy_cash','adds','added_quantity','entry_q','entry_price','entry_fee','add_buy_cash','total_buy_cash','buy_cash_to_date','actions','core_qty','add_qty','fees_to_date','cashflow_to_date']
c=c.merge(z[cols],on=['event_id','sid'],validate='one_to_one',suffixes=('_close',''));assert len(c)==14880
c['label']='UNKNOWN';closed=c.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND');c.loc[closed,'label']=np.where(c.loc[closed,'net_pnl'].gt(0),'W','L')
c.loc[c.status.str.startswith('OPEN_CENSORED'),'label']='U';c.loc[c.status.isin(['NEXT_OPEN_BELOW_PROTECTION','MINIMUM_LOT_NOT_FUNDED']),'label']='NO_ENTRY'
c['tail30']=closed&c.net_return_on_buy_cash.ge(.3);c['core_net']=np.nan;c['add_net']=np.nan
for i,x in c[closed].iterrows():
 cq=int(x.entry_q);aq=0;core=-D(str(x.entry_q))*D(str(x.entry_price))-D(str(x.entry_fee));add=D(0)
 for a in json.loads(x.actions):
  q=int(a['q']);pr=D(a['price']);fee=D(a['fee'])
  if a['side']=='buy_add':add-=q*pr+fee;aq+=q
  elif a['side']=='sell_add':assert q==aq;add+=q*pr-fee;aq=0
  else:
   assert a['side']=='sell_all' and q==cq+aq
   fc=fee*D(cq)/D(q);core+=cq*pr-fc;add+=aq*pr-(fee-fc);cq=aq=0
 assert cq==aq==0 and abs(float(core+add)-x.net_pnl)<1e-7
 c.loc[i,['core_net','add_net']]=[float(core),float(add)]
c.to_csv(O/'ALL_M3_RESULTS.csv',index=False)
keys=['window','event_type']
def stats(g):
 d=g[g.label.isin(['W','L'])];w=d[d.label.eq('W')];l=d[d.label.eq('L')];added=d[d.adds.gt(0)]
 out=dict(n=len(g),stocks=g.sid.nunique(),dates=g.day.nunique(),W=len(w),L=len(l),U=int(g.label.eq('U').sum()),UNKNOWN=int(g.label.eq('UNKNOWN').sum()),NO_ENTRY=int(g.label.eq('NO_ENTRY').sum()),winrate=len(w)/len(d) if len(d) else np.nan,mean_win=w.net_pnl.mean(),mean_loss=-l.net_pnl.mean(),payoff=w.net_pnl.mean()/(-l.net_pnl.mean()),mean_net=d.net_pnl.mean(),mean_return=d.net_return_on_buy_cash.mean(),tail30=int(d.tail30.sum()),added_closed=len(added),add_leg_wins=int(added.add_net.gt(0).sum()),add_leg_losses=int(added.add_net.lt(0).sum()),mean_add_net=added.add_net.mean(),mean_core_net=d.core_net.mean(),net5=d.net_pnl.quantile(.05),net95=d.net_pnl.quantile(.95),mean_PVR=g.PVR_score.mean(),mean_close_risk_fraction=(1-g.close_floor_raw/g.known_close_raw).mean(),mean_initial_cash=(g.entry_q*g.entry_price+g.entry_fee).mean())
 return out
summ=[]
for scope,h in [('ALL_M3',c),('MATCHED',c[c.match_reason.eq('MATCHED')]),('BASELINE',c[c.baseline_selected]),('MATCH_FRESH',c[c.MATCH_FRESH]),('MATCH_CONTINUING',c[c.MATCH_CONTINUING])]:
 for key,g in h.groupby(keys+(['member_state'] if scope in ['ALL_M3','MATCHED'] else [])):
  if not isinstance(key,tuple):key=(key,)
  summ.append(dict(scope=scope,**dict(zip(keys+(['member_state'] if scope in ['ALL_M3','MATCHED'] else []),key)),**stats(g)))
s=pd.DataFrame(summ);s.to_csv(O/'SUMMARY.csv',index=False)
# Side-by-side pairs; no filtering until labels already assigned.
pc=p.copy()
for name,col in [('fresh','fresh_index'),('continuing','continuing_index')]:
 v=c.loc[p[col]].reset_index(drop=True)
 for cc in ['label','net_pnl','net_return_on_buy_cash','tail30','adds','core_net','add_net','baseline_selected','name','known_close_raw','close_floor_raw','entry_q','entry_price','entry_fee','I_age_common']:
  pc[name+'_'+cc]=v[cc].to_numpy()
pc['both_closed']=pc.fresh_label.isin(['W','L'])&pc.continuing_label.isin(['W','L'])
pc['one_baseline_slot']=pc.fresh_baseline_selected.ne(pc.continuing_baseline_selected)
pc.to_csv(O/'PAIRED_RESULTS.csv',index=False)
pair_s=[];clusters=[];tails=[]
cal=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet').index
for key,g in pc.groupby(keys):
 base=dict(zip(keys,key));q=g[g.both_closed].copy();n=len(q)
 dd=q.fresh_net_pnl-q.continuing_net_pnl;dw=q.fresh_label.eq('W').astype(float)-q.continuing_label.eq('W').astype(float);dr=q.fresh_net_return_on_buy_cash-q.continuing_net_return_on_buy_cash
 pair_s.append(base|dict(pairs=len(g),both_closed=n,fresh_only_closed=int((g.fresh_label.isin(['W','L'])&~g.continuing_label.isin(['W','L'])).sum()),continuing_only_closed=int((~g.fresh_label.isin(['W','L'])&g.continuing_label.isin(['W','L'])).sum()),fresh_winrate=q.fresh_label.eq('W').mean(),continuing_winrate=q.continuing_label.eq('W').mean(),delta_winrate=dw.mean(),fresh_mean_net=q.fresh_net_pnl.mean(),continuing_mean_net=q.continuing_net_pnl.mean(),delta_mean_net=dd.mean(),delta_mean_return=dr.mean(),fresh_tails=int(q.fresh_tail30.sum()),continuing_tails=int(q.continuing_tail30.sum()),fresh_win_cont_loss=int((q.fresh_label.eq('W')&q.continuing_label.eq('L')).sum()),fresh_loss_cont_win=int((q.fresh_label.eq('L')&q.continuing_label.eq('W')).sum()),exactly_one_original_slot=int(g.one_baseline_slot.sum()),mean_PVR_gap=g.PVR_gap.mean(),max_PVR_gap=g.PVR_gap.max()))
 if n>=2:
  block=cal.get_indexer(q.day)//20
  for label,values in [('winrate',dw),('net_cny',dd),('return',dr)]:
   vals=values.to_numpy();est=vals.mean()
   for unit,ids in [('date',q.day.to_numpy()),('20_common_day_block',block)]:
    unique=pd.unique(ids);leave=[vals[ids!=u].mean() for u in unique if (ids!=u).any()];se=np.sqrt((len(leave)-1)/len(leave)*np.sum((np.array(leave)-np.mean(leave))**2)) if len(leave)>1 else np.nan
    clusters.append(base|dict(metric=label,cluster=unit,clusters=len(unique),estimate=est,delete_cluster_SE=se,leave_min=min(leave) if leave else np.nan,leave_max=max(leave) if leave else np.nan,interpretation='Descriptive conditional complete-pair jackknife; not independent trials or OOS CI'))
   stocks=sorted(set(q.fresh_sid)|set(q.continuing_sid));leave=[vals[(q.fresh_sid.ne(u)&q.continuing_sid.ne(u)).to_numpy()].mean() for u in stocks];leave=np.array(leave);se=np.sqrt((len(leave)-1)/len(leave)*np.sum((leave-leave.mean())**2))
   clusters.append(base|dict(metric=label,cluster='delete_either_stock_endpoint',clusters=len(stocks),estimate=est,delete_cluster_SE=se,leave_min=leave.min(),leave_max=leave.max(),interpretation='Endpoint deletion sensitivity; overlapping two-stock clusters, SE not certified confidence interval'))
 # Pair outcome cross table and all tails preserved separately.
 tails.append(g[g.fresh_tail30|g.continuing_tail30])
pd.DataFrame(pair_s).to_csv(O/'PAIRED_SUMMARY.csv',index=False);pd.DataFrame(clusters).to_csv(O/'CLUSTER_DIAGNOSTIC.csv',index=False);pd.concat(tails).to_csv(O/'PAIRED_TAILS.csv',index=False)
pc.groupby(keys+['fresh_label','continuing_label']).size().rename('pairs').reset_index().to_csv(O/'PAIR_LABEL_COUNTS.csv',index=False)
c[c.window.eq('2026H1_SEMI')].to_csv(O/'ALL_2026H1_M3.csv',index=False)
c[c.tail30].to_csv(O/'ALL_M3_TAILS.csv',index=False)
# Exact slot opportunity costs.
cost=[]
for key,g in c.groupby(keys):
 for strategy in ['MATCH_FRESH','MATCH_CONTINUING']:
  removed=g[g.baseline_selected&~g[strategy]];added=g[~g.baseline_selected&g[strategy]]
  cost.append(dict(zip(keys,key))|dict(strategy=strategy,removed=len(removed),added=len(added),removed_tail30=int(removed.tail30.sum()),added_tail30=int(added.tail30.sum()),removed_W=int(removed.label.eq('W').sum()),added_W=int(added.label.eq('W').sum()),removed_L=int(removed.label.eq('L').sum()),added_L=int(added.label.eq('L').sum()),removed_UNKNOWN=int(removed.label.eq('UNKNOWN').sum()),added_UNKNOWN=int(added.label.eq('UNKNOWN').sum())))
pd.DataFrame(cost).to_csv(O/'SLOT_OPPORTUNITY_COST.csv',index=False)
assert all(sha(p)==h for p,h in seal['source_hashes'].items());assert all(sha(p)==h for p,h in seal['output_hashes'].items())
dump('QA.json',dict(rows=len(c),pairs=len(p),unique_matched_endpoints=2*len(p),both_closed_pairs=int(pc.both_closed.sum()),prior_sources_and_seals_unchanged=True,complete_round_cashflow_reconciled=int(closed.sum()),all_original_baseline_counts_reproduced=True,no_simulation_rerun=True,no_parameter_search=True,no_accounts=True,outcome_source_sha256=sha(B/'rounds/ALL_SHADOW_ROUNDS.csv')))
print('MATCHED MAIN\n',s[(s.scope.eq('MATCHED'))&s.event_type.eq('FALSE_TO_TRUE')].to_string(index=False))
print('PAIRED MAIN\n',pd.DataFrame(pair_s).query("event_type=='FALSE_TO_TRUE'").to_string(index=False))
print('SLOT MAIN\n',s[s.scope.isin(['BASELINE','MATCH_FRESH','MATCH_CONTINUING'])&s.event_type.eq('FALSE_TO_TRUE')][['window','scope','n','W','L','UNKNOWN','winrate','payoff','mean_net','tail30']].to_string(index=False))
print('COST\n',pd.DataFrame(cost).query("event_type=='FALSE_TO_TRUE'").to_string(index=False))
print('CLUSTER MAIN\n',pd.DataFrame(clusters).query("event_type=='FALSE_TO_TRUE' and metric!='return'").to_string(index=False))
