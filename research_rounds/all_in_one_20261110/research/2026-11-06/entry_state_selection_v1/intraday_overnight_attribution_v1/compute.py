"""Single no-fit timing attribution diagnostic. Original sources and states untouched."""
from pathlib import Path
import sys,json,hashlib,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;B=R/'selection_entry_diagnosis_v1'
S=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design')
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
sys.path.insert(0,str(S));from features import original_pvr,original_observation_clock
W=.9**np.arange(20,-1,-1);W/=W.sum()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def qs(x):return pd.Series(x).dropna().quantile([0,.001,.01,.05,.5,.95,.99,.999,1]).to_dict()
protocol=dict(status='FORMULA_FROZEN_BEFORE_THIS_COMPUTATION_ALREADY_SEEN_HISTORY_NOT_OOS',hypothesis='Literature-inspired timing attribution only, not literature-validated strategy or estimated capital flow',r='log(C_t)-log(C_prev) on exact original PVR block',s='max(1e-8,1.4826*median(abs(previous63 r)))',a_ref='median(previous21 positive amount)',u='tanh(r/s)',b='tanh(log(A/a_ref))',m='1+0.5*abs(u)*b',n='log(O_t)-log(C_prev)',d='log(C_t)-log(O_t)',k='tanh(r/s)/(r/s)/s, continuous value 1/s at r=0; no clipping',e_original='m*u',e_star='e_original+k*(m_prev-m)*n; equals k*(m*d+m_prev*n)',aggregation='Original normalized21 weights .9^k, score=50+50*tanh(2E)',clock='Original positive finite close/amount and optional masks; invalid/source change resets. Previous means previous original valid observation within same original block, not silently previous exchange date. No artificial new calendar clock.',unknown='Need finite positive current open, original e, previous same-block m and21 complete candidate contributions. Otherwise unknown score keeps original queue slot. No forward-fill or changed E0/I/CP/readiness.',knowledge='All A_t,C_t,u_t,k_t,m_t known only after signal-day close. m_prev historical; kernel is not known at current open.',numerical='r=0 can produce nonzero e_star. Tiny-r finite continuous scale, not division explosion from r. Scale floor may permit large contributions. No winsorization, no rescue coefficients.',evaluation='Original PVR account legal empty MOBILE candidate dates, original queue order. K=min(20,N); candidate score descending, original priority then sid ties; unknown original slots fixed. Reuse frozen same date native next-open price labels. Old actual complete round associations only, never call them new strategy returns.',periods=['2022','2023','2024','2025','2026 through2026-05-15','2024-09-24..2024-10-31','2026-01-01..2026-03-31'],costs='40bp/100bp constant price-path sensitivity, not realized fees or turnover',account_runs=0,parameter_searches=0,fitting=0,source_files_unchanged=True)
save('PROTOCOL.json',protocol)
manifest={x['symbol']:x for x in json.loads(M.read_text())}
queue=pd.read_parquet(B/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');queue=queue[queue.account.eq('PVR')].copy()
firstkeys=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv',usecols=['account','sid','signal_day']);firstkeys=firstkeys[firstkeys.account.eq('PVR')]
sids=sorted(set(queue.sid)|set(firstkeys.sid))
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);cal=cal[cal<='2026-05-15'];calmap={d:i for i,d in enumerate(cal)}
source={str(p):sha(p) for p in [M,H,S/'features.py',Path(__file__),B/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',B/'ALL_FIRST_ENTRIES.csv']}
def compute(f):
 z=original_pvr(f);valid,block=original_observation_clock(f);z['m']=1+.5*z.u.abs()*z.b
 z['prev_m']=z.m.shift().where(block.eq(block.shift()))
 previous=f.close.shift().where(block.eq(block.shift()))
 openok=f.open.gt(0)&np.isfinite(f.open)
 z['n']=(np.log(f.open.where(openok))-np.log(previous));z['d']=np.log(f.close)-np.log(f.open.where(openok))
 x=(z.r/z.scale).to_numpy();ratio=np.divide(np.tanh(x),x,out=np.ones_like(x),where=x!=0)
 z['k']=ratio/z.scale;z['delta']=z.k*(z.prev_m-z.m)*z.n;z['star_e']=z.e+z.delta
 z['direct_e']=z.k*(z.m*z.d+z.prev_m*z.n)
 z['star_E']=np.nan;z['delta_E']=np.nan;z['direct_E']=np.nan
 for _,g in z[valid].groupby(block[valid],sort=False):
  for c,out in [('star_e','star_E'),('delta','delta_E'),('direct_e','direct_E')]:
   z.loc[g.index,out]=g[c].rolling(21,min_periods=21).apply(lambda a:np.dot(W,a),raw=True)
 z['star_score']=50+50*np.tanh(2*z.star_E);z['score_delta']=z.star_score-z.score
 z['block']=block;z['valid']=valid;z['open']=f.open;z['close']=f.close;z['amount']=f.amount
 z['factor']=f.adjustment_factor if 'adjustment_factor' in f else np.nan
 z['factor_change']=np.log(z.factor/z.factor.shift()).where(block.eq(block.shift()))
 z['common_t']=[calmap.get(x,np.nan) for x in f.index]
 z['observation_gap']=(z.common_t.diff()>1)&block.eq(block.shift())
 z['open_missing_21']=((~openok)&valid).astype(int).rolling(21,min_periods=21).sum()
 return z
parts=[];aud=[];extremes=[];prefix=[];firstparts=[];scalarparts=[]
start=time.monotonic()
for no,sid in enumerate(sids):
 m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));f=pd.read_parquet(p).loc[:'2026-05-15'];native=pd.read_parquet(m['refs']['facts']).reindex(f.index)
 source[p]=sha(p);source[m['refs']['facts']]=sha(m['refs']['facts']);a=compute(f)
 known=a.e.notna();new=a.star_e.notna();fc=f.close.notna()&native.close.notna()
 closeerr=float((f.close[fc]-native.close[fc]).abs().max());assert closeerr<1e-7,(sid,closeerr)
 factorerr=float((f.adjustment_factor-native.factor).abs().max());assert factorerr<1e-8,(sid,factorerr)
 openerr=float((f.open-f.raw_open*f.adjustment_factor).abs().max());closecoord=float((f.close-f.raw_close*f.adjustment_factor).abs().max());assert max(openerr,closecoord)<1e-7
 eq=float((a.star_e-a.direct_e).abs().max());eqs=float(((50+50*np.tanh(2*a.direct_E))-a.star_score).abs().max())
 assert eqs<1e-8,(sid,eq,eqs)
 assert np.allclose(a.E+a.delta_E,a.star_E,rtol=2e-14,atol=1e-12,equal_nan=True),(sid,float((a.E+a.delta_E-a.star_E).abs().max()))
 # Source break never inherits an m, even if preceding e happened to be known.
 vb=a.block.ne(a.block.shift());assert a.loc[vb,'prev_m'].isna().all()
 z=a[a.index>='2022-01-01'].copy();z['sid']=sid;z['day']=z.index.strftime('%Y-%m-%d')
 wanted=set(queue.loc[queue.sid.eq(sid),'day'])|set(firstkeys.loc[firstkeys.sid.eq(sid),'signal_day'])
 parts.append(z[z.day.isin(wanted)])
 scalarparts.append(z[['r','scale','n','e','star_e','delta','score_delta','factor_change','observation_gap']].copy())
 x=z[z.star_e.notna()].nlargest(3,'star_e');y=z[z.star_e.notna()].nsmallest(3,'star_e');v=z.loc[z.delta.abs().nlargest(3).index];extremes.append(pd.concat([x,y,v]).drop_duplicates(['sid','day']))
 if sid in ['600056.SH','300182.SZ','002385.SZ','600606.SH','688582.SH','300666.SZ','301611.SZ','688603.SH']:
  z.to_csv(O/(sid+'_DAILY.csv'),index=False)
  for cut in ['2022-03-31','2024-09-24','2026-01-15']:
   aa=compute(f.loc[:cut]);cols=['r','m','prev_m','k','delta','star_e','star_E','star_score'];pd.testing.assert_frame_equal(a.loc[aa.index,cols],aa[cols],check_exact=True)
   prefix.append(dict(sid=sid,cut=cut,rows=len(aa),max_error=0))
 aud.append(dict(sid=sid,observations=len(a),original_e=int(known.sum()),candidate_e=int(new.sum()),original_scores=int(a.score.notna().sum()),candidate_scores=int(a.star_score.notna().sum()),max_close_error=closeerr,max_factor_error=factorerr,max_open_coordinate_error=openerr,max_close_coordinate_error=closecoord,max_aggregation_equivalence_error=float((a.E+a.delta_E-a.star_E).abs().max()),max_daily_equivalence_error=eq,max_score_equivalence_error=eqs,zero_r=int((a.r.eq(0)&new).sum()),zero_r_nonzero_star=int((a.r.eq(0)&new&a.star_e.ne(0)).sum()),scale_floor=int((a.scale.eq(1e-8)&new).sum()),daily_abs_gt1_5=int((a.star_e.abs()>1.5).sum()),factor_change_days=int((a.factor_change.abs()>1e-12).sum()),gaps_original_clock=int(a.observation_gap.sum())))
 if (no+1)%200==0:print('STOCKS',no+1,'SECONDS',round(time.monotonic()-start,1),flush=True)
