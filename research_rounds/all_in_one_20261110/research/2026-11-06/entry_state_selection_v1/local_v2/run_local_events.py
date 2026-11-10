"""Frozen E2. No original model/account runs. Single sequential market-cache pass."""
from pathlib import Path
import json,time,hashlib
import numpy as np,pandas as pd
import pyarrow.dataset as ds,pyarrow.parquet as pq
BASE=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality')
ROOT=BASE/'daily_signal_cache_pilot20_v1/full_universe_v1'
OUT=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/local_v2')
V1=OUT.parent
files=sorted((ROOT/'artifacts').glob('*.parquet'))
cases=pd.read_csv(V1/'CASE_DATES.csv');casekeys=set(zip(cases.sid,cases.day))
tick=time.time()
d=ds.dataset([str(p)for p in files],format='parquet').to_table(columns=['sid','day','price__close']).to_pandas()
P=d.pivot(index='day',columns='sid',values='price__close').sort_index();del d
M=P.rolling(20,min_periods=20).mean();known=P.notna()&M.notna();above=P>M
breadth=above.where(known).mean(axis=1);pair=known&known.shift(5,fill_value=False)
delta=above.where(pair).mean(axis=1)-above.shift(5).where(pair).mean(axis=1)
reg=np.where(breadth>=.5,'SUPPORT',np.where(delta>0,'IMPROVING','WEAK'))
market={d.strftime('%Y-%m-%d'):(float(b),float(ch),r)for d,b,ch,r in zip(P.index,breadth,delta,reg)}
pd.DataFrame({'day':P.index,'breadth20':breadth,'paired_delta5':delta,'regime':reg}).to_csv(OUT/'MARKET_BREADTH.csv',index=False)
del P,M,known,above,pair
cols=['day','source_row_present','price__open','price__high','price__low','price__close','price__amount','native__e0_ready','native__g_ready','native__i_target','native__i_buy','pvr__score']
records=[];daily=[];stats=[]
def calc(path):
 sid=path.stem;f=pq.read_table(path,columns=cols).to_pandas();n=len(f)
 day=f.day.dt.strftime('%Y-%m-%d').to_numpy()
 C=f.price__close.to_numpy();O=f.price__open.to_numpy();H=f.price__high.to_numpy();L=f.price__low.to_numpy();A=f.price__amount.to_numpy()
 v=f.source_row_present.to_numpy()&np.isfinite(C)&np.isfinite(H)&np.isfinite(L)&np.isfinite(A)&(C>0)&(A>0)
 opgood=np.isfinite(O)&(O>0)
 buy=(f.native__e0_ready.eq(1)&f.native__g_ready.eq(True)&f.native__i_target.eq(1)&f.native__i_buy.eq(True)).to_numpy()
 pv=f.pvr__score.to_numpy()
 tr=np.full(n,np.nan);tr[1:]=np.maximum.reduce([H[1:]-L[1:],abs(H[1:]-C[:-1]),abs(L[1:]-C[:-1])])
 at=pd.Series(tr).shift().rolling(20,min_periods=20).mean().to_numpy()
 ar=pd.Series(A).shift().rolling(20,min_periods=20).median().to_numpy()
 cur=None;setup=None;waiting='NONE';seq=0;born=0;signal_n=0;local=[]
 for t in range(n):
  if not v[t]:
   cur=None;setup=None;waiting='UNKNOWN';continue
  if t<21 or not np.all(v[t-21:t+1]):continue
  newtype=None;b=None;s=None;a=at[t];fail=False
  if cur is not None:
   fail=C[t]<cur['S'] or (C[t]<cur['B'] and A[t]>=cur['Aref'] and C[t]<C[t-1])
   if fail:
    setup=dict(start=t,Hfail=H[t],trough=L[t],atr=at[t]);waiting='REPAIR_WAIT';cur=None
  if not fail:
   if waiting=='REPAIR_WAIT' and setup is not None:
    setup['trough']=min(setup['trough'],L[t])
    threshold=max(setup['Hfail'],max(C[t-2:t]))
    if t>setup['start'] and C[t]>threshold:
     newtype='RECLAIM';b=threshold;a=setup['atr'];s=setup['trough']-.25*a
   elif waiting=='PULLBACK_WAIT' and setup is not None:
    setup['trough']=min(setup['trough'],L[t])
    threshold=max(C[t-2:t])
    if t>setup['start'] and C[t]>threshold:
     newtype='PULLBACK';b=threshold;a=setup['atr'];s=setup['trough']-.25*a
   elif cur is not None:
    cur['peak']=max(cur['peak'],C[t])
    if t>cur['tau'] and C[t]<=cur['peak']-cur['atr']:
     setup=dict(start=t,peak=cur['peak'],trough=L[t],atr=at[t]);waiting='PULLBACK_WAIT'
   else:
    b=max(C[t-20:t])
    if C[t]>b:newtype='BREAK';s=min(L[t-5:t])-.25*a
  if newtype is not None and np.isfinite(a) and a>0 and 0<s<C[t]:
   seq+=1;born+=1;setup=None;waiting='ACTIVE'
   cur=dict(sid=sid,event_id=f'{sid}:{seq}',tau=t,tau_day=day[t],kind=newtype,B=float(b),S=float(s),atr=float(a),Aref=float(ar[t]),Ctau=float(C[t]),peak=float(C[t]),confirmed=False,used=False,base_W_ATR=float((max(C[t-20:t])-min(C[t-20:t]))/a),higher_low=bool(min(L[t-5:t])>min(L[t-20:t-5])),amount5vs15=float(np.median(A[t-5:t])/np.median(A[t-20:t-5])))
  if cur is not None and waiting=='ACTIVE' and t>cur['tau'] and C[t]>cur['B'] and C[t]>cur['Ctau']:
   tau=cur['tau']
   if np.sum(A[tau+1:t+1]*np.sign(np.diff(C[tau:t+1])))>0:cur['confirmed']=True
  active=cur is not None and waiting=='ACTIVE'
  if (sid,day[t]) in casekeys:
   daily.append(dict(sid=sid,day=day[t],waiting=waiting,state=('CONFIRMED' if cur['confirmed'] else 'PROBE')if active else waiting,tau=cur['tau_day']if cur else None,kind=cur['kind']if cur else None,B=cur['B']if cur else None,S=cur['S']if cur else None,atr=cur['atr']if cur else None,C=C[t],i_buy=bool(buy[t]),failure=fail,new_event=newtype is not None))
  if active and buy[t] and np.isfinite(pv[t]) and not cur['used']:
   cur['used']=True;signal_n+=1;r=cur.copy();r.pop('used');r.pop('peak');r['signal_index']=t;r['signal_day']=day[t];r['pvr']=float(pv[t]);r['signal_age']=t-cur['tau']
   # This is a next-open price benchmark, not a claimed fill. No future close/high/low/amount admission.
   ent=t+1;ok=ent<n and opgood[ent] and O[ent]>cur['S'];r['open_proxy_ok']=bool(ok);r['entry_index']=ent;r['entry_day']=day[ent]if ent<n else None;r['entry_open']=float(O[ent])if ent<n and opgood[ent]else np.nan
   r['next_open_missing']=bool(ent>=n or not opgood[ent]);r['next_open_below_support']=bool(ent<n and opgood[ent] and O[ent]<=cur['S'])
   r['market_breadth'],r['market_delta5'],r['market_regime']=market[day[t]]
   ep=C[[t,t-63,t-126,t-189,t-252]] if t>=252 else np.array([])
   r['h1']=float(np.sum((ep[:-1]/ep[1:]-1)*np.array([.4,.2,.2,.2])))if len(ep)==5 and np.isfinite(ep).all() and (ep>0).all()else np.nan
   r['risk_frac']=(O[ent]-cur['S'])/O[ent]if ok else np.nan;r['risk_atr']=(O[ent]-cur['S'])/cur['atr']if ok else np.nan
   r['zbin']=('LE2' if r['risk_atr']<=2 else 'LE4' if r['risk_atr']<=4 else 'GT4')if ok else 'UNKNOWN'
   r['entry_gap']=float(O[ent]/C[t]-1)if ok else np.nan
   r['cell']='|'.join([r['kind'],str(int(r['confirmed'])),r['market_regime'],r['zbin']])
   r['entry_flat_ohlc_posthoc']=bool(ent<n and O[ent]==H[ent]==L[ent]==C[ent])
   for h in [20,60]:
    end=ent+h-1;labelok=ok and end<n and np.all(v[ent:end+1]);r['mature_day'+str(h)]=day[end]if end<n else None
    arr=C[ent:end+1]if labelok else np.array([])
    r['ret'+str(h)]=float(arr[-1]/O[ent]-1)if labelok else np.nan;r['mfe'+str(h)]=float(max(0,arr.max()/O[ent]-1))if labelok else np.nan;r['mae'+str(h)]=float(min(0,arr.min()/O[ent]-1))if labelok else np.nan
    rr=np.nan;exreason=None;exday=None
    if labelok:
     rr=float(C[end]/O[ent]-1);exreason='terminal'+str(h);exday=day[end]
     for u in range(ent,end+1):
      broken=C[u]<r['S'] or (C[u]<r['B'] and A[u]>=r['Aref'] and C[u]<C[u-1])
      if broken:
       # Failure on final horizon close cannot use next open outside the horizon.
       if u==end:break
       if not opgood[u+1]:rr=np.nan;exreason='missing_exit_open';exday=None
       else:rr=float(O[u+1]/O[ent]-1);exreason='failure_next_open';exday=day[u+1]
       break
    r['proxy_ret'+str(h)]=rr;r['proxy_exit_reason'+str(h)]=exreason;r['proxy_exit_day'+str(h)]=exday
   local.append(r)
 records.extend(local);stats.append(dict(sid=sid,born=born,entry_signals=signal_n))
