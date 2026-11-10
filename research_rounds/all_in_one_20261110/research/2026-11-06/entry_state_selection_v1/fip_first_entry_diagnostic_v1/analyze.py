"""FIP fixed-window small diagnostic. No native model, account, ranking production or order calls."""
from pathlib import Path
import json, hashlib, math, time
import numpy as np, pandas as pd
O=Path(__file__).resolve().parent
R=O.parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
A=R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv'
END=pd.Timestamp('2026-05-15')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 if isinstance(v,np.integer):return int(v)
 if isinstance(v,np.bool_):return bool(v)
 if isinstance(v,pd.Timestamp):return str(v.date())
 return v
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2))
protocol=dict(status='SPECIFICATION_FIXED_BEFORE_NEW_COMPUTATION_NOT_UNTOUCHED_PREREGISTRATION',
 formula='r_j=log(C_j/C_j-1); PRET_n=exp(sum r)-1; F_n=sgn(PRET_n)*(Npos-Nneg)/n = -ID_n. n=20 primary,60 sensitivity. Zeros count in n. Require all n returns finite in same native segment.',
 long_interpretation='Compare only positive PRET_n for long-side FIP interpretation. Negative PRET left unchanged by any prospective consumer, not treated as desirable smooth downtrends.',
 concentration='J_n=max(max(r,0))/sum(max(r,0)); effective_positive_days=(sum r+)^2/sum(r+^2). Diagnostic only, no new combo fitting.',
 matching='Same exact signal date and fixed native sector, both PRET_n>0, abs(log1p(PRET_a)-log1p(PRET_b))<=0.02. Greedy ascending absolute gap then lexicographic IDs, no reuse within n/mode. Feature pair selection ignores outcomes; orient higher F vs lower F, drop equal F after matching with no replacement. Winner/loser pair mode is separately outcome-stratified description, not predictive validation.',
 outcomes='Native same-source adjusted close / (actual original first raw OPEN * native entry factor)-1 at fixed 20/60 common observations including entry close. Entire horizon finite and same segment; cutoff2026-05-15. Common dates from existing H1. No assumed fee for these price paths. Closed 0-to-0 original round_pnl includes actual original costs but remains original-path association.',
 scope='Only original PVR actual first entries, one per flat-to-flat campaign. Does not represent all legal buy pool or a new strategy, no accounts/orders/indicator reruns. Exact same-date pairs may be sparse; no widening after result.',
 frozen_windows=[20,60],log_return_caliper=.02,forward_horizons=[20,60],endpoint=str(END.date()),
 big60='fixed forward60 maximum close>=30% and terminal>=20%; diagnostic only.',
 major_periods={'2024_924_to_Oct31':['2024-09-24','2024-10-31'],'2025H2':['2025-07-01','2025-12-31'],'2026Q1':['2026-01-01','2026-03-31']},
 no_grid=True,no_account=True,no_new_gate=True,not_PIT=True)
save('PROTOCOL.json',protocol)
src={str(p):sha(p) for p in [M,H,A,Path(__file__)]}
manifest={x['symbol']:x for x in json.loads(M.read_text())}
x=pd.read_csv(A); x=x[x.account.eq('PVR')].copy().reset_index(drop=True)
assert len(x)==2693 and not x.duplicated(['sid','entry_day']).any()
common=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']); common=common[common<=END]
rows=[];prefix=[];identities=[]
def feat(f):
 r=np.log(f.close).diff().where(f.segment_id.eq(f.segment_id.shift()))
 z=pd.DataFrame(index=f.index)
 for n in [20,60]:
  same=f.segment_id.eq(f.segment_id.shift(n))
  lr=r.rolling(n,min_periods=n).sum().where(same)
  sign=np.sign(r)
  score=np.sign(lr)*sign.rolling(n,min_periods=n).sum()/n
  rp=r.clip(lower=0)
  ps=rp.rolling(n,min_periods=n).sum()
  z['logpret'+str(n)]=lr
  z['pret'+str(n)]=np.expm1(lr)
  z['F'+str(n)]=score.where(lr.notna())
  z['J'+str(n)]=(rp.rolling(n,min_periods=n).max()/ps).where(lr.notna()&ps.gt(0))
  z['Neff'+str(n)]=(ps**2/rp.pow(2).rolling(n,min_periods=n).sum()).where(lr.notna()&ps.gt(0))
  z['vol'+str(n)]=r.rolling(n,min_periods=n).std(ddof=0).where(lr.notna())
 return z
