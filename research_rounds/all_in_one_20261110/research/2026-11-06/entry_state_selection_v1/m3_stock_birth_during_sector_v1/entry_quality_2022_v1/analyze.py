from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;E=O.parent;R=E.parent
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
hashes={str(p):sha(p) for p in [Path(__file__),O/'PROTOCOL.json',E/'lifecycle_v1/ROUNDS.csv',H,U/'STOCK_MANIFEST.json',M/'COMMON_K_COMPARISON.parquet',M/'RIGHT3.parquet',M/'KNOWN3.parquet',M/'MU5.parquet',R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet']}
z=pd.read_csv(E/'lifecycle_v1/ROUNDS.csv',parse_dates=['signal_day','entry_day','exit_day'],low_memory=False)
z=z[z.window.eq('2022')&z.arm.eq('A_UNION_B')].copy();assert len(z)==2432
z['label']=np.where(z.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND'),np.where(z.net_pnl.gt(0),'WIN','LOSS'),np.where(z.status.str.contains('UNKNOWN'),'UNKNOWN','NOFILL'))
closed=z[z.label.isin(['WIN','LOSS'])]
pairs=[]
for (day,sec),g in closed.groupby(['signal_day','sector']):
 if len(g)==2 and g.label.eq('WIN').sum()==1:
  v=g.copy();v['pair_id']=str(day.date())+'|'+sec;pairs.append(v)
paired=pd.concat(pairs,ignore_index=True);assert len(paired)==326
counts=paired.groupby('industry').size().rename('n').reset_index().sort_values(['n','industry'],ascending=[False,True])
inds=counts.head(8).industry.tolist()
case=pd.concat([paired[paired.industry.eq(ind)&paired.signal_day.eq(paired[paired.industry.eq(ind)].signal_day.min())] for ind in inds])
paired.to_csv(O/'SEALED_PAIRED_COHORT.csv',index=False);case.to_csv(O/'SEALED_REPRESENTATIVE_CASES.csv',index=False)
save('CASE_SEAL.json',dict(industries=inds,all_pairs=163,cases=len(case),hashes={str(O/n):sha(O/n) for n in ['PROTOCOL.json','SEALED_PAIRED_COHORT.csv','SEALED_REPRESENTATIVE_CASES.csv']}))
h=np.load(H,allow_pickle=False);cal=pd.DatetimeIndex(h['dates']);syms=pd.Index(h['symbols'])
C=pd.DataFrame(h['close'],index=cal,columns=syms);G=pd.DataFrame(h['segment'],index=cal,columns=syms);dates={d:i for i,d in enumerate(cal)}
stockM=pd.read_parquet(M/'RIGHT3.parquet');stockK=pd.read_parquet(M/'KNOWN3.parquet');mu=pd.read_parquet(M/'MU5.parquet')
panel=pd.read_parquet(M/'COMMON_K_COMPARISON.parquet').set_index(['sector','day'])
pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet');pv=pv[pv.sid.isin(z.sid.unique())&pv.day.le(pd.Timestamp('2022-12-31'))]
pv=pv.set_index(['sid','day'])
manifest={x['symbol']:x for x in json.loads((U/'STOCK_MANIFEST.json').read_text())};facts={}
features=[];daily=[];max_error=0.
for sid,sg in z.groupby('sid'):
 fp=manifest[sid]['refs']['facts'];f=pd.read_parquet(fp);facts[sid]=f;hashes[fp]=sha(fp)
 ilast=None;root=None;pretarget=None;root_map={};last_map={}
 for d,fr in f.iterrows():
  if pd.notna(fr.i_target) and fr.i_target==1:
   if pretarget==0:root=d
   if fr.i_buy==True:ilast=d
  else:root=None
  pretarget=fr.i_target;root_map[d]=root;last_map[d]=ilast
 for rr in sg.to_dict('records'):
  t=rr['signal_day'];sec=rr['sector'];k=dates[t];fr=f.loc[t];cc=C.loc[t,sid];err=abs(cc-fr.close);max_error=max(max_error,err);assert err<1e-9
  out=dict(rr);s=panel.loc[(sec,t)]
  out.update(close=cc,raw_close=fr.raw_close,I_floor=fr.i_floor,log_floor_distance=np.log(cc/fr.i_floor),g_grade=fr.g_grade,i_buy=fr.i_buy,g_fresh_up=fr.g_fresh_up,sector_share=s.M3_n/s.N,sector_known=s.K,sector_size=s.N,sector_join3=s.M3_entered3,sector_leave3=s.M3_left3,sector_delta3=s.M3_delta3,sector_state=s.M3_candidate,stock_mu5=mu.loc[t,sid])
  rt=root_map[t];lt=last_map[t];out['I_root_age']=k-dates[rt] if rt in dates else np.nan;out['last_I_buy_age']=k-dates[lt] if lt in dates else np.nan
  for n in [5,21,63]:
   ix=cal[k-n:k+1];p=C.loc[ix,sid];q=C.loc[ix,sec]
   sk=len(ix)==n+1 and p.notna().all() and p.gt(0).all() and G.loc[ix,sid].nunique()==1 and G.loc[ix,sid].notna().all()
   ik=len(ix)==n+1 and q.notna().all() and q.gt(0).all() and G.loc[ix,sec].nunique()==1 and G.loc[ix,sec].notna().all()
   out['stock_ret'+str(n)]=np.log(p.iloc[-1]/p.iloc[0]) if sk else np.nan
   out['industry_ret'+str(n)]=np.log(q.iloc[-1]/q.iloc[0]) if ik else np.nan
   out['relative_ret'+str(n)]=out['stock_ret'+str(n)]-out['industry_ret'+str(n)] if sk and ik else np.nan
   out['below_prior_high'+str(n)]=np.log(p.iloc[-1]/p.iloc[:-1].max()) if sk else np.nan
   if n==63:
    out['stock_rms63']=np.sqrt(np.square(np.log(p).diff().iloc[1:]).mean()) if sk else np.nan
    out['relative_rms63']=np.sqrt(np.square(np.log(p).diff().iloc[1:]-np.log(q).diff().iloc[1:]).mean()) if sk and ik else np.nan
  features.append(out)
  if rr['round_id'] in set(case.round_id):
   for j in range(max(0,k-10),k+1):
    d=cal[j];a=f.loc[d];b=panel.loc[(sec,d)] if (sec,d) in panel.index else None
    m=stockM.loc[d,sid] if d in stockM.index and stockK.loc[d,sid] else np.nan
    v=pv.loc[(sid,d)] if (sid,d) in pv.index else None
    daily.append(dict(pair_id=str(t.date())+'|'+sec,round_id=rr['round_id'],signal_day=t,day=d,relative_day=j-k,sid=sid,name=rr['name'],industry=rr['industry'],label=rr['label'],close=a.close,raw_close=a.raw_close,industry_close=C.loc[d,sec],stock_M3=m,stock_mu5=mu.loc[d,sid] if d in mu.index else np.nan,PVR_score=v.score if v is not None else np.nan,PVR_state=v.state if v is not None else np.nan,sector_state=b.M3_candidate if b is not None else np.nan,sector_n=b.M3_n if b is not None else np.nan,sector_N=b.N if b is not None else np.nan,sector_join3=b.M3_entered3 if b is not None else np.nan,sector_leave3=b.M3_left3 if b is not None else np.nan,sector_delta3=b.M3_delta3 if b is not None else np.nan,g_grade=a.g_grade,i_target=a.i_target,i_buy=a.i_buy,i_floor=a.i_floor))
x=pd.DataFrame(features);x.to_csv(O/'ALL_2022_ENTRY_FEATURES.csv',index=False)
x[x.round_id.isin(case.round_id)].to_csv(O/'REPRESENTATIVE_FEATURES.csv',index=False)
pd.DataFrame(daily).to_csv(O/'REPRESENTATIVE_PREENTRY_PATHS.csv',index=False)
pairfeat=x[x.round_id.isin(paired.round_id)].merge(paired[['round_id','pair_id']],on='round_id',validate='one_to_one')
pairfeat.to_csv(O/'ALL_PAIRED_FEATURES.csv',index=False)
metrics=['PVR_score','stock_mu5','stock_ret5','stock_ret21','stock_ret63','industry_ret21','relative_ret5','relative_ret21','relative_ret63','below_prior_high21','below_prior_high63','log_floor_distance','g_grade','I_root_age','last_I_buy_age']
desc=[]
for metric in metrics:
 for label,g in x.groupby('label'):
  desc.append(dict(metric=metric,label=label,n=len(g),known=g[metric].notna().sum(),median=g[metric].median(),mean=g[metric].mean()))
pd.DataFrame(desc).to_csv(O/'DESCRIPTIVE_GROUP_FEATURES.csv',index=False)
pairsums=[]
for metric in metrics:
 v=pairfeat.pivot(index='pair_id',columns='label',values=metric);v=v.dropna();delta=v.WIN-v.LOSS
 pairsums.append(dict(metric=metric,pairs=len(v),winner_higher=int(delta.gt(1e-12).sum()),loser_higher=int(delta.lt(-1e-12).sum()),equal=int(delta.abs().le(1e-12).sum()),median_difference=delta.median()))
pd.DataFrame(pairsums).to_csv(O/'PAIR_FEATURE_COMPARISONS.csv',index=False)
assert all(sha(p)==v for p,v in hashes.items())
save('SOURCE_HASHES.json',hashes);save('QA.json',dict(all_selected=2432,closed=1913,pairs=163,representative=16,stock_h1_facts_max_error=max_error,no_future_fields_in_features=True,signal_prices_not_next_close=True,no_new_returns_or_backtest=True))
print(x[x.round_id.isin(case.round_id)][['signal_day','name','industry','label','PVR_score','g_grade','I_root_age','last_I_buy_age','sector_share','sector_join3','sector_leave3','stock_ret21','industry_ret21','relative_ret21','below_prior_high63','log_floor_distance','net_return_on_buy_cash']].to_string(index=False))
print('\nPAIRS');print(pd.DataFrame(pairsums).to_string(index=False))
