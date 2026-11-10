"""Fixed-breakout return-per-amount retest diagnostic. Native saved inputs only."""
from pathlib import Path
import json,hashlib,time,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
FP=R/'fip_first_entry_diagnostic_v1/FIRST_ENTRIES_WITH_FIP.csv'
QP=R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet'
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
END='2026-05-15'
DATES=['2022-03-03','2022-03-24','2022-10-14','2023-03-10','2024-07-29','2024-09-24','2024-10-15','2025-07-01','2026-01-15']
CASES=[('002385.SZ','2022-03-04'),('300182.SZ','2022-01-04'),('601607.SH','2022-03-24'),('600606.SH','2022-03-22'),('688582.SH','2024-07-29'),('002317.SZ','2022-10-14'),('600056.SH','2022-03-03'),('000620.SZ','2022-01-11'),('002911.SZ','2022-07-25'),('300085.SZ','2024-09-24'),('002583.SZ','2024-10-15'),('000506.SZ','2024-10-15')]
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
protocol=dict(status='FIXED_BEFORE_NEW_Z_COMPUTATION_ALL_HISTORY_PREVIOUSLY_SEEN',formula='At native I 0->1 a freeze B=max(previous20 native adjusted highs), Aref=median(previous20 amounts). First close>B starts breakout. First later lower close confirms previous peak Cp; U=ln(Cp/B), Vup=sum(A/Aref) from breakout through peak inclusive. First higher close after pullback confirms prior trough; current rebound day excluded from Cmin and Vtest. D=ln(Cp/Cmin); Vtest=sum(A/Aref) from peak+1 through recovery-1. Z=(U*Vtest-D*Vup)/(U*Vtest+D*Vup).',
 state='I/source off resets. After breakout any C<B permanently fails this original I root. No reclaim/restart within root. First completed test fixed, no test reselection. Record Z only at native I=1 and fresh original CP. Existing CP after completed test consumes no new strategy action; first CP per root is event unit, later CP records only repeated observations.',
 ambiguity_resolved='No requirement to touch B; first lower then first higher completed closes. Flats prolong the relevant leg. All peak/pullback/recovery dates distinct. No intraday sequence guessing. First test stays fixed while waiting fresh CP. No threshold except natural Z>0 descriptive split.',
 main='All 2693 original PVR first entries; original closed 0-to-0 outcomes associations only. Also first scored CP per represented original I root and 9 preselected dates of original legal EMPTY MOBILE pool. No all-stock rerank/account/fee-return claim.',
 controls='Exact same signal-date,sector,n_up,n_test matched pairs if available; no relaxing for sample size. Z_time=(U*n_test-D*n_up)/(U*n_test+D*n_up), amounts replaced by1 each day. Z_mean=(U*meanA_test-D*meanA_up)/(...) as mechanism diagnostic only, not replacement candidate.',
 forward='Fixed20/60 common observations after query signal, next native adjusted OPEN benchmark. Completeness and same segment required; cutoff2026-05-15. No executable-fill claim.',
 fixed_dates=DATES,fixed_cases=CASES,no_accounts=True,no_parameters=True,no_full_entry_gate=True)