out=pd.concat(parts,ignore_index=True);out.to_parquet(O/'SCORES.parquet',index=False);pd.DataFrame(aud).to_csv(O/'SOURCE_AUDIT.csv',index=False);pd.concat(extremes,ignore_index=True).to_csv(O/'DAILY_EXTREMES.csv',index=False);pd.DataFrame(prefix).to_csv(O/'PREFIX_TESTS.csv',index=False)
s=pd.concat(scalarparts,ignore_index=True);kn=s.star_e.notna();sc=queue.merge(out,on=['sid','day'],how='left',validate='one_to_one');fc=firstkeys.merge(out,left_on=['sid','signal_day'],right_on=['sid','day'],how='left',validate='many_to_one')
assert (sc.original_PVR-sc.score).abs().max()<1e-8
sc.to_parquet(O/'CANDIDATE_SCORES.parquet',index=False);fc.to_parquet(O/'FIRST_ENTRY_SCORES.parquet',index=False)
summary=dict(stocks=len(sids),candidate_rows=len(sc),candidate_known=int(sc.star_score.notna().sum()),candidate_unknown=int(sc.star_score.isna().sum()),actual_first_rows=len(fc),actual_first_known=int(fc.star_score.notna().sum()),original_PVR_error=float((sc.original_PVR-sc.score).abs().max()),candidate_score_change_quantiles=qs(sc.score_delta),absolute_candidate_score_change_quantiles=qs(sc.score_delta.abs()),all_2022_onward_observations=len(s),candidate_daily_known=int(kn.sum()),daily_star_quantiles=qs(s.star_e),daily_delta_quantiles=qs(s.delta),daily_absolute_delta_quantiles=qs(s.delta.abs()),daily_abs_star_gt1_5=int(s.star_e.abs().gt(1.5).sum()),daily_abs_star_gt3=int(s.star_e.abs().gt(3).sum()),scale_quantiles=qs(s.loc[kn,'scale']),zero_r=int((s.r.eq(0)&kn).sum()),zero_r_nonzero=int((s.r.eq(0)&kn&s.star_e.ne(0)).sum()),scale_floor_days=int((s.scale.eq(1e-8)&kn).sum()),prefix_checks=len(prefix),all_sources_unchanged=all(sha(p)==v for p,v in source.items()),seconds=time.monotonic()-start)
save('SOURCE_SHA256.json',source);save('COMPUTE_SUMMARY.json',summary);print(json.dumps(clean(summary),ensure_ascii=False,indent=2),flush=True)
