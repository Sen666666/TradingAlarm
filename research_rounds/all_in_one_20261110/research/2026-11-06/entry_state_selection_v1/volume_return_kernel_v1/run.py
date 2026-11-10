"""One frozen conditional return kernel diagnostic. No account or original indicator rerun."""
from pathlib import Path
import sys,json,hashlib,time
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
R=O.parent
B=R/'selection_entry_diagnosis_v1'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
S=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design')
sys.path.insert(0,str(S))
from features import original_pvr,original_observation_clock
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
mode=sys.argv[1] if len(sys.argv)>1 else 'cases'
save('PROTOCOL.json',dict(status='FIXED_BEFORE_NEW_FIT_ALREADY_SEEN_HISTORY_NOT_OOS',stock_estimation=True,industry_pooling=False,train_window=504,min_samples=252,ridge_pseudocount=20,volume_proxy='V=log(amount/median(previous21 amount)); NOT turnover or causal flow',y_main='log(O[s+2]/O[s+1]), exact common trading dates, same source block',y_control='log(C[s+1]/C[s])',freeze='At original I start tau, only labels with maturity<tau; latest504 source rows strictly before tau. Main s+2<tau, control s+1<tau. Coefficients carried until next I start including non-I days; no historical e rewritten.',fit='Training-only predictor centering/scaling. min sum((y-a-b*r-c*r*V)^2)+20*sum(standardized_predictor_coeff^2). Intercept unpenalized. AR-only same protocol is mechanism ablation.',kernel='e_j=tanh((b_frozen+c_frozen*V_j)*r_j/s_j); nuisance intercept not used; E=sum original21 normalized .9^k e; score=50+50*tanh(2E). Each historical j uses its own then-frozen theta.',unknown='Keep original queue slot, no new entry gate. Require all21 contributions and original PVR known; source invalid resets.',K='min(20,N) same exact original legal empty MOBILE PVR account day, same candidate/permission/pending/holding state. Original_PVR baseline rank and unknown slots preserved.',horizons=[5,20,60],major_periods=['2024-09-24..2024-10-31','2026-01-01..2026-03-31'],no_parameter_scan=True,no_accounts=True))
manifest={x['symbol']:x for x in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates'])
cal=cal[cal<='2026-05-15']
queue=pd.read_parquet(B/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet')
queue=queue[queue.account.eq('PVR')].copy()
first=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv');first=first[first.account.eq('PVR')].copy()
caseids=['600056.SH','002317.SZ','000620.SZ','002911.SZ','300085.SZ','002583.SZ','000506.SZ','300666.SZ','688603.SH','301611.SZ']
sids=caseids if mode=='cases' else sorted(set(queue.sid)|set(first.sid))
parts=[];fits=[];audits=[];sources={str(p):sha(p) for p in [M,H,Path(__file__),S/'features.py',B/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet']}
def fit(q,cols,yname):
    z=q[cols+[yname]].dropna()
    if len(z)<252:return None
    X=z[cols].to_numpy(float);y=z[yname].to_numpy(float);mu=X.mean(0);sd=X.std(0)
    if not np.isfinite(sd).all() or (sd<=1e-12).any():return None
    Z=(X-mu)/sd;bet=np.linalg.solve(Z.T@Z+20*np.eye(len(cols)),Z.T@(y-y.mean()))/sd
    return np.r_[y.mean()-mu@bet,bet],len(z),str(z.index[0].date()),str(z.index[-1].date())
def compute(sid,end=None):
    m=manifest[sid];p=[p for p in m['source_sha256'] if p.endswith('/signal.parquet')][0]
    f=pd.read_parquet(p)
    native=pd.read_parquet(m['refs']['facts'])
    if end is not None:f=f.loc[:end];native=native.loc[:end]
    f=f.loc[:'2026-05-15'];native=native.reindex(f.index)
    comp=f.close.notna()&native.close.notna()
    err=float((f.close[comp]-native.close[comp]).abs().max())
    assert err<1e-7,(sid,err)
    z=original_pvr(f);valid,block=original_observation_clock(f)
    z['V']=np.log(f.amount/z.amount_ref);z['rV']=z.r*z.V
    # Exact common exchange calendar; never skip suspended/missing dates for targets.
    ff=f.reindex(cal);bb=block.reindex(cal)
    oo=np.log(ff.open.shift(-2)/ff.open.shift(-1)).where(bb.eq(bb.shift(-1))&bb.eq(bb.shift(-2)))
    cc=np.log(ff.close.shift(-1)/ff.close).where(bb.eq(bb.shift(-1)))
    z['yoo']=oo.reindex(z.index);z['ycc']=cc.reindex(z.index)
    mat1=pd.Series(cal.to_series().shift(-1).to_numpy(),index=cal).reindex(z.index)
    mat2=pd.Series(cal.to_series().shift(-2).to_numpy(),index=cal).reindex(z.index)
    roots=native.i_target.eq(1)&native.i_target.shift(fill_value=0).ne(1)
    ans=z[['r','V','scale','u','score']].rename(columns={'score':'native_pvr'}).copy()
    for name in ['OO','CC','AR']:
        ans[name+'_e']=np.nan;ans[name+'_h']=np.nan;ans[name+'_b']=np.nan;ans[name+'_c']=np.nan
    ans['root']=pd.NaT
    rr=[];rootpos=np.flatnonzero(roots.to_numpy())
    for k,ix in enumerate(rootpos):
        tau=f.index[ix];nxt=rootpos[k+1] if k+1<len(rootpos) else len(f)
        start=max(0,ix-504);train=z.iloc[start:ix].copy()
        sameblock=block.iloc[start:ix].eq(block.iloc[ix])
        train.loc[~sameblock,['yoo','ycc']]=np.nan
        train.loc[mat2.iloc[start:ix].ge(tau),'yoo']=np.nan
        train.loc[mat1.iloc[start:ix].ge(tau),'ycc']=np.nan
        region=f.index[ix:nxt];region=region[block.loc[region].eq(block.iloc[ix])];ans.loc[region,'root']=tau
        for name,cols,y in [('OO',['r','rV'],'yoo'),('CC',['r','rV'],'ycc'),('AR',['r'],'yoo')]:
            v=fit(train,cols,y)
            if v is None:continue
            beta,n,ts,te=v;a,b=beta[:2];c=beta[2] if len(beta)>2 else 0.
            h=b+c*z.loc[region,'V']
            ans.loc[region,name+'_e']=np.tanh(h*z.loc[region,'r']/z.loc[region,'scale'])
            ans.loc[region,name+'_h']=h;ans.loc[region,name+'_b']=b;ans.loc[region,name+'_c']=c
            rr.append(dict(sid=sid,root=str(tau.date()),model=name,a=a,b=b,c=c,n=n,train_first=ts,train_last=te))
    weights=.9**np.arange(20,-1,-1);weights/=weights.sum()
    for name in ['OO','CC','AR']:
        ans[name]=np.nan
        for _,g in ans[valid].groupby(block[valid],sort=False):
            e=g[name+'_e'].rolling(21,min_periods=21).apply(lambda x:np.dot(weights,x),raw=True)
            ans.loc[g.index,name]=50+50*np.tanh(2*e)
    ans['day']=ans.index.strftime('%Y-%m-%d');ans['sid']=sid
    return ans,rr,p,err
start=time.monotonic()
for no,sid in enumerate(sids):
    a,rr,p,err=compute(sid)
    wanted=set(queue.loc[queue.sid.eq(sid),'day'])|set(first.loc[first.sid.eq(sid),'signal_day'])
    if mode=='cases':wanted|=set(a.loc['2024-09-18':'2024-10-15','day'])|set(a.loc['2026-01-01':'2026-02-15','day'])
    part=a[a.day.isin(wanted)].copy();parts.append(part);fits+=rr
    sources[p]=sha(p);sources[manifest[sid]['refs']['facts']]=sha(manifest[sid]['refs']['facts'])
    audits.append(dict(sid=sid,max_native_close_error=err))
    if no<3:
        for cut in ['2022-03-31','2024-09-24']:
            aa,_,_,_=compute(sid,cut)
            common=a.index.intersection(aa.index)
            pd.testing.assert_frame_equal(a.loc[common],aa.loc[common],check_exact=False,rtol=0,atol=1e-12)
    if(no+1)%200==0:print('stocks',no+1,'seconds',round(time.monotonic()-start,1),flush=True)
out=pd.concat(parts,ignore_index=True);out.to_parquet(O/(mode+'_SCORES.parquet'),index=False)
pd.DataFrame(fits).to_csv(O/(mode+'_FITS.csv'),index=False)
pd.DataFrame(audits).to_csv(O/(mode+'_SOURCE_CHECKS.csv'),index=False)
save(mode+'_SOURCES.json',sources)
print('SCORES',mode,len(out),'models',len(fits),'seconds',time.monotonic()-start,flush=True)
if mode=='cases':
    cf=first[first.sid.isin(sids)].merge(out,left_on=['sid','signal_day'],right_on=['sid','day'],validate='many_to_one')
    cols=['sid','signal_day','round_pnl','closed','PVR_decision','OO','AR','CC','OO_b','OO_c','OO_h','CC_h','V','root']
    cf[cols].to_csv(O/'CASES_ACTUAL_ROUNDS.csv',index=False);print(cf[cols].to_string(index=False))
    sys.exit(0)
# Seal scores/rank decisions before reading future price labels or actual round outcomes for evaluation.
sc=queue.merge(out,on=['sid','day'],how='left',validate='one_to_one')
selection=[];qc=[]
for day,g in sc.groupby('day',sort=True):
    base=g.sort_values(['original_priority_rank','sid']);k=min(20,len(base))
    selection.append(base.head(k).assign(strategy='PVR'))
    for name in ['OO','AR']:
        ready=base[name].notna()&base.original_PVR.notna()
        ranked=base[ready].sort_values([name,'original_priority_rank','sid'],ascending=[False,True,True])
        it=iter(ranked.index);ix=[next(it) if ready.loc[i] else i for i in base.index]
        selection.append(sc.loc[ix[:k]].assign(strategy=name))
        qc.append(dict(day=day,model=name,N=len(g),K=k,known=int(ready.sum()),changed=len(set(ix[:k])-set(base.head(k).index))))
sel=pd.concat(selection,ignore_index=True);sel.to_parquet(O/'SEALED_SELECTIONS.parquet',index=False)
pd.DataFrame(qc).to_csv(O/'QUEUE_AUDIT.csv',index=False)
save('RANK_SEAL.json',dict(selections_sha=sha(O/'SEALED_SELECTIONS.parquet'),source_sha=sha(O/'full_SCORES.parquet'),label_columns_in_rank=[],no_account=True))
labels=pd.read_parquet(B/'mobile_candidate_response_v1/FIXED_NATIVE_PRICE_LABELS.parquet')
sel=sel.merge(labels,on=['sid','day'],how='left',validate='many_to_one')
sel.to_parquet(O/'SELECTIONS_WITH_PRICE_LABELS.parquet',index=False)
results=[]
for period,mask in [('ALL',pd.Series(True,index=sel.index))]+[(str(y),sel.year.eq(y)) for y in [2022,2023,2024,2025,2026]]+[('2024_924',sel.day.between('2024-09-24','2024-10-31')),('2026Q1',sel.day.between('2026-01-01','2026-03-31'))]:
    p=sel[mask]
    for hor in [5,20,60]:
        ok=p.groupby('day')['complete'+str(hor)].all();q=p[p.day.isin(ok[ok].index)]
        for strategy,g in q.groupby('strategy'):
            r=g['ret'+str(hor)];win=r>0;loss=r<0
            results.append(dict(period=period,H=hor,strategy=strategy,source_picks=int((p.strategy==strategy).sum()),common_days=g.day.nunique(),n=len(g),return_day=g.groupby('day')['ret'+str(hor)].mean().mean(),winrate=win.mean(),avg_win=r[win].mean(),avg_loss=r[loss].mean(),mae=g['mae'+str(hor)].mean(),mfe=g['mfe'+str(hor)].mean(),big60=g.big60_posthoc.sum(),return_minus_40bp=r.mean()-.004,return_minus_100bp=r.mean()-.01))
pd.DataFrame(results).to_csv(O/'SAME_DATE_K_RESULTS.csv',index=False)
# Original actual round labels are descriptive association only, not rerun outcomes.
actual=first.merge(out,left_on=['sid','signal_day'],right_on=['sid','day'],how='left',validate='many_to_one')
actual.to_csv(O/'ACTUAL_ROUND_ASSOCIATION.csv',index=False)
assoc=[]
for name in ['OO','AR']:
    for yr,g in actual.groupby('year'):
        for sign,sub in [('known',g[g[name].notna()]),('positive_h',g[g[name+'_h']>0]),('nonpositive_h',g[g[name+'_h']<=0])]:
            c=sub[sub.closed];assoc.append(dict(model=name,year=yr,group=sign,n=len(sub),closed=len(c),wins=int(c.round_pnl.gt(0).sum()),net_winrate=c.round_pnl.gt(0).mean(),round_pnl_sum=c.round_pnl.sum()))
pd.DataFrame(assoc).to_csv(O/'ROUND_ASSOCIATION_SUMMARY.csv',index=False)
save('COMPLETION.json',dict(status='COMPLETED_DIAGNOSTIC_NOT_STRATEGY',stocks=len(sids),score_rows=len(out),source_queue_rows=len(queue),selected_rows=len(sel),accounts=0,parameters_scanned=0,all_sources_unchanged=all(sha(p)==h for p,h in sources.items()),seconds=time.monotonic()-start))
print(pd.DataFrame(results).to_string(index=False))