save('PROTOCOL.json',protocol)
src={str(p):sha(p) for p in [M,FP,QP,H,Path(__file__)]}
manifest={r['symbol']:r for r in json.loads(M.read_text())}
first=pd.read_csv(FP)
q=pd.read_parquet(QP);q=q[q.account.eq('PVR') & q.day.astype(str).isin(DATES)].copy();q['day']=q.day.astype(str)
common=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);common=common[common<=pd.Timestamp(END)]
ids=sorted(set(first.sid)|set(q.sid)|{s for s,d in CASES})
def calc(f,cp):
 rows=[];root=None;prevseg=None;prevactive=False
 for j,(day,r) in enumerate(f.iterrows()):
  active=bool(r.i_target==1);newseg=prevseg is None or r.segment_id!=prevseg
  if newseg:root=None;prevactive=False
  event=''
  if not active:root=None
  elif not prevactive:
   base=f.iloc[max(0,j-20):j];good=len(base)==20 and base.segment_id.eq(r.segment_id).all() and np.isfinite(base.high).all() and base.high.gt(0).all() and np.isfinite(base.amount).all() and base.amount.gt(0).all()
   root=dict(root=str(day.date()),state='PREBREAK' if good else 'UNKNOWN_BASE',a=j,B=float(base.high.max()) if good else np.nan,Aref=float(base.amount.median()) if good else np.nan,breakday=None,peakday=None,testday=None,recoveryday=None,failday=None,Z=np.nan,U=np.nan,D=np.nan,Vup=0.,Vtest=0.,n_up=0,n_test=0,Cp=np.nan,Cmin=np.nan,peakj=None,recoveryj=None,firstcp=None)
   event='I_START'
  if root is not None and root['state'] not in ['UNKNOWN_BASE','FAILED']:
   st=root['state'];C=float(r.close);A=float(r.amount)/root['Aref']
   if root['breakday'] is not None and C<root['B']:
    root['state']='FAILED';root['failday']=str(day.date());event='BREAK_FAILURE'
   elif st=='PREBREAK':
    if C>root['B']:
     root.update(state='ADVANCE',breakday=str(day.date()),peakday=str(day.date()),peakj=j,Cp=C,Vup=A,n_up=1);event='BREAK'
   elif st=='ADVANCE':
    if C>=root['Cp']:
     root.update(Cp=C,peakday=str(day.date()),peakj=j,Vup=root['Vup']+A,n_up=root['n_up']+1)
    else:
     root.update(state='TEST',testday=str(day.date()),Cmin=C,Vtest=A,n_test=1,U=math.log(root['Cp']/root['B']));event='TEST_START'
   elif st=='TEST':
    if C>float(f.close.iloc[j-1]):
     U=root['U'];D=math.log(root['Cp']/root['Cmin']);Vu=root['Vup'];Vt=root['Vtest'];nu=root['n_up'];nt=root['n_test']
     Z=(U*Vt-D*Vu)/(U*Vt+D*Vu)
     root.update(state='COMPLETE',recoveryday=str(day.date()),recoveryj=j,D=D,Z=Z,Z_time=(U*nt-D*nu)/(U*nt+D*nu),Z_mean=(U*(Vt/nt)-D*(Vu/nu))/(U*(Vt/nt)+D*(Vu/nu)))
     event='TEST_COMPLETE'
    else:
     root.update(Cmin=min(root['Cmin'],C),Vtest=root['Vtest']+A,n_test=root['n_test']+1)
   elif st=='COMPLETE':
    pass
  nativecp=bool(cp.receipt.iloc[j])
  scored=bool(root is not None and root['state']=='COMPLETE' and active and nativecp)
  if scored and root['firstcp'] is None:root['firstcp']=str(day.date())
  rr=dict(day=str(day.date()),state=root['state'] if root else 'I_INACTIVE',event=event,root=root['root'] if root else None,i_active=active,fresh_cp=nativecp,score_known=scored)
  if root:
   rr.update({k:root.get(k) for k in ['B','Aref','breakday','peakday','testday','recoveryday','failday','U','D','Vup','Vtest','n_up','n_test','Cp','Cmin','firstcp']})
   rr.update(Z=root['Z'] if scored else np.nan,Z_time=root.get('Z_time',np.nan) if scored else np.nan,Z_mean=root.get('Z_mean',np.nan) if scored else np.nan,wait_from_break=j-f.index.get_loc(pd.Timestamp(root['breakday'])) if root['breakday'] else np.nan,wait_after_recovery=j-root['recoveryj'] if root['recoveryj'] is not None else np.nan)
  rows.append(rr);prevseg=r.segment_id;prevactive=active
 return pd.DataFrame(rows).set_index('day')
