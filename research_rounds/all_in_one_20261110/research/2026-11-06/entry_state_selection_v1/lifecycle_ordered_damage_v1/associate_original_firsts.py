from pathlib import Path
import pandas as pd,numpy as np,json,math,hashlib,time
O=Path(__file__).resolve().parent;B=O.parent/'selection_entry_diagnosis_v1'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
HP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
rho=20/21;floor=math.log1p(.001)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
m={r['symbol']:r for r in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(HP,allow_pickle=False)['dates'])
fst=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv');fst=fst[fst.account.eq('PVR')].copy()
keys=fst[['sid','signal_day']].copy();allcols=[];checks=[];src=[];t0=time.monotonic()
old=pd.read_csv(O/'FULL_PREFIX_STATES.csv');old['day']=pd.to_datetime(old.day)
def state(f):
 n=len(f);p=np.log(f.close.to_numpy());r=np.r_[np.nan,np.diff(p)];seg=f.segment_id.to_numpy();loc=cal.get_indexer(f.index)
 reset=np.r_[True,(seg[1:]!=seg[:-1])|(loc[1:]!=loc[:-1]+1)|(loc[1:]<0)|(loc[:-1]<0)]
 block=np.cumsum(reset);r[reset]=np.nan
 sig=pd.Series(r,index=f.index).groupby(block).transform(lambda q:q.shift().rolling(63,min_periods=63).apply(lambda x:np.sqrt(np.mean(x*x)),raw=True)).clip(lower=floor).to_numpy()
 U=H=H0=0.;known=0;rows=[]
 for j in range(n):
  if reset[j]:U=H=H0=0.;known=0
  s=sig[j];rr=r[j];a=U/(U+math.sqrt(21)*s)if np.isfinite(s)else np.nan
  if np.isfinite(rr):U=max(0.,rho*U+rr)
  health=plain=np.nan
  if np.isfinite(s)and np.isfinite(rr):
   shock=(max(-rr,0.)/s)**2;H=rho*H+(1-rho)*a*shock;H0=rho*H0+(1-rho)*shock;known+=1;health=1/(1+H);plain=1/(1+H0)
  rows.append((health,plain,a,H if np.isfinite(health)else np.nan,H0 if np.isfinite(plain)else np.nan,s,U,known,known>=63,bool(reset[j])))
 return pd.DataFrame(rows,index=f.index,columns=['health','plain_health','advance_fraction','damage','plain_damage','sigma','advance_after','observations_scale_known','fully_warmed','source_reset'])
for no,(sid,g)in enumerate(keys.groupby('sid')):
 p=m[sid]['refs']['facts'];h=sha(p);f=pd.read_parquet(p).loc[:'2026-05-15'];z=state(f)
 if sid in set(old.sid):
  q=old[old.sid.eq(sid)].set_index('day');cols=['health','advance_fraction','damage','sigma','advance_after','observations_scale_known'];diff=(z[cols]-q[cols]).abs().max().max();assert diff<1e-12,(sid,diff);checks.append(dict(sid=sid,max_array_reimplementation_diff=float(diff)))
 wanted=pd.to_datetime(g.signal_day);v=z.reindex(wanted).copy();v['sid']=sid;v['signal_day']=g.signal_day.to_numpy();v['native_close']=f.close.reindex(wanted).to_numpy();allcols.append(v.reset_index(drop=True))
 assert sha(p)==h;src.append(dict(sid=sid,path=p,sha256=h,rows=len(f)))
 if(no+1)%200==0:print('stocks',no+1,'seconds',round(time.monotonic()-t0,2),flush=True)