start=time.monotonic()
for no,(sid,g) in enumerate(x.groupby('sid',sort=True)):
 p=Path(manifest[sid]['refs']['facts']);src[str(p)]=sha(p)
 f=pd.read_parquet(p,columns=['close','segment_id','factor','raw_close','i_target','i_buy'])
 assert f.index.is_unique and f.index.is_monotonic_increasing
 z=feat(f)
 if no in [0,1,2,100,200,300]:
  for cut in ['2022-03-31','2024-09-24']:
   sub=f.loc[:cut]; zz=feat(sub);pd.testing.assert_frame_equal(zz,z.loc[zz.index],check_exact=True)
   prefix.append(dict(sid=sid,cutoff=cut,rows=len(sub),passed=True))
 ff=f.reindex(common)
 for d in g.to_dict('records'):
  t=pd.Timestamp(d['signal_day']);ent=pd.Timestamp(d['entry_day'])
  assert t<ent and t in f.index and ent in f.index
  d.update(z.loc[t].to_dict())
  er=abs(float(f.at[t,'close'])-float(d['original_close']))
  identities.append(er)
  assert er<1e-8,(sid,t,er)
  entry=float(d['first_raw_open'])*float(f.at[ent,'factor'])
  d['native_entry_open']=entry
  d['signal_day_return']=float(f.at[t,'close']/f.close.shift().at[t]-1)
  d['current_i_root']=str(f.index[(f.i_target.eq(1)&f.i_target.shift(fill_value=0).ne(1))&(f.index<=t)][-1].date()) if any((f.i_target.eq(1)&f.i_target.shift(fill_value=0).ne(1))&(f.index<=t)) else 'LEFT_CENSORED'
  pos=common.get_loc(ent)
  for h in [20,60]:
   q=ff.iloc[pos:pos+h]
   ok=len(q)==h and np.isfinite(q.close).all() and q.close.gt(0).all() and q.segment_id.eq(f.at[ent,'segment_id']).all()
   d['native_complete'+str(h)]=bool(ok)
   d['native_ret'+str(h)]=float(q.close.iloc[-1]/entry-1) if ok else np.nan
   d['native_mfe'+str(h)]=max(0,float(q.close.max()/entry-1)) if ok else np.nan
   d['native_mae'+str(h)]=min(0,float(q.close.min()/entry-1)) if ok else np.nan
  d['native_big60']=bool(d['native_complete60'] and d['native_mfe60']>=.3 and d['native_ret60']>=.2)
  rows.append(d)
 if (no+1)%200==0: print('stocks',no+1,'seconds',round(time.monotonic()-start,1),flush=True)
y=pd.DataFrame(rows).sort_values(['signal_day','sid']).reset_index(drop=True)
y['win']=y.round_pnl.gt(0)
y.to_csv(O/'FIRST_ENTRIES_WITH_FIP.csv',index=False)
pd.DataFrame(prefix).to_csv(O/'PREFIX_CHECKS.csv',index=False)
def metric(g):
 c=g[g.closed]
 d=dict(N=len(g),stocks=g.sid.nunique(),dates=g.signal_day.nunique(),closed=len(c),wins=int(c.win.sum()),original_closed_winrate=float(c.win.mean()) if len(c) else None,original_round_pnl_sum=float(c.round_pnl.sum()),big60=int(g.native_big60.sum()))
 for h in [20,60]:
  k=g[g['native_complete'+str(h)]]
  d.update({f'n{h}':len(k),f'mean_ret{h}':float(k['native_ret'+str(h)].mean()),f'positive_ret{h}':float(k['native_ret'+str(h)].gt(0).mean()),f'mean_mfe{h}':float(k['native_mfe'+str(h)].mean()),f'mean_mae{h}':float(k['native_mae'+str(h)].mean())})
 return d