results=[];opps=[];events=[];case=[];prefix=[];errors=[];start=time.monotonic()
def labels(f,t):
 out={};j=common.get_loc(pd.Timestamp(t))+1;ef=f.reindex(common);ep=ef.iloc[j] if j<len(ef) else None
 for h in [20,60]:
  path=ef.iloc[j:j+h];ok=ep is not None and len(path)==h and np.isfinite(ep.open) and ep.open>0 and np.isfinite(path.close).all() and path.close.gt(0).all() and path.segment_id.eq(ep.segment_id).all()
  out['complete'+str(h)]=bool(ok);out['ret'+str(h)]=float(path.close.iloc[-1]/ep.open-1) if ok else np.nan;out['mfe'+str(h)]=max(0,float(path.close.max()/ep.open-1)) if ok else np.nan;out['mae'+str(h)]=min(0,float(path.close.min()/ep.open-1)) if ok else np.nan
 return out
for no,sid in enumerate(ids):
 refs=manifest[sid]['refs'];pricepath=next(p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet'))
 ff=pd.read_parquet(refs['facts']).loc[:END];cp=pd.read_parquet(refs['CP1']);price=pd.read_parquet(pricepath,columns=['symbol','open','high','low','close','amount','segment_id']).reindex(ff.index)
 assert price.symbol.eq(sid).all(),(sid,pricepath,price.symbol.unique().tolist(),int(price.symbol.isna().sum()))
 err=float((price.close-ff.close).abs().max());assert err<1e-10,(sid,err);assert price.segment_id.eq(ff.segment_id).all()
 for path in [refs['facts'],refs['CP1'],pricepath]:src[path]=sha(path)
 f=ff[['close','segment_id','i_target']].join(price[['open','high','low','amount']]);f=f.loc[:END];cp=cp.reindex(f.index)
 z=calc(f,cp)
 if no in [0,1,2,100,200,300]:
  for stop in ['2022-03-31','2024-09-24']:
   sub=f.loc[:stop];a=calc(sub,cp.loc[sub.index]);pd.testing.assert_frame_equal(a,z.loc[a.index],check_exact=True);prefix.append(dict(sid=sid,stop=stop,passed=True))
 g=first[first.sid.eq(sid)]
 represented=set()
 for a in g.to_dict('records'):
  d=a['signal_day'];rr=z.loc[d].to_dict();represented.add(rr['root'])
  results.append(dict(**a,**{'Z_'+k:v for k,v in rr.items()}))
 e=z[z.score_known & ~z.index.to_series().lt('2022-01-01')]
 e=e[e.root.isin(represented)].groupby('root',sort=False).head(1)
 for d,r in e.iterrows():
  events.append(dict(sid=sid,day=d,year=int(d[:4]),sector=g.iloc[0].sector,**r.to_dict(),**labels(f,d)))
 for a in q[q.sid.eq(sid)].to_dict('records'):
  d=a['day'];opps.append(dict(**a,**{'Z_'+k:v for k,v in z.loc[d].to_dict().items()},**labels(f,d)))
 for s,d in CASES:
  if s==sid:
   c=z.loc[d].to_dict();a=g[g.signal_day.eq(d)]
   case.append(dict(sid=sid,day=d,**c,round_pnl=float(a.round_pnl.iloc[0]) if len(a) else np.nan))
   zz=z.loc[:d].tail(25).reset_index();zz['sid']=sid;zz['case_day']=d;zz['close']=f.close.reindex(pd.to_datetime(zz.day)).to_numpy();zz['amount']=f.amount.reindex(pd.to_datetime(zz.day)).to_numpy()
   zz.to_csv(O/f'CASE_{sid}_{d}.csv',index=False)
 if (no+1)%250==0:print('stocks',no+1,'seconds',round(time.monotonic()-start,1),flush=True)
x=pd.DataFrame(results);p=pd.DataFrame(opps);e=pd.DataFrame(events);c=pd.DataFrame(case)
x.to_csv(O/'ACTUAL_FIRST_ENTRIES.csv',index=False);p.to_csv(O/'FIXED_DATE_LEGAL_MOBILE.csv',index=False);e.to_csv(O/'FIRST_SCORED_EVENTS_PER_REPRESENTED_ROOT.csv',index=False);c.to_csv(O/'FIXED_CASES.csv',index=False);pd.DataFrame(prefix).to_csv(O/'PREFIX_CHECKS.csv',index=False)
def summarize(g):
 closed=g[g.closed]
 return dict(N=len(g),closed=len(closed),wins=int(closed.round_pnl.gt(0).sum()),winrate=float(closed.round_pnl.gt(0).mean()) if len(closed) else None,big60=int(g.native_big60.sum()),forward20=g.native_ret20.mean(),forward60=g.native_ret60.mean())
annual=[]
for year,g in x.groupby('year'):
 for group,mask in [('ALL',pd.Series(True,index=g.index)),('scored',g.Z_score_known),('Z_positive',g.Z_score_known & g.Z_Z.gt(0)),('Z_nonpositive',g.Z_score_known & g.Z_Z.le(0)),('native_CP_no_Z',g.Z_fresh_cp & ~g.Z_score_known),('no_CP',~g.Z_fresh_cp)]:
  annual.append(dict(year=year,group=group,**summarize(g[mask])))
pd.DataFrame(annual).to_csv(O/'ANNUAL_ACTUAL_COVERAGE.csv',index=False)
coverage=x.groupby(['year','Z_state','Z_fresh_cp']).agg(N=('sid','size'),big60=('native_big60','sum')).reset_index();coverage.to_csv(O/'STATE_COVERAGE.csv',index=False)
pair=[]
for (d,s,nu,nt),g in p[p.Z_score_known].groupby(['day','sector','Z_n_up','Z_n_test']):
 a=g.sort_values(['Z_Z','sid']);h=len(a)//2
 for j in range(h):
  lo=a.iloc[j];hi=a.iloc[-1-j]
  if lo.Z_Z==hi.Z_Z:continue
  pair.append(dict(day=d,sector=s,n_up=nu,n_test=nt,high=hi.sid,low=lo.sid,delta_Z=hi.Z_Z-lo.Z_Z,delta_wait=hi.Z_wait_from_break-lo.Z_wait_from_break,delta_U=hi.Z_U-lo.Z_U,delta_D=hi.Z_D-lo.Z_D,ret20=hi.ret20-lo.ret20,ret60=hi.ret60-lo.ret60))
pd.DataFrame(pair).to_csv(O/'EXACT_LENGTH_SAME_DAY_SECTOR_PAIRS.csv',index=False)
cg=p[p.Z_score_known]
ct=dict(known=len(cg),positive=int(cg.Z_Z.gt(0).sum()),nonpositive=int(cg.Z_Z.le(0).sum()),same_length_pairs=len(pair),amount_changes_natural_sign=int(cg.Z_Z.gt(0).ne(cg.Z_Z_time.gt(0)).sum()),Z_time_spearman=cg.Z_Z.corr(cg.Z_Z_time,method='spearman'),Z_testlength_spearman=cg.Z_Z.corr(cg.Z_n_test,method='spearman'),Z_mean_spearman=cg.Z_Z.corr(cg.Z_Z_mean,method='spearman'))
save('CONTROLS.json',ct)
print('ANNUAL',pd.DataFrame(annual).to_string(index=False));print('CASES',c.to_string(index=False));print('CONTROLS',ct)
print('OPPORTUNITY',p.groupby('day').agg(N=('sid','size'),known=('Z_score_known','sum')).to_string())
save('SOURCE_SHA256.json',src)
save('COMPLETION.json',dict(status='EVENT_DIAGNOSTIC_COMPLETE_NOT_STRATEGY',actual_first_entries=len(x),fixed_date_opportunities=len(p),scored_root_events=len(e),prefix_checks=len(prefix),source_files=len(src),all_sources_unchanged=all(sha(p)==v for p,v in src.items()),account_runs=0,original_models_run=0,parameter_searches=0,seconds=time.monotonic()-start))