state_only=pd.concat(allcols,ignore_index=True);state_only.to_csv(O/'SEALED_ORIGINAL_FIRST_STATES.csv',index=False)
dump('ASSOCIATION_STATE_SEAL.json',dict(state_file_sha=sha(O/'SEALED_ORIGINAL_FIRST_STATES.csv'),protocol_sha=sha(O/'ASSOCIATION_PROTOCOL.json'),code_sha=sha(Path(__file__)),future_labels_in_state=[],seconds=time.monotonic()-t0))
pd.DataFrame(src).to_csv(O/'ASSOCIATION_SOURCE_HASHES.csv',index=False);pd.DataFrame(checks).to_csv(O/'ARRAY_EQUIVALENCE_CHECKS.csv',index=False)
# State is sealed before label association.
z=fst.merge(state_only,on=['sid','signal_day'],how='left',validate='one_to_one');z['native_close_error']=(z.native_close-z.original_close).abs();z['win']=z.round_pnl>0
z['primary_closed']=z.closed & ((z.year!=2022)|z.closed_in_entry_year)
z.to_csv(O/'ALL_ORIGINAL_FIRST_ASSOCIATIONS.csv',index=False)
def auc(y,s):
 v=pd.DataFrame(dict(y=y,s=s)).dropna();npos=int(v.y.sum());nneg=len(v)-npos
 if not npos or not nneg:return np.nan
 return (v.s.rank(method='average')[v.y].sum()-npos*(npos+1)/2)/(npos*nneg)
def strat_auc(g,col):
 numer=denom=0
 for _,q in g.groupby(['first_kind','market_regime']):
  q=q[q[col].notna()];p=int(q.win.sum());n=len(q)-p
  if p and n:numer+=auc(q.win,q[col])*p*n;denom+=p*n
 return numer/denom if denom else np.nan
stats=[];dist=[]
for mode in ['primary','terminal_all','fully_warmed_primary']:
 for year,g0 in z.groupby('year'):
  g=g0[g0.primary_closed if mode!='terminal_all' else g0.closed]
  if mode=='fully_warmed_primary':g=g[g.fully_warmed]
  base=dict(sample=mode,year=int(year),original_firsts=len(g0),original_unclosed=int((~g0.closed).sum()),included_closed=len(g),health_known=int(g.health.notna().sum()),health_unknown=int(g.health.isna().sum()),wins=int(g.win.sum()),original_net_win_rate=float(g.win.mean())if len(g)else np.nan)
  for col in ['health','plain_health','PVR_decision','advance_fraction']:
   q=g[g[col].notna()]
   rr=base|dict(feature=col,AUC=auc(q.win,q[col]),role_market_stratified_AUC=strat_auc(g,col),spearman_round_return=float(q[col].corr(q.round_return_on_cumulative_cost,method='spearman')),spearman_forward20=float(q[col].corr(q.ret20_forward,method='spearman')))
   stats.append(rr)
   for outcome,gg in q.groupby('win'):
    dist.append(dict(sample=mode,year=int(year),feature=col,win=bool(outcome),n=len(gg),mean=gg[col].mean(),q25=gg[col].quantile(.25),median=gg[col].median(),q75=gg[col].quantile(.75)))
pd.DataFrame(stats).to_csv(O/'ANNUAL_CONTINUOUS_ASSOCIATIONS.csv',index=False);pd.DataFrame(dist).to_csv(O/'WIN_LOSS_DISTRIBUTIONS.csv',index=False)
cor=[]
for year,g in z.groupby('year'):
 for col in ['plain_health','PVR_decision','ret20','sigma20_prior','advance_fraction']:
  cor.append(dict(year=int(year),other_feature=col,n=int(g[['health',col]].dropna().shape[0]),spearman=g.health.corr(g[col],method='spearman')))
pd.DataFrame(cor).to_csv(O/'STATE_OVERLAP.csv',index=False)
qa=dict(firsts=len(z),stocks=len(src),known_health=int(z.health.notna().sum()),unknown_health=int(z.health.isna().sum()),fully_warmed=int(z.fully_warmed.sum()),max_native_close_error=float(z.native_close_error.max()),array_equivalence_stocks=len(checks),max_array_difference=max(x['max_array_reimplementation_diff']for x in checks),all_sources_unchanged=True,account_runs=0,native_signal_recomputations=0,new_universe_rankings=0,threshold_searches=0,elapsed_seconds=time.monotonic()-t0)
dump('ASSOCIATION_CHECKS.json',qa)
print(pd.DataFrame(stats).query("sample=='primary'")[['year','feature','included_closed','health_unknown','original_net_win_rate','AUC','role_market_stratified_AUC','spearman_round_return']].round(6).to_string(index=False));print(qa)
