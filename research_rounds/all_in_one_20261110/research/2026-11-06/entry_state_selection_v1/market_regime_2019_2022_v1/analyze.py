from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1'); O=Path(__file__).parent
S=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/sector-data-v2'); U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
hs={}
def h(p):p=Path(p);hs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def js(p):return json.loads(h(p).read_text())
def pq(p,**kw):return pd.read_parquet(h(p),**kw)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
phases=[
('P01','2019春季普涨','2018-12-28','2019-04-19'),
('P02','2019春后回撤','2019-04-19','2019-08-06'),
('P03','2019下半年结构行情','2019-08-06','2020-01-14'),
('P04','2020疫情冲击及剧烈反复','2020-01-14','2020-03-23'),
('P05','2020春夏修复','2020-03-23','2020-07-13'),
('P06','2020下半年至2021春节结构牛市','2020-07-13','2021-02-10'),
('P07','2021春节后抱团回撤','2021-02-10','2021-03-09'),
('P08','2021新能源资源第二波','2021-03-09','2021-09-13'),
('P09','2021秋冬分化退潮','2021-09-13','2021-12-31'),
('P10','2022初至4月普跌','2021-12-31','2022-04-26'),
('P11','2022春夏修复与新能源延续','2022-04-26','2022-08-17'),
('P12','2022夏末秋季回撤','2022-08-17','2022-10-31'),
('P13','2022年末结构修复','2022-10-31','2022-12-30'),
('C01','跨段科技完整观察','2019-08-06','2020-02-25'),
('C02','跨段消费新能源完整观察','2020-03-23','2021-02-10')]
protocol=dict(purpose='User requested subjective ex-post market segmentation; not signal rules or backtest',fixed_periods=[dict(period=a,label=b,start=c,end=d) for a,b,c,d in phases],boundaries='Subjective reference endpoints selected using historical knowledge, not optimized bottoms/tops, not causally detectable signal dates',indices='All 90 currently mapped THS industries; raw index close price returns, not dividend total return',membership='1709 current static survivors/current industry mapping, NOT historical all-A/PIT denominator',metrics='end/start-1; observed close chronological MDD=min(C/cummax(C)-1), max/min relative start; positive-sector and positive-member proportions; all unknown denominators retained',fat_tail='Qualitative judgment for discussion, no numeric threshold or admission rule',new_account_runs=0,parameter_searches=0)
save('PROTOCOL.json',protocol)
manifest=[x for x in js(S/'manifest.json')['series'] if x['market']=='A'];assert len(manifest)==90
idx={};quality=[]
for m in manifest:
 z=pq(m['bars']['path']);z=z.loc['2018-12-28':'2022-12-30'];ok=z.observed_bar.eq(True)&z.price_eligible.eq(True)&~z.source_invalid.eq(True)&z.close.gt(0)&np.isfinite(z.close)
 idx[m['symbol']]=z.close.where(ok);quality.append(dict(symbol=m['symbol'],name=m['name'],start=str(z.index.min()),end=str(z.index.max()),bars=len(z),valid=int(ok.sum()),source_kind='|'.join(z.source_kind.dropna().unique()),source_path_count=z.source_path.nunique()))
calendar=pd.DatetimeIndex(sorted(set().union(*(set(s.index) for s in idx.values()))));C=pd.DataFrame(idx).reindex(calendar);names={m['symbol']:m['name'] for m in manifest}
rows=[];summ=[]
for pid,label,b,e in phases:
 w=C.loc[b:e];rr=[]
 for sid,s in w.items():
  valid=s.dropna();pair=np.isfinite(s.iloc[0]) and np.isfinite(s.iloc[-1]);r=s.iloc[-1]/s.iloc[0]-1 if pair else np.nan;dd=valid/valid.cummax()-1
  z=dict(period=pid,label=label,start=b,end=e,sector=sid,industry=names[sid],ret=r,n_sessions=len(s),known_closes=len(valid),missing_closes=int(s.isna().sum()),start_close=s.iloc[0],end_close=s.iloc[-1],MDD=dd.min(),max_from_start=valid.max()/s.iloc[0]-1,min_from_start=valid.min()/s.iloc[0]-1,peak_day=valid.idxmax(),trough_day=valid.idxmin(),MDD_trough=dd.idxmin(),MDD_peak=valid.loc[:dd.idxmin()].idxmax()); rows.append(z);rr.append(z)
 t=pd.DataFrame(rr);summ.append(dict(period=pid,label=label,start=b,end=e,sector_N=90,endpoint_K=int(t.ret.notna().sum()),positive=int(t.ret.gt(0).sum()),negative=int(t.ret.lt(0).sum()),median_return=t.ret.median(),median_MDD=t.MDD.median(),all_complete=bool(t.missing_closes.eq(0).all()),leaders='; '.join(f'{x.industry} {x.ret:.1%}' for x in t.nlargest(6,'ret').itertuples()),laggards='; '.join(f'{x.industry} {x.ret:.1%}' for x in t.nsmallest(3,'ret').itertuples())))
