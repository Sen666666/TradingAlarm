from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
CL=['W','U','L']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.item() if isinstance(a,np.generic)else str(a))+'\n')
seal=json.load(open(O/'RANK_SEAL.json'));assert all(sha(p)==h for p,h in seal['hashes'].items());s=pd.read_parquet(O/'SEALED_SELECTIONS.parquet');z=pd.read_parquet(O/'LABELS_120.parquet');c=pd.read_parquet(O/'SCORED_CANDIDATES.parquet');cols=['event_id','sid','label','entry_status','status','net_pnl','net_return_on_buy_cash','adds','horizon_day','exit_day','unknown_day']
a=s.merge(z[cols],on=['event_id','sid'],validate='many_to_one');a.to_parquet(O/'SELECTED_WITH_LABELS.parquet',index=False)
rows=[]
for key,g in a.groupby(['window','arm','event_type','method']):
 done=g[g.label.isin(['W','L'])];wins=done[done.label.eq('W')];loss=done[done.label.eq('L')];ultimate=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];tail=done.net_return_on_buy_cash.ge(.3);urt=ultimate.net_return_on_buy_cash.ge(.3)
 row=dict(zip(['window','arm','event_type','method'],key));row.update(selected=len(g),events=g.event_id.nunique(),stocks=g.sid.nunique(),dates=g.day.nunique(),score_known=int(g.score_known.sum()),entered=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),W=int(g.label.eq('W').sum()),L=int(g.label.eq('L').sum()),U=int(g.label.eq('U').sum()),UNKNOWN=int(g.label.eq('UNKNOWN').sum()),IMMATURE=int(g.label.eq('IMMATURE').sum()),NO_ENTRY=int(g.label.eq('NO_ENTRY').sum()),closedH=len(done),win_rate_H=len(wins)/len(done)if len(done)else None,mean_win_cny=wins.net_pnl.mean(),mean_loss_cny=-loss.net_pnl.mean(),payoff_ratio_H=wins.net_pnl.mean()/(-loss.net_pnl.mean())if len(wins)and len(loss)else None,mean_closedH_net_cny=done.net_pnl.mean(),mean_closedH_return=done.net_return_on_buy_cash.mean(),median_closedH_return=done.net_return_on_buy_cash.median(),return_q95=done.net_return_on_buy_cash.quantile(.95),return_q99=done.net_return_on_buy_cash.quantile(.99),tailH=int(tail.sum()),tailH_cny=float(done.loc[tail,'net_pnl'].sum()),ordinaryH_mean_cny=done.loc[~tail,'net_pnl'].mean(),mean_pW=g.pW.mean(),mean_pL=g.pL.mean(),mean_pU=g.pU.mean(),min_pClosure=g.pClosure.min(),median_pClosure=g.pClosure.median(),mean_win_component=g.win_component.mean(),mean_loss_component=g.loss_component.mean(),mean_predicted_conditional_net=g.conditional_net.mean(),ultimate_closed=len(ultimate),ultimate_win_rate=ultimate.net_pnl.gt(0).mean(),ultimate_payoff=ultimate.loc[ultimate.net_pnl.gt(0),'net_pnl'].mean()/(-ultimate.loc[ultimate.net_pnl.le(0),'net_pnl'].mean()),ultimate_tail=int(urt.sum()),U_eventually_closed_tail=int((g.label.eq('U')&g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')&g.net_return_on_buy_cash.ge(.3)).sum()))
 rows.append(row)
results=pd.DataFrame(rows);results.to_csv(O/'COMPARISON.csv',index=False)
# Full eligible tail opportunity denominators, keep both H and eventual labels separate.
tails=[]
for key,g in z.groupby(['window','arm','event_type']):
 for basis,mask in [('H120',g.label.isin(['W','L'])),('ULTIMATE_DESCRIPTIVE',g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND'))]:
  tg=g[mask&g.net_return_on_buy_cash.ge(.3)];available=set(zip(tg.event_id,tg.sid))
  for method,ss in s[(s.window==key[0])&(s.arm==key[1])&(s.event_type==key[2])].groupby('method'):
   selected=set(zip(ss.event_id,ss.sid));tails.append(dict(window=key[0],arm=key[1],event_type=key[2],basis=basis,method=method,known_tail_opportunities=len(available),captured=len(selected&available),capture=len(selected&available)/len(available)if available else None))
pd.DataFrame(tails).to_csv(O/'TAIL_CAPTURE.csv',index=False)
# Probabilistic calibration on all known-feature W/L/U eligible candidates, not merely selected.
p=c.merge(z[['event_id','sid','label']],on=['event_id','sid'],validate='one_to_one');mass=json.load(open(O/'FIT_SEAL.json'))['weighted_class_mass'];base=np.array([mass[k]for k in CL]);base/=base.sum();proper=[];calib=[]
for win,g in p.groupby('window'):
 t=g[g.score_known&g.label.isin(CL)];pred=t[['p'+k for k in CL]].to_numpy();y=np.array([CL.index(v)for v in t.label],dtype=int);Y=np.eye(3)[y];hist=np.repeat(base[None,:],len(t),axis=0)
 if len(t):proper.append(dict(window=win,known=len(t),all_candidates=len(g),known_dates=t.day.nunique(),Brier=float(np.mean(np.sum((pred-Y)**2,axis=1))),Brier_historical=float(np.mean(np.sum((hist-Y)**2,axis=1))),logloss=float(-np.mean(np.log(pred[np.arange(len(t)),y]))),logloss_historical=float(-np.mean(np.log(hist[np.arange(len(t)),y]))),predW=float(pred[:,0].mean()),actualW=float(Y[:,0].mean()),predL=float(pred[:,2].mean()),actualL=float(Y[:,2].mean()),predU=float(pred[:,1].mean()),actualU=float(Y[:,1].mean())))
 for cl in CL:
  if not len(t):continue
  bins=pd.cut(t['p'+cl],[0,.02,.05,.1,.2,.3,.4,.5,1],include_lowest=True)
  for b,gg in t.groupby(bins,observed=True):calib.append(dict(window=win,endpoint=cl,bin=str(b),n=len(gg),mean_prediction=gg['p'+cl].mean(),observed_fraction=gg.label.eq(cl).mean()))
pd.DataFrame(proper).to_csv(O/'PROPER_SCORES.csv',index=False);pd.DataFrame(calib).to_csv(O/'CALIBRATION.csv',index=False)
changes=[]
for key,g in s.groupby(['window','arm','event_type']):
 baseg=g[g.method.eq('PVR_DESC')];basekeys=set(zip(baseg.event_id,baseg.sid))
 for method,gg in g.groupby('method'):
  keys=set(zip(gg.event_id,gg.sid));changes.append(dict(window=key[0],arm=key[1],event_type=key[2],method=method,selected=len(keys),kept=len(keys&basekeys),added=len(keys-basekeys),removed=len(basekeys-keys)))
pd.DataFrame(changes).to_csv(O/'SELECTION_CHANGES.csv',index=False)
# Delete-cluster approximate uncertainty on conditional completed metrics. No complete-date conditioning.
unc=[]
cal=pd.DatetimeIndex(sorted(pd.read_parquet(O.parent/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet').day.unique()));idx={v:i for i,v in enumerate(cal)}
def metrics(g):
 d=g[g.label.isin(['W','L'])];return np.array([d.label.eq('W').mean(),d.net_pnl.mean()])
for window in ['2022','2024_924']:
 v=a[(a.window==window)&a.arm.eq('M3')&a.event_type.eq('FALSE_TO_TRUE')].copy();v['date_block']=v.day.map(idx)//20
 for met in ['PWIN','CONDITIONAL_NET']:
  pair=v[v.method.isin(['PVR_DESC',met])];point=metrics(pair[pair.method.eq(met)])-metrics(pair[pair.method.eq('PVR_DESC')])
  for clust in ['date_block','sid']:
   vals=[];groups=pair[clust].unique()
   for group in groups:
    cut=pair[pair[clust]!=group];vals.append(metrics(cut[cut.method.eq(met)])-metrics(cut[cut.method.eq('PVR_DESC')]))
   vv=np.array(vals);se=np.sqrt((len(vv)-1)/len(vv)*np.sum((vv-vv.mean(0))**2,axis=0))
   unc.append(dict(window=window,method=met,cluster=clust,nclusters=len(groups),winrate_difference=point[0],winrate_SE=se[0],mean_net_difference_cny=point[1],mean_net_SE_cny=se[1],conditional_known_closed_estimand=True,no_refit_uncertainty=True,not_independent_shadows=True))
pd.DataFrame(unc).to_csv(O/'CLUSTER_DIAGNOSTIC.csv',index=False)
# Feature/source provenance current hashes must match both prior manifest and pre-computation hash.
manifest=json.load(open('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'));old={k:v for rec in manifest for k,v in rec['source_sha256'].items()};source=json.load(open(O/'SOURCE_HASHES.json'));mismatch=[pp for pp,h in source.items()if pp in old and old[pp]!=h];assert not mismatch
assert all(sha(pp)==h for pp,h in source.items());assert all(sha(pp)==h for pp,h in seal['hashes'].items())
dump('QA.json',dict(all_candidate_rows=len(c),all_shadow_rows=len(z),selected_rows=len(s),models=1,ranking_comparators=3,accounts=0,parameter_searches=0,source_unchanged=True,original_manifest_source_hashes_match=True,counts_reconcile=bool((results[['W','L','U','UNKNOWN','IMMATURE','NO_ENTRY']].sum(axis=1)==results.selected).all()),training_only2022=True,latest_training_horizon='2023-07-04',future_labels_loaded_but_not_used_in_fit_scaling_or_ranking=True,dividend_or_factor_unknown_not_imputed=True,net_cashflow_contract_not_verified_total_return=True))
print(results[results.arm.eq('M3')&results.event_type.eq('FALSE_TO_TRUE')][['window','method','selected','W','L','U','UNKNOWN','IMMATURE','NO_ENTRY','win_rate_H','payoff_ratio_H','mean_closedH_net_cny','mean_closedH_return','tailH','mean_pU','min_pClosure','U_eventually_closed_tail']].to_string(index=False));print(pd.DataFrame(proper).to_string(index=False));print(pd.DataFrame(unc).to_string(index=False))
