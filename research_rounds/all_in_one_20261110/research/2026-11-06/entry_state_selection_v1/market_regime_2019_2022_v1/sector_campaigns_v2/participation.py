from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).parent;T=pd.read_csv(O/'USER_REVIEW_CAMPAIGNS.csv');ST=pd.read_csv(O/'CAMPAIGN_STATIC_MEMBER_RETURNS.csv');S=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/sector-data-v2');U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');im=json.loads((S/'manifest.json').read_text())['series'];sm=json.loads((U/'STOCK_MANIFEST.json').read_text());D={};dates={}
for r in T.itertuples():
 m=next(m for m in im if m['market']=='A' and m['name']==r.industry);cal=pd.read_parquet(m['bars']['path']).loc[r.start:r.end].index;dates[r.campaign]=cal;D[r.campaign]={'n':np.zeros(len(cal),dtype=int),'k':np.zeros(len(cal),dtype=int)}
known=ST[ST.known.eq(True)]
for m in sm:
 sid=m['symbol'];tt=known[known.sid.eq(sid)]
 if tt.empty:continue
 p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));q=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid']);ok=q.observed_bar.eq(True)&q.price_eligible.eq(True)&~q.source_invalid.eq(True)&q.close.gt(0);s=q.close.where(ok)
 for c in tt.campaign:
  cal=dates[c];w=s.reindex(cal);valid=w.notna();rise=valid&w.gt(w.iloc[0]);D[c]['k']+=valid.to_numpy(dtype=int);D[c]['n']+=rise.to_numpy(dtype=int)
rows=[];daily=[]
for r in T.itertuples():
 c=r.campaign;z=ST[(ST.campaign.eq(c))&ST.known.eq(True)];rets=z.ret;pos=rets.clip(lower=0);total=pos.sum();weights=pos/total if total else pos;top=pos.nlargest(3).sum()/total if total else np.nan;eff=1/(weights**2).sum() if total else np.nan;cal=dates[c];n=D[c]['n'];k=D[c]['k'];ratio=np.divide(n,k,out=np.full(len(k),np.nan),where=k>0)
 a=dict(campaign=c,member_p25=rets.quantile(.25),member_median=rets.median(),member_p75=rets.quantile(.75),positive_return_top3_share=top,positive_return_effective_n=eff,daily_positive_fraction_median=np.nanmedian(ratio[1:]),daily_known_min=int(k.min()),endpoint_cohort_K=len(z))
 for frac in [.25,.5,.75,1]:
  ix=int(round((len(cal)-1)*frac));label=str(int(frac*100));a[f'checkpoint_{label}_date']=str(cal[ix].date());a[f'checkpoint_{label}_n']=int(n[ix]);a[f'checkpoint_{label}_K']=int(k[ix])
 rows.append(a)
 for day,nn,kk in zip(cal,n,k):daily.append(dict(campaign=c,day=day,positive=int(nn),known=int(kk)))
A=pd.DataFrame(rows);A.to_csv(O/'MEMBER_PARTICIPATION_CONCENTRATION.csv',index=False);pd.DataFrame(daily).to_csv(O/'MEMBER_DAILY_PARTICIPATION.csv',index=False);T=T.merge(A,on='campaign',validate='one_to_one');assert T.endpoint_cohort_K.eq(T.K).all();T.to_csv(O/'USER_REVIEW_WITH_PARTICIPATION.csv',index=False)
print(T[T.priority.eq('重点')][['industry','start','end','n','K','N','member_p25','member_median','positive_return_top3_share','positive_return_effective_n','daily_positive_fraction_median']].to_string(index=False))
