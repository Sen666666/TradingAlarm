"""Fixed current-roster semiconductor H1 signal study. No accounts, fitting or orders."""
import sys, json, time, importlib.util, hashlib, math
from pathlib import Path
import numpy as np, pandas as pd
O=Path(__file__).resolve().parent; R=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
MONEY=Path('/Users/bytedance/Documents/ChatGPT/money')
P=Path(json.load(open(MONEY/'TradingAlarm/runtime/market/current.json'))['path'])
U=W/'universe-cp1-inputs-20261031'
END='2026-06-30'; CUT='2026-05-15'; START='2026-01-01'; BASE='2025-12-31'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); sys.modules[n]=m;s.loader.exec_module(m);return m
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(x):
 if isinstance(x,dict):return {str(k):norm(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [norm(v) for v in x]
 if isinstance(x,np.generic):return norm(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 return x
def save(n,x):(O/n).write_text(json.dumps(norm(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def exact(a,b):
 a=a.copy(deep=False);b=b.copy(deep=False)
 if isinstance(a.index,pd.DatetimeIndex):a.index=a.index.as_unit('ns');b.index=b.index.as_unit('ns')
 pd.testing.assert_frame_equal(a,b,check_exact=True,check_dtype=False,check_freq=False)
G=load('semi_gen',W/'case-stock-cp1-warmup-20261031/generate.py')
D=load('semi_dual',R/'dual_frontier_cp_full_v1/replay_signals.py')
F=load('semi_factors',R/'account_comparison_continuous_v1/factors/continuous_factors.py')
T=load('semi_trace',W/'cp1-evidence-trace-20261031/trace.py')
S=load('semi_stage',W/'industry-mobile-stage-20261031/stage.py')
rosterpath=MONEY/'research_rounds/tech-compound-design-20261026/proposed-pool.csv'
roster=pd.read_csv(rosterpath); pool=roster[roster.sector_id.eq('URFI881121')].sort_values('symbol')
ids=pool.symbol.tolist();names=dict(zip(pool.symbol,pool.name));assert len(ids)==126 and len(set(ids))==126
sm={x['symbol']:x for x in json.load(open(U/'STOCK_MANIFEST.json'))}; pm={x['series_id']:x for x in json.load(open(P/'manifest.json'))['series']}
source_paths=[Path(__file__),rosterpath,U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',P/'manifest.json',Path(G.__file__),Path(G.N.__file__),Path(G.M.__file__),Path(D.__file__),Path(F.__file__),Path(T.__file__),Path(S.__file__)]
hashes={str(p):sha(p) for p in source_paths}
save('PROTOCOL.json',dict(frozen_before_this_run=True,universe='All 126 members of current local TradingAlarm roster, sector URFI881121; fixed before results; NOT point-in-time membership',ids=ids,window=[BASE,END],old_account_cutoff=CUT,cost='3 engineering samples 0.28-0.42 seconds each. Budget 300 seconds signal audit, one worker; no accounts or network or installation.',signal='Original full warm history E0/I derived by native source, original CP model unchanged, plus existing frozen dual-frontier formula. Full H1 old CP/facts exact to stored canonical; prefix at 2025-12-31 and 2026-05-15. Current source all common semantic fields exact to old source. Factor recomputed using only effective actions and strict prior raw closes through 6/30.',labels='Descriptive close returns, not executions. Established stocks last observation <=12/31 to last <=6/30 with exact observation dates and stale flags. Separate exact-endpoint subset. All H1 entrants and no-H1 stocks disclosed. Root comparisons use all I roots intersecting H1; first old/new CP in root, never cherry-picked winner roots. Next-observed-open path labels 20 observations only when complete in H1, not executable returns.',no_account_run=True,no_parameter_search=True,limitations=['Current-survivor/member and concept mapping not PIT','Corporate-action terms assumed preknown; announcement availability not verified','Observed dates do not verify suspensions or reachable limit-up fills','No real positions, trades, allocations or account returns inferred','Cached sources are local data, not independently exchange-validated'],initial_hashes=hashes))
pool.to_csv(O/'FIXED_ROSTER.csv',index=False)
t0=time.monotonic();audits=[];all_daily=[];roots=[];coverage=[];prices=[]
semrec=next(x for x in json.load(open(U/'INDUSTRY_MANIFEST.json')) if x['series']=='URFI881121')
sf=pd.read_parquet(semrec['refs']['CP1_input']);sz=G.M.calculate(sf);exact(sz,pd.read_parquet(semrec['refs']['CP1']))
T.BEGIN='1900-01-01';T.END=END
sff,sev,sep,_=T.source_frame('URFI881121',G.N.RECORDS);exact(sf,sff)
srr,_,_=T.trace('URFI881121',sf,sz,sev,sep);ss=pd.DataFrame(S.run('URFI881121',sf,sz,{r['confirmed_day']:r['receipt_id'] for r in srr}));exact(ss,pd.read_parquet(semrec['refs']['state']))
for cut in [BASE,CUT]:
 exact(G.M.calculate(sf.loc[:cut]),sz.loc[:cut]);exact(pd.DataFrame(S.run('URFI881121',sf.loc[:cut],sz.loc[:cut],{r['confirmed_day']:r['receipt_id'] for r in srr if r['confirmed_day']<=cut})),ss[ss.day.le(cut)].reset_index(drop=True))
prsec=pd.read_parquet(P/'signals/URFI881121.parquet').loc[:END]
np.testing.assert_equal(prsec.loc[sf.index,'close'].to_numpy(),sf.close.to_numpy())
ss['old_CP_receipt']=sz.receipt.to_numpy();ss['CP_scale']=sz.scale.to_numpy();ss['CP_displacement']=sz.displacement.to_numpy();ss['CP_credit']=sz.credit.to_numpy();ss['threshold']=sz.scale.to_numpy()*math.sqrt(5)
ss[ss.day.ge('2025-12-01')].to_csv(O/'SECTOR_DAILY.csv',index=False)
secmap=ss.set_index('day')
for n,sid in enumerate(ids):
 r=sm[sid];rawsig=pd.read_parquet(P/'signals'/(sid+'.parquet'));pr=rawsig.loc[:END];hist=pr.loc[START:END]
 h=dict(sid=sid,name=names[sid],first_source=str(rawsig.index.min().date()),last_H1=str(pr.index.max().date()) if len(pr) else None,H1_rows=len(hist),exact_base=BASE in pr.index,exact_end=END in pr.index,baseline_available=bool(len(pr.loc[:BASE])),listed_or_source_starts_in_H1=bool(len(pr) and pr.index.min()>pd.Timestamp(BASE)))
 coverage.append(h)
 for p in [P/'signals'/(sid+'.parquet'),P/'facts'/(sid+'.parquet'),Path(r['refs']['CP1_input']),Path(r['refs']['CP1']),Path(r['refs']['facts'])]:hashes[str(p)]=sha(p)
 if pr.empty:
  audits.append(dict(sid=sid,status='NO_H1_OBSERVATIONS'));continue
 f,_=G.N.derive(sid,END);exact(f,pd.read_parquet(r['refs']['facts']).loc[:END]);exact(f,pd.read_parquet(P/'facts'/(sid+'.parquet')).loc[:END])
 q=G.frame(sid,f,END);exact(q,pd.read_parquet(r['refs']['CP1_input']).loc[:END]);z=G.M.calculate(q);exact(z,pd.read_parquet(r['refs']['CP1']).loc[:END]);pr=pr.reindex(q.index)
 oldpath=next(p for p in r['source_sha256'] if p.endswith('/signal.parquet'));oldpr=pd.read_parquet(oldpath).loc[:END].reindex(q.index)
 cols=['open','high','low','close','raw_open','raw_high','raw_low','raw_close','raw_volume','amount','adjustment_factor','volume_factor','segment_id','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']
 exact(pr[cols],oldpr[cols]);hashes[oldpath]=sha(oldpath)
 rec=pm[sid];raw=pd.read_parquet(rec['raw']['path']);ap=rec['adjustment']['actions']['path'];hashes[ap]=sha(ap);events=json.load(open(ap))['events'];ft=F.OpenFactorTimeline(raw,events,method=rec['adjustment']['method'],end=END);fv=ft.at_dates(pr.index)
 np.testing.assert_allclose(fv.to_numpy(),pr.adjustment_factor.to_numpy(),rtol=0,atol=0)
 dual=D.calc(q,pr,True);base=D.calc(q,pr,False)
 assert base.receipt.equals(z.receipt)
 for c in ['anchor','scale','credit','displacement','delta_frontier','candidate','next_anchor']:np.testing.assert_allclose(base[c],z[c],rtol=0,atol=1e-12,equal_nan=True)
 for cut in [BASE,CUT]:
  if q.loc[:cut].empty:continue
  fq,_=G.N.derive(sid,cut);exact(fq,f.loc[:cut]);exact(G.M.calculate(q.loc[:cut]),z.loc[:cut]);exact(D.calc(q.loc[:cut],pr.loc[:cut],True),dual.loc[:cut])
 cache=R/'dual_frontier_cp_full_v1/states'/(sid+'.parquet')
 if cache.exists():
  prev=pd.read_parquet(cache);prev=prev.set_index(pd.DatetimeIndex(prev.day));prev=prev.loc[START:CUT]
  if len(prev):
   for a,b in [('old_receipt',z.receipt),('new_receipt',dual.receipt),('qok',dual.qok)]:np.testing.assert_equal(prev[a].to_numpy(),b.loc[prev.index].to_numpy())
   for a,b in [('new_anchor',dual.anchor),('new_scale',dual.scale),('new_credit',dual.credit),('new_mean_frontier',dual.mean_frontier)]:np.testing.assert_allclose(prev[a],b.loc[prev.index],rtol=0,atol=0,equal_nan=True)
 active=f.i_target.astype(bool);birth=active&(~active.shift(fill_value=False)|f.segment_id.ne(f.segment_id.shift()))
 rd=pd.Series(pd.NaT,index=f.index);rd.loc[birth]=f.index[birth];rd=rd.ffill().where(active)
 d=f.copy();d['sid']=sid;d['name']=names[sid];d['day']=d.index.strftime('%Y-%m-%d');d['I_root']=rd.dt.strftime('%Y-%m-%d');d['I_birth']=birth;d['native_down']=q.e0_down;d['old_receipt']=z.receipt;d['new_receipt']=dual.receipt;d['old_ready']=z.ready;d['new_ready']=dual.ready;d['qok']=dual.qok
 for c in ['scale','credit','displacement','delta_frontier']:d['old_'+c]=z[c]
 d['old_threshold']=z.scale*math.sqrt(5);d['new_credit']=dual.credit;d['new_threshold']=dual.scale*math.sqrt(5)
 for c in ['raw_open','raw_close','raw_high','raw_low','amount','raw_volume']:d[c]=pr[c]
 d['sector_E0']=d.day.map(secmap.E0_valid);d['sector_stage']=d.day.map(secmap.stage);d['sector_authorization']=d.day.map(secmap.authorization_usable)
 d['original_CP_with_sector_authorization']=d.old_receipt&d.sector_authorization.fillna(False)
 all_daily.append(d.loc[START:END].reset_index(drop=True))
 for root,g in d[d.I_root.notna()].groupby('I_root',sort=False):
  if g.index[-1]<pd.Timestamp(START):continue
  row=dict(sid=sid,name=names[sid],I_root=root,root_start=g.day.iloc[0],root_end=g.day.iloc[-1],left_truncated_H1=root<START,open_at_H1_end=g.index[-1]==f.index[-1] and bool(active.iloc[-1]),root_observations=len(g),root_end_from_start=float(g.close.iloc[-1]/g.close.iloc[0]-1),root_peak_from_start=float(g.close.max()/g.close.iloc[0]-1))
  for k in ['old','new']:
   e=g[g[k+'_receipt']];row[k+'_first']=e.day.iloc[0] if len(e) else None;row[k+'_count']=len(e);row[k+'_lag']=g.index.get_loc(e.index[0]) if len(e) else None;row[k+'_move_already']=float(e.close.iloc[0]/g.close.iloc[0]-1) if len(e) else None
   row[k+'_first_sector_authorized']=bool(e.sector_authorization.iloc[0]) if len(e) else None
   if len(e):
    forward=pr.loc[pr.index>e.index[0]].iloc[:20]
    row[k+'_complete20']=len(forward)==20
    if len(forward)==20:
     op=float(forward.raw_open.iloc[0]*forward.adjustment_factor.iloc[0]);row[k+'_ret20']=float(forward.close.iloc[-1]/op-1);row[k+'_mfe20']=float(forward.close.max()/op-1);row[k+'_mae20']=float(forward.close.min()/op-1)
  roots.append(row)
 last=pr.iloc[-1];basepr=pr.loc[:BASE];mid=pr.loc[:CUT]
 px=dict(sid=sid,name=names[sid],first_source=h['first_source'],H1_rows=len(hist),base_day=str(basepr.index[-1].date()) if len(basepr) else None,end_day=str(pr.index[-1].date()),exact_base=h['exact_base'],exact_end=h['exact_end'],base_close=float(basepr.close.iloc[-1]) if len(basepr) else None,end_close=float(last.close),end_raw_close=float(last.raw_close),end_factor=float(last.adjustment_factor),mid_day=str(mid.index[-1].date()) if len(mid) else None,mid_close=float(mid.close.iloc[-1]) if len(mid) else None)
 if len(basepr):px.update(H1_return=float(last.close/basepr.close.iloc[-1]-1),through_May15=float(mid.close.iloc[-1]/basepr.close.iloc[-1]-1),after_May15=float(last.close/mid.close.iloc[-1]-1),H1_peak=float(hist.close.max()/basepr.close.iloc[-1]-1),H1_trough=float(hist.close.min()/basepr.close.iloc[-1]-1))
 else:px['since_first_H1_observation']=float(last.close/pr.close.iloc[0]-1)
 prices.append(px)
 audits.append(dict(sid=sid,status='PASS',observations=len(q),native_E0_I_exact=True,CP_all_fields_exact=True,current_old_source_exact=True,causal_factor_exact=True,physical_prefixes_exact=True,dual_old_cache_exact=True,H1_cp_ready=int(z.loc[START:END].ready.sum()),H1_old_receipts=int(z.loc[START:END].receipt.sum()),H1_dual_receipts=int(dual.loc[START:END].receipt.sum()),H1_q_unknown=int((~dual.loc[START:END].qok).sum())))
 if (n+1)%20==0:print('AUDIT',n+1,round(time.monotonic()-t0,2),flush=True)
 if time.monotonic()-t0>300:raise TimeoutError('300 second compute budget reached')
# Only publish final data after every exact audit passed.
c=pd.DataFrame(coverage);a=pd.DataFrame(audits);d=pd.concat(all_daily,ignore_index=True);rr=pd.DataFrame(roots);px=pd.DataFrame(prices)
for name,v in [('COVERAGE.csv',c),('EXACT_AUDITS.csv',a),('ALL_STOCK_PRICE_PATHS.csv',px),('ALL_I_ROOTS.csv',rr)]:v.to_csv(O/name,index=False)
d.to_parquet(O/'ALL_STOCK_DAILY.parquet',index=False)
px=px.merge(d.groupby('sid').agg(H1_I_days=('i_target','sum'),H1_I_buys=('i_buy','sum'),H1_CP=('old_receipt','sum'),H1_dual_CP=('new_receipt','sum'),CP_sector_authorized=('original_CP_with_sector_authorization','sum')),on='sid')
px.to_csv(O/'ALL_STOCK_PRICE_AND_SIGNAL_SUMMARY.csv',index=False)
counts=d.groupby('day').agg(observed=('sid','count'),E0=('e0_target','sum'),I=('i_target','sum'),I_buys=('i_buy','sum'),old_CP=('old_receipt','sum'),new_CP=('new_receipt','sum'),authorized_CP=('original_CP_with_sector_authorization','sum'))
counts.to_csv(O/'DAILY_BREADTH.csv')
def dist(x):
 x=x.dropna();return dict(n=len(x),positive=int((x>0).sum()),over50pct=int((x>=.5).sum()),over100pct=int((x>=1).sum()),min=x.min(),p10=x.quantile(.1),p25=x.quantile(.25),median=x.median(),p75=x.quantile(.75),p90=x.quantile(.9),max=x.max(),mean=x.mean())
summary=dict(status='COMPLETE_EXACT_SIGNAL_STUDY_NO_ACCOUNT',seconds=time.monotonic()-t0,universe=126,H1_observed=int(c.H1_rows.gt(0).sum()),no_H1=c[c.H1_rows.eq(0)][['sid','name','first_source']].to_dict('records'),new_H1=c[c.listed_or_source_starts_in_H1][['sid','name','first_source','H1_rows']].to_dict('records'),exact_endpoint=int((c.exact_base&c.exact_end).sum()),established_with_stale_dates=int(c.baseline_available.sum()),H1_all_established=dist(px.H1_return),H1_exact_endpoints=dist(px.loc[px.exact_base&px.exact_end,'H1_return']),after_May15_established=dist(px.after_May15),sector=dict(H1=float(sf.loc[END,'close']/sf.loc[BASE,'close']-1),through_May15=float(sf.loc[CUT,'close']/sf.loc[BASE,'close']-1),after_May15=float(sf.loc[END,'close']/sf.loc[CUT,'close']-1),state_full_and_prefix_exact=True),signal_counts=dict(old=int(d.old_receipt.sum()),new=int(d.new_receipt.sum()),both=int((d.old_receipt&d.new_receipt).sum()),old_only=int((d.old_receipt&~d.new_receipt).sum()),new_only=int((~d.old_receipt&d.new_receipt).sum())),sources_unchanged=all(sha(p)==v for p,v in hashes.items()),source_hashes=len(hashes))
assert summary['sources_unchanged'];save('SOURCE_HASHES.json',hashes);save('SUMMARY.json',summary);save('OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'});print(json.dumps(norm(summary),ensure_ascii=False,indent=2),flush=True)