for k,path in enumerate(files):
 calc(path)
 if(k+1)%500==0:print('processed',k+1,'events',len(records),'seconds',round(time.time()-tick,1),flush=True)
events=pd.DataFrame(records)
events.to_parquet(OUT/'ALL_LOCAL_ENTRY_EVENTS.parquet',index=False)
pd.DataFrame(daily).to_csv(OUT/'KNOWN_CASE_DAYS.csv',index=False)
pd.DataFrame(stats).to_csv(OUT/'STOCK_EVENT_COUNTS.csv',index=False)
# Quarterly prequential diagnostic, fixed model family; no parameter search.
events['entry_month']=events.entry_day.str[:7];events['signal_dt']=pd.to_datetime(events.signal_day)
events['mature_dt']=pd.to_datetime(events.mature_day60);events['quarter']=events.signal_dt.dt.to_period('Q').astype(str)
events['model_known']=False;events['model_N']=0;events['model_months']=0;events['model_stocks']=0;events['lcb_net']=np.nan;events['tail_loss']=np.nan;events['gap99']=np.nan;events['rank_value']=np.nan
model=[]
for quarter,g in events.groupby('quarter'):
 cutoff=pd.Period(quarter).start_time
 train=events[(events.mature_dt<cutoff)&(events.signal_dt>=cutoff-pd.DateOffset(years=3))&events.open_proxy_ok&events.proxy_ret60.notna()].copy()
 for cell,vv in train.groupby('cell'):
  N=len(vv);ns=vv.sid.nunique();nm=vv.entry_month.nunique()
  target=g.index[g.cell.eq(cell)]
  events.loc[target,['model_N','model_months','model_stocks']]=[N,nm,ns]
  known=N>=200 and ns>=50 and nm>=12
  row=dict(quarter=quarter,cutoff=str(cutoff.date()),cell=cell,N=N,stocks=ns,months=nm,known=known,max_training_maturity=str(vv.mature_dt.max().date()))
  if known:
   block=vv.assign(net=vv.proxy_ret60-.005).groupby('entry_month').net.mean().to_numpy()
   rng=np.random.default_rng(20261106);bm=rng.choice(block,size=(1000,len(block)),replace=True).mean(axis=1);lb=float(np.quantile(bm,.1))
   losses=np.maximum(0,-(vv.proxy_ret60.to_numpy()-.005));tail=float(np.sort(losses)[-max(1,int(np.ceil(.1*N))):].mean());gap=float(np.quantile(abs(vv.entry_gap.dropna()),.99))
   row.update(lcb_net=lb,tail_loss=tail,gap99=gap)
   den=np.maximum.reduce([events.loc[target,'risk_frac'].to_numpy(),np.full(len(target),tail),np.full(len(target),gap)])
   events.loc[target,'model_known']=True;events.loc[target,'lcb_net']=lb;events.loc[target,'tail_loss']=tail;events.loc[target,'gap99']=gap;events.loc[target,'rank_value']=lb/den
  model.append(row)