groups=[]
for n in [20,60]:
 y['long'+str(n)]=y['pret'+str(n)].gt(0)&y['F'+str(n)].notna()
 for yr,g in y.groupby('year'):
  groups.append(dict(n=n,year=yr,group='ALL',**metric(g)))
  for label,mask in [('positive_pret',g['long'+str(n)]),('nonpositive_pret',g['pret'+str(n)].le(0)),('unknown',g['F'+str(n)].isna()),('positive_pret_more_positive_days',g['long'+str(n)]&g['F'+str(n)].gt(0)),('positive_pret_not_more_positive_days',g['long'+str(n)]&g['F'+str(n)].le(0))]:
   groups.append(dict(n=n,year=yr,group=label,**metric(g[mask])))
pd.DataFrame(groups).to_csv(O/'ANNUAL_DESCRIPTIVE.csv',index=False)
pairs=[]
for n in [20,60]:
 eligible=y[y['long'+str(n)]]
 for mode in ['feature_blind','winner_loser_descriptive']:
  pool=eligible if mode=='feature_blind' else eligible[eligible.closed]
  for (date,sec),g in pool.groupby(['signal_day','sector'],sort=True):
   idx=list(g.index);edges=[]
   for j,a in enumerate(idx):
    for b in idx[j+1:]:
     gap=abs(y.at[a,'logpret'+str(n)]-y.at[b,'logpret'+str(n)])
     if gap>.02+1e-12:continue
     if mode=='winner_loser_descriptive' and y.at[a,'win']==y.at[b,'win']:continue
     edges.append((gap,y.at[a,'sid'],y.at[b,'sid'],a,b))
   used=set()
   for gap,sa,sb,a,b in sorted(edges):
    if a in used or b in used:continue
    used|={a,b}
    if mode=='feature_blind':
     if y.at[a,'F'+str(n)]==y.at[b,'F'+str(n)]:continue
     if y.at[a,'F'+str(n)]<y.at[b,'F'+str(n)]:a,b=b,a
    elif not y.at[a,'win']:a,b=b,a
    aa=y.loc[a];bb=y.loc[b]
    rr=dict(n=n,mode=mode,signal_day=date,year=int(aa.year),sector=sec,a_sid=aa.sid,b_sid=bb.sid,a_root=aa.current_i_root,b_root=bb.current_i_root,pret_gap=gap,
      Fdiff=aa['F'+str(n)]-bb['F'+str(n)],Jdiff=aa['J'+str(n)]-bb['J'+str(n)],pvr_gap=aa.PVR_decision-bb.PVR_decision,
      both_closed=bool(aa.closed and bb.closed),a_win=bool(aa.win) if aa.closed else None,b_win=bool(bb.win) if bb.closed else None,
      a_pnl=aa.round_pnl if aa.closed else np.nan,b_pnl=bb.round_pnl if bb.closed else np.nan,a_F=aa['F'+str(n)],b_F=bb['F'+str(n)])
    for h in [20,60]:
     good=bool(aa['native_complete'+str(h)] and bb['native_complete'+str(h)])
     rr['both_complete'+str(h)]=good
     for key in ['ret','mfe','mae']:
      rr['a_'+key+str(h)]=aa['native_'+key+str(h)] if good else np.nan
      rr['b_'+key+str(h)]=bb['native_'+key+str(h)] if good else np.nan
      rr['diff_'+key+str(h)]=rr['a_'+key+str(h)]-rr['b_'+key+str(h)]
    rr['a_big60']=aa.native_big60;rr['b_big60']=bb.native_big60
    pairs.append(rr)