T=pd.DataFrame(rows);T.to_csv(O/'INDUSTRY_PHASES.csv',index=False);pd.DataFrame(summ).to_csv(O/'PHASE_SUMMARY.csv',index=False);pd.DataFrame(quality).to_csv(O/'INDUSTRY_SOURCE_QUALITY.csv',index=False);C.to_csv(O/'INDUSTRY_DAILY_CLOSE.csv')
print(pd.DataFrame(summ).to_string(index=False),flush=True)
roster=pd.read_csv(h(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')).set_index('sid');sm=js(U/'STOCK_MANIFEST.json');st=[]
for j,m in enumerate(sm):
 sid=m['symbol'];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));q=pq(p,columns=['close','raw_close','adjustment_factor','observed_bar','price_eligible','source_invalid','source_kind','source_path','segment_id']).loc['2018-12-28':'2022-12-30'];ok=q.observed_bar.eq(True)&q.price_eligible.eq(True)&~q.source_invalid.eq(True)&q.close.gt(0)&np.isfinite(q.close);s=q.close.where(ok);ident=q.source_kind.astype('string')+'|'+q.source_path.astype('string')+'|'+q.segment_id.astype('string')
 for pid,label,b,e in phases:
  b=pd.Timestamp(b);e=pd.Timestamp(e);w=s.loc[b:e];v=w.dropna();same=len(v)>0 and ident.loc[b:e].dropna().nunique()==1;pair=b in s.index and e in s.index and np.isfinite(s.get(b,np.nan)) and np.isfinite(s.get(e,np.nan)) and same
  st.append(dict(period=pid,sid=sid,name=roster.loc[sid,'name'],sector=roster.loc[sid,'sector_id'],industry=roster.loc[sid,'industry'],endpoint_same_source_known=pair,known_prices=len(v),common_calendar_days=len(calendar[(calendar>=b)&(calendar<=e)]),ret=s.loc[e]/s.loc[b]-1 if pair else np.nan,MDD=(v/v.cummax()-1).min() if pair else np.nan,max_from_start=v.max()/s.loc[b]-1 if pair else np.nan,peak_day=v.idxmax() if pair else None))
 if (j+1)%500==0:print('stock files read',j+1,flush=True)
ST=pd.DataFrame(st);ST.to_csv(O/'STATIC_1709_STOCK_PHASES.csv',index=False)
agg=[]
for (pid,sec),g in ST.groupby(['period','sector']):
 k=g.ret.notna();agg.append(dict(period=pid,sector=sec,industry=g.industry.iloc[0],current_N=len(g),endpoint_known=int(k.sum()),unknown=int((~k).sum()),positive=int(g.ret.gt(0).sum()),negative=int(g.ret.lt(0).sum()),positive_share_known=g.ret.gt(0).sum()/k.sum() if k.sum() else None,positive_share_lower=g.ret.gt(0).sum()/len(g),positive_share_upper=(g.ret.gt(0).sum()+(~k).sum())/len(g),median_member_return=g.ret.median(),member_max_return=g.ret.max()))
A=pd.DataFrame(agg);A.to_csv(O/'STATIC_MEMBER_BREADTH.csv',index=False);T.merge(A,on=['period','sector','industry'],validate='one_to_one').to_csv(O/'INDUSTRY_WITH_MEMBER_BREADTH.csv',index=False)
ST[ST.ret.notna()].sort_values(['period','ret'],ascending=[True,False]).groupby('period').head(10).to_csv(O/'EX_POST_TOP10_CURRENT_POOL_STOCKS.csv',index=False)
save('SOURCE_HASHES.json',hs);save('QA.json',dict(industries=len(idx),stocks=len(sm),periods=len(phases),industry_rows=len(T),stock_rows=len(ST),sector_complete_by_period={x['period']:x['all_complete'] for x in summ},no_source_changes=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hs.items()),account_runs=0,parameter_searches=0))
print('DONE',O,flush=True)