events.to_parquet(OUT/'SCORED_LOCAL_ENTRY_EVENTS.parquet',index=False)
pd.DataFrame(model).to_csv(OUT/'QUARTERLY_MATURED_MODEL.csv',index=False)
selections=[]
for day,g in events[events.open_proxy_ok].groupby('signal_day'):
 for name,col in [('PVR','pvr'),('H1','h1'),('E2','rank_value')]:
  v=g[g[col].notna()]
  if name=='E2':v=v[v.rank_value>0]
  v=v.sort_values([col,'sid'],ascending=[False,True]).head(20)
  for _,r in v.iterrows():selections.append(dict(strategy=name,**r.to_dict()))
sel=pd.DataFrame(selections);sel.to_parquet(OUT/'EVENT_TOP20_SELECTIONS.parquet',index=False)
summary=[]
for(year,strat),g in sel.groupby([sel.signal_dt.dt.year,'strategy']):
 q=g[g.proxy_ret60.notna()];big=g.mfe60.ge(.3)&g.ret60.ge(.2)
 summary.append(dict(year=int(year),strategy=strat,selected_events=len(g),complete60=len(q),mean_net_proxy60=(q.proxy_ret60-.005).mean(),median_net_proxy60=(q.proxy_ret60-.005).median(),mean_fixed60=g.ret60.mean(),mean_mae60=g.mae60.mean(),big60=int(big.sum()),failure_later_big=int((big&g.proxy_exit_reason60.eq('failure_next_open')).sum()),avg_stop_risk=g.risk_frac.mean()))
pd.DataFrame(summary).to_csv(OUT/'ANNUAL_EVENT_TOP20.csv',index=False)
coverage=[]
for y,g in events.groupby(events.signal_dt.dt.year):
 q=g[g.open_proxy_ok];coverage.append(dict(year=int(y),events=len(g),open_proxies=len(q),model_known=int(q.model_known.sum()),model_known_fraction=q.model_known.mean(),positive_score=int(q.rank_value.gt(0).sum()),label60_known=int(q.proxy_ret60.notna().sum()),gap_gt3pct=int(q.entry_gap.gt(.03).sum()),flat_posthoc=int(q.entry_flat_ohlc_posthoc.sum())))
pd.DataFrame(coverage).to_csv(OUT/'COVERAGE.csv',index=False)
(OUT/'COMPLETION.json').write_text(json.dumps(dict(status='COMPLETE_PREQUENTIAL_HISTORICAL_DEVELOPMENT_NOT_OOS',stocks=len(files),events=len(events),seconds=time.time()-tick,account_runs=0,parameter_grids=0,signal_reruns=0,source_cache_unmodified=True,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
print('COVERAGE');print(pd.DataFrame(coverage).to_string(index=False));print('SUMMARY');print(pd.DataFrame(summary).to_string(index=False))