p=pd.DataFrame(pairs);p.to_csv(O/'MATCHED_PAIRS.csv',index=False)
stats=[]
rng=np.random.default_rng(20261106)
for (n,mode),allg in p.groupby(['n','mode']):
 for yr,g in [('ALL',allg)]+list(allg.groupby('year')):
  c=g[g.both_closed]
  d=dict(n=n,mode=mode,year=yr,pairs=len(g),dates=g.signal_day.nunique(),stocks=len(set(g.a_sid)|set(g.b_sid)),mean_abs_pret_gap=g.pret_gap.mean(),mean_pvr_gap=g.pvr_gap.mean(),Fdiff_mean=g.Fdiff.mean(),winner_F_higher_fraction=g.Fdiff.gt(0).mean(),winner_F_tie_fraction=g.Fdiff.eq(0).mean(),both_closed=len(c),a_closed_winrate=c.a_win.mean(),b_closed_winrate=c.b_win.mean(),a_big60=int(g.a_big60.sum()),b_big60=int(g.b_big60.sum()))
  for h in [20,60]:
   q=g[g['both_complete'+str(h)]]
   d['complete_pairs'+str(h)]=len(q)
   for k in ['ret','mfe','mae']:d['diff_'+k+str(h)]=q['diff_'+k+str(h)].mean()
   if len(q):
    q=q.copy();q['month']=q.signal_day.str[:7]
    blocks=q.groupby('month')['diff_ret'+str(h)].agg(['sum','count'])
    draw=rng.integers(0,len(blocks),size=(2000,len(blocks)))
    boot=blocks['sum'].to_numpy()[draw].sum(1)/blocks['count'].to_numpy()[draw].sum(1)
    d['ret'+str(h)+'_month_boot_lo'],d['ret'+str(h)+'_month_boot_hi']=np.quantile(boot,[.025,.975])
  stats.append(d)
pd.DataFrame(stats).to_csv(O/'MATCHED_SUMMARY.csv',index=False)
tail=[]
for n in [20,60]:
 for name,lo,hi in [('ALL','2022-01-01','2026-05-15')]+[(k,*v) for k,v in protocol['major_periods'].items()]:
  g=y[y.signal_day.between(lo,hi)]
  b=g[g.native_big60]
  pos=b[b['long'+str(n)]]
  tail.append(dict(n=n,period=name,N=len(g),big60=len(b),big60_positive_pret=len(pos),big60_nonpositive_pret=int(b['pret'+str(n)].le(0).sum()),big60_unknown=int(b['F'+str(n)].isna().sum()),big60_F_nonpositive=int((pos['F'+str(n)]<=0).sum()),big60_F_median=pos['F'+str(n)].median(),big60_J_median=pos['J'+str(n)].median()))
pd.DataFrame(tail).to_csv(O/'MAJOR_PERIOD_RIGHT_TAIL.csv',index=False)
cases=y[y.sid.isin(['600056.SH','002317.SZ','000620.SZ','002911.SZ','300085.SZ','002583.SZ','000506.SZ'])]
cases[['sid','signal_day','entry_day','year','round_pnl','closed','pret20','F20','J20','Neff20','pret60','F60','J60','native_ret20','native_ret60','native_big60']].to_csv(O/'FIXED_CASE_NAMES_ALL_ROUNDS.csv',index=False)
corr=y[['F20','F60','PVR_decision','pvr_eff21','J20','J60','vol20','vol60']].corr(method='spearman');corr.to_csv(O/'SPEARMAN_OVERLAP.csv')
save('SOURCE_SHA256.json',src)
save('COMPLETION.json',dict(status='SMALL_FIRST_ENTRY_DIAGNOSTIC_COMPLETED_NO_STRATEGY_PROMOTION',N=len(y),stocks=y.sid.nunique(),max_native_original_close_error=max(identities),prefix_checks=len(prefix),sources=len(src),source_hashes_unchanged=all(sha(p)==v for p,v in src.items()),windows=[20,60],account_runs=0,original_model_runs=0,parameter_scans=0,common_endpoint=END,duplicate_stock_signal_days=int(y.duplicated(['sid','signal_day']).sum()),repeated_I_roots=int(y.duplicated(['sid','current_i_root']).sum()),elapsed_seconds=time.monotonic()-start))
print('COMPLETION', (O/'COMPLETION.json').read_text())
print('MATCHED',pd.DataFrame(stats).to_string(index=False))
print('TAIL',pd.DataFrame(tail).to_string(index=False))
print('CORR',corr.to_string())

