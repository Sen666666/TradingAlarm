from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;P=O.parent;t0=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n')
with (O/'RUN_ONCE.lock').open('x') as h:h.write(pd.Timestamp.now(tz='UTC').isoformat())
src=[Path(__file__),O/'PROTOCOL.json',P/'AXES_FROZEN.json',P/'ENTRY_FEATURES_WITH_OLD_LABELS.csv',P/'ALL_PREDEFINED_STRATA.csv']
hashes={str(p):sha(p) for p in src}
axes=json.loads(src[2].read_text())
dtype={a:str for a in axes['axes']};dtype['window']=str
z=pd.read_csv(src[3],dtype=dtype,parse_dates=['signal_day'])
s=pd.read_csv(src[4])
def period(p):
 if p=='2024_924':return z[z.window.eq(p)]
 g=z[z.window.eq('2022')]
 if p=='2022_ALL':return g
 if p=='2022_REST':return g[g.signal_day.dt.quarter.ge(2)]
 return g[g.signal_day.dt.quarter.eq(int(p[-1]))]
def subset(g,axis,val):
 if axis=='ALL':return g
 fields=axis.split('__X__');vals=val.split('|');assert len(fields)==len(vals)
 mask=pd.Series(True,index=g.index)
 for f,v in zip(fields,vals):mask&=g[f].eq(v)
 return g[mask]
def metric(a,keys,pnl,ret):
 n=len(a)
 if not n:return dict(clusters=0,max_trade_share=None,weight_equivalent_clusters=None,winning_clusters=0,positive_net_clusters=0,tail_clusters=0,loo_winrate_min=None,loo_winrate_max=None,loo_mean_net_min=None,loo_mean_net_max=None,loo_tail_count_min=None,loo_tail_count_max=None,loo_defined=False)
 q=a.assign(_w=a[pnl].gt(0).astype(int),_tail=a[ret].ge(.3).astype(int)).groupby(keys,dropna=False).agg(n=(pnl,'size'),wins=('_w','sum'),net=(pnl,'sum'),tails=('_tail','sum'))
 weights=q.n/n;den=n-q.n;ok=den>0
 looW=(a[pnl].gt(0).sum()-q.loc[ok,'wins'])/den[ok]
 looN=(a[pnl].sum()-q.loc[ok,'net'])/den[ok]
 looT=a[ret].ge(.3).sum()-q.loc[ok,'tails']
 return dict(clusters=len(q),max_trade_share=float(weights.max()),weight_equivalent_clusters=float(1/(weights**2).sum()),winning_clusters=int(q.wins.gt(0).sum()),positive_net_clusters=int(q.net.gt(0).sum()),tail_clusters=int(q.tails.gt(0).sum()),loo_winrate_min=float(looW.min()) if len(looW) else None,loo_winrate_max=float(looW.max()) if len(looW) else None,loo_mean_net_min=float(looN.min()) if len(looN) else None,loo_mean_net_max=float(looN.max()) if len(looN) else None,loo_tail_count_min=int(looT.min()) if len(looT) else None,loo_tail_count_max=int(looT.max()) if len(looT) else None,loo_defined=bool(ok.any()))
out=[];detail=[]
for r in s.itertuples():
 g=subset(period(r.period),r.axis,r.value)
 a=g[g.evidence_usable_closed.eq(True)]
 pnl,ret=('core_net','core_return') if r.layer=='CORE' else ('net_pnl','net_return_on_buy_cash')
 assert len(g)==r.permits and len(a)==r.usable_closed and int(a[pnl].gt(0).sum())==r.wins
 assert int(a[ret].ge(.3).sum())==r.final_net_ge30
 d=r._asdict();d.pop('Index',None)
 d['feature_contains_unknown']='UNKNOWN' in r.value
 for label,keys in [('date',['signal_day']),('industry',['sector']),('date_industry',['signal_day','sector']),('stock',['sid'])]:
  m=metric(a,keys,pnl,ret);d.update({label+'_'+k:v for k,v in m.items()})
 out.append(d)
 for _,q in a.assign(_wins=a[pnl].gt(0).astype(int),_tails=a[ret].ge(.3).astype(int)).groupby(['signal_day','sector'],dropna=False):
  detail.append(dict(period=r.period,axis=r.axis,value=r.value,layer=r.layer,signal_day=q.signal_day.iloc[0],sector=q.sector.iloc[0],trades=len(q),wins=int(q._wins.sum()),net=float(q[pnl].sum()),tail30=int(q._tails.sum())))
out=pd.DataFrame(out);out.to_csv(O/'ALL_FROZEN_STRATA_WITH_CLUSTERS.csv',index=False)
pd.DataFrame(detail).to_csv(O/'ALL_DATE_INDUSTRY_CLUSTERS.csv',index=False)
periods=['2022_Q1','2022_Q3','2024_924']
cols=['permits','usable_closed','wins','winrate','mean_net','payoff','final_net_ge30','financial_unusable_closed','execution_unknown','nofill','date_clusters','industry_clusters','date_industry_clusters','stock_clusters','date_max_trade_share','industry_max_trade_share','date_weight_equivalent_clusters','industry_weight_equivalent_clusters','date_tail_clusters','industry_tail_clusters','date_loo_winrate_min','date_loo_winrate_max','date_loo_mean_net_min','date_loo_mean_net_max','industry_loo_winrate_min','industry_loo_winrate_max','industry_loo_mean_net_min','industry_loo_mean_net_max']
wide=None
for p in periods:
 a=out[out.period.eq(p)][['axis','value','layer','feature_contains_unknown']+cols].copy()
 a=a.rename(columns={c:p+'__'+c for c in cols})
 wide=a if wide is None else wide.merge(a,on=['axis','value','layer','feature_contains_unknown'],validate='one_to_one')
assert len(wide)==148
wide.to_csv(O/'FIXED_WEAK_STRONG_INFORMATION_MATRIX.csv',index=False)
# Logical conjunction of the user's stated requirements only; no coverage threshold or best-cell search.
qa=dict(rows=len(z),summary_rows=len(out),cells_per_period_per_layer=74,wide_rows=len(wide),groups_overlap_not_independent=True,all_counts_match_existing=True,zero_new_features=True,zero_new_economics=True,requirement_check={})
for layer in ['CORE','FULL']:
 w=wide[wide.layer.eq(layer)];match=np.ones(len(w),bool)
 for p in periods:match&=(w[p+'__winrate'].ge(.35)&w[p+'__mean_net'].gt(0)&w[p+'__final_net_ge30'].gt(0)).to_numpy()
 qa['requirement_check'][layer]=dict(all_three_periods_win35_positive_mean_nonzero_tail_count=int(match.sum()),Q1_positive_mean_cells=int(out[out.period.eq('2022_Q1')&out.layer.eq(layer)].mean_net.gt(0).sum()),Q1_winrate35_cells=int(out[out.period.eq('2022_Q1')&out.layer.eq(layer)].winrate.ge(.35).sum()))
q=out[out.axis.eq('ALL')];q.to_csv(O/'PERIOD_BASELINES_WITH_CLUSTERS.csv',index=False)
save('SOURCE_HASHES.json',hashes);assert hashes=={p:sha(p) for p in hashes}
qa['seconds']=time.monotonic()-t0;save('QA.json',qa)
print(json.dumps(qa,indent=2),flush=True)
print(q[q.period.isin(periods)&q.layer.eq('CORE')][['period','usable_closed','winrate','mean_net','final_net_ge30','date_clusters','industry_clusters','date_industry_clusters','stock_clusters','date_max_trade_share','industry_max_trade_share','date_tail_clusters','industry_tail_clusters','date_loo_winrate_min','date_loo_winrate_max','industry_loo_winrate_min','industry_loo_winrate_max','date_loo_mean_net_min','date_loo_mean_net_max','industry_loo_mean_net_min','industry_loo_mean_net_max']].to_string(index=False),flush=True)
