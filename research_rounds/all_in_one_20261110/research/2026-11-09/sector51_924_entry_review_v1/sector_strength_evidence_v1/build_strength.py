from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;P=O.parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
Q=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
END=pd.Timestamp('2024-10-08');START=pd.Timestamp('2024-01-02');SOURCE_START=pd.Timestamp('2023-11-01')
TARGETS=pd.to_datetime(['2024-09-06','2024-09-18','2024-09-19','2024-09-20','2024-09-23','2024-09-24','2024-09-25','2024-09-26','2024-09-27','2024-09-30','2024-10-08'])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
inputs={}
def hashed(p):inputs[str(p)]=sha(p);return p
ro=pd.read_csv(hashed(P/'joint51_candidate_v6_facts/CLASSIFICATION_ALL1709.csv'),keep_default_na=False)
ro=ro[ro.eligible.eq(True)].sort_values('symbol');ids=ro.symbol.to_list();sectors=sorted(ro.sector51.unique());sector_of=ro.set_index('symbol').sector51.to_dict();assert len(ids)==1692 and len(sectors)==50
manifest={m['symbol']:m for m in json.loads(M.read_text())};hashed(M)
k=pd.read_parquet(hashed(Q/'KNOWN3.parquet'))[ids].loc[:END].fillna(False).astype(bool)
r=pd.read_parquet(hashed(Q/'RIGHT3.parquet'))[ids].loc[:END].fillna(False).astype(bool)
ps=pd.read_parquet(hashed(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'),columns=['sid','day','state']);ps=ps[(ps.sid.isin(ids))&(ps.day<=END)].pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=ids)
known=k&ps.ge(0);right=r&known
cal=k.index[(k.index>=SOURCE_START)&(k.index<=END)];assert cal.is_unique and cal.is_monotonic_increasing
prices=np.full((len(cal),len(ids)),np.nan);valid=np.zeros_like(prices,dtype=bool);present=valid.copy();changed=valid.copy();raw_reasons=[]
t0=time.monotonic()
for j,s in enumerate(ids):
    m=manifest[s];path=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
    h=sha(path);assert h==m['source_sha256'][path],('SOURCE_DRIFT',s);inputs[path]=h
    z=pd.read_parquet(path).loc[:END];assert z.index.is_unique and z.index.is_monotonic_increasing
    z=z.reindex(cal);present[:,j]=z.symbol.eq(s).fillna(False)
    cols=['raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor']
    basic=z.observed_bar.eq(True)&z.price_eligible.eq(True)&z.volume_eligible.eq(True)&z.source_invalid.eq(False)&z.synthetic_event_bar.eq(False)
    vals=z[cols].to_numpy(float);finite_positive=np.isfinite(vals).all(axis=1)&(vals>0).all(axis=1)
    lineage_cols=['source_kind','source_path','segment_id'];lin=z[lineage_cols].astype('string');has_lin=lin.notna().all(axis=1)&lin.ne('').all(axis=1)
    chg=lin.ne(lin.shift()).fillna(True).any(axis=1);changed[:,j]=chg
    px=z.raw_close*z.adjustment_factor
    matches=np.isclose(px.to_numpy(float),z.close.to_numpy(float),rtol=1e-10,atol=1e-10,equal_nan=False)
    ok=basic.to_numpy(bool)&finite_positive&has_lin.to_numpy(bool)&matches
    valid[:,j]=ok;prices[:,j]=px.where(ok).to_numpy(float)
    if (j+1)%300==0:print('Read',j+1,'stocks',round(time.monotonic()-t0,1),'s',flush=True)
px=pd.DataFrame(prices,index=cal,columns=ids);vf=pd.DataFrame(valid,index=cal,columns=ids);pres=pd.DataFrame(present,index=cal,columns=ids);chg=pd.DataFrame(changed,index=cal,columns=ids)
returns={};eligible={};reasons={}
for h in [5,10,20]:
    all_present=pres.astype(int).rolling(h+1,min_periods=h+1).sum().eq(h+1)
    all_valid=vf.astype(int).rolling(h+1,min_periods=h+1).sum().eq(h+1)
    no_change=chg.astype(int).rolling(h,min_periods=h).sum().eq(0)
    ok=all_valid&no_change
    ret=(px/px.shift(h)-1).where(ok)
    returns[h]=ret;eligible[h]=ok
    reasons[h]=pd.DataFrame(np.where(ok,'KNOWN',np.where(~all_present,'MISSING_COMMON_DAY',np.where(~all_valid,'INVALID_DAILY_BAR','SOURCE_OR_SEGMENT_CHANGE'))),index=cal,columns=ids)
# Every price statistic uses the same explicit complete-window set; no constructed sector index.
prior_hi=px.shift(1).rolling(20,min_periods=20).max();high_incl=px.rolling(21,min_periods=21).max()
breakout=(px>prior_hi).where(eligible[20]);drawdown=(px/high_incl-1).where(eligible[20])
def streak(a):
    out=[];n=0
    for v in a:
        n=n+1 if bool(v) else 0;out.append(n)
    return np.asarray(out,int)
sector_breadth={};brecs=[]
for sec in sectors:
    ss=ro.loc[ro.sector51.eq(sec),'symbol'].tolist();kn=known[ss];rt=right[ss];N=len(ss);K=kn.sum(axis=1);n=rt.sum(axis=1);pair=kn&kn.shift(3,fill_value=False);J=pair.sum(axis=1);entered=(pair&rt&~rt.shift(3,fill_value=False)).sum(axis=1);left=(pair&~rt&rt.shift(3,fill_value=False)).sum(axis=1);diff=entered-left;u=N-K
    lo=n.ge(3)&(((3*n>=N)&J.gt(0)&diff.gt(0))|(2*n>=N))
    hi=(n+u).ge(3)&(((3*(n+u)>=N)&(diff.gt(0)|J.eq(0)))|(2*(n+u)>=N))
    state=np.where(lo,1,np.where(~hi,0,-1));half=np.where(2*n>=N,1,np.where(2*(n+u)<N,0,-1))
    z=pd.DataFrame(dict(N=N,K=K,n=n,U=u,paired_K=J,entered3=entered,left3=left,diff=diff,state=state,strength=(2*n>=N)&(2*n.shift()>=N)&diff.gt(0),breadth_lower=n/N,breadth_upper=(n+u)/N,half_state=half,true_streak=streak(state==1),false_streak=streak(state==0),unknown_streak=streak(state==-1),half_streak=streak(half==1),diff3_pct_N=diff/N,diff3_pct_pair=(diff/J).where(J>0),full_pool_saturated=(n.eq(N)&K.eq(N)),known_saturated=(K.gt(0)&n.eq(K))),index=k.index)
    sector_breadth[sec]=z
# Validate exact inherited M3 evidence through target end.
old=pd.read_csv(hashed(P/'joint51_candidate_v1/ALL50_DAILY_RECOGNITION.csv'),parse_dates=['day']);old=old[old.day<=END]
for sec,g in old.groupby('sector51'):
    a=sector_breadth[sec].loc[g.day]
    for c in ['N','K','n','U','paired_K','entered3','left3','diff','state','strength']:
        assert np.array_equal(a[c].to_numpy(),g[c].to_numpy()),('M3_MISMATCH',sec,c)
# Aggregate all 50, with market computed from the same complete-window rule over all 1692.
days=cal[cal>=START];bench=[];records=[]
for d in days:
    bm={}
    for h in [5,10,20]:
        x=returns[h].loc[d].dropna();bm[h]={'K':len(x),'mean':x.mean(),'median':x.median()}
        bench.append(dict(day=d.date(),window=h,N=1692,K=len(x),U=1692-len(x),mean_return=x.mean(),median_return=x.median(),positive_count=int((x>0).sum()),positive_fraction=(x>0).mean()))
    for sec in sectors:
        ss=ro.loc[ro.sector51.eq(sec),'symbol'].tolist();N=len(ss);b=sector_breadth[sec].loc[d]
        row=dict(day=d.date(),sector51=sec,**{'m3_'+c:b[c] for c in b.index})
        for h in [5,10,20]:
            x=returns[h].loc[d,ss].dropna();med=x.median();avg=x.mean();den=len(x)
            row.update({f'return{h}_K':den,f'return{h}_U':N-den,f'return{h}_coverage':den/N,f'return{h}_median':med,f'return{h}_mean':avg,f'return{h}_positive_count':int((x>0).sum()),f'return{h}_positive_fraction':(x>0).mean(),f'market{h}_K':bm[h]['K'],f'market{h}_U':1692-bm[h]['K'],f'market{h}_median':bm[h]['median'],f'market{h}_mean':bm[h]['mean'],f'rs{h}_median_pp':100*(med-bm[h]['median']),f'rs{h}_mean_pp':100*(avg-bm[h]['mean']),f'beat_market{h}_median_count':int((x>bm[h]['median']).sum()),f'beat_market{h}_median_fraction':(x>bm[h]['median']).mean()})
        x=breakout.loc[d,ss].dropna().astype(bool);dd=drawdown.loc[d,ss].dropna()
        row.update(breakout20_K=len(x),breakout20_U=N-len(x),breakout20_count=int(x.sum()),breakout20_fraction=x.mean(),drawdown20_median=dd.median(),drawdown20_mean=dd.mean())
        records.append(row)
a=pd.DataFrame(records).sort_values(['sector51','day']);a['day']=pd.to_datetime(a.day)
for h in [5,10,20]:
    a[f'rs{h}_positive_streak']=a.groupby('sector51')[f'rs{h}_median_pp'].transform(lambda x:streak(x.gt(0)))
    a[f'rs{h}_negative_streak']=a.groupby('sector51')[f'rs{h}_median_pp'].transform(lambda x:streak(x.lt(0)))
    # Informational cross-sectional ranks at t only. Never ranked by future returns.
    a[f'rs{h}_median_rank']=a.groupby('day')[f'rs{h}_median_pp'].rank(ascending=False,method='min')
a['rs10_and20_positive']=a.rs10_median_pp.gt(0)&a.rs20_median_pp.gt(0)
a['rs10_and20_positive_streak']=a.groupby('sector51').rs10_and20_positive.transform(streak)
a['rs5_and10_negative']=a.rs5_median_pp.lt(0)&a.rs10_median_pp.lt(0)
a['rs5_and10_negative_streak']=a.groupby('sector51').rs5_and10_negative.transform(streak)
# Point-in-time calculation checks: directly inspect every target stock window, not last valid observations.
qa=0;stockrows=[]
for d in TARGETS:
    i=cal.get_loc(d)
    for h in [5,10,20]:
        v=valid[i-h:i+1].all(axis=0)&~changed[i-h+1:i+1].any(axis=0)
        direct=np.where(v,prices[i]/prices[i-h]-1,np.nan)
        assert np.array_equal(v,eligible[h].loc[d].to_numpy())
        assert np.allclose(direct,returns[h].loc[d].to_numpy(float),equal_nan=True,rtol=1e-12,atol=1e-12)
        for j,s in enumerate(ids):stockrows.append(dict(day=d.date(),window=h,start_day=cal[i-h].date(),required_bars=h+1,symbol=s,sector51=sector_of[s],known=bool(v[j]),return_value=direct[j],reason=reasons[h].loc[d,s]))
        qa+=len(ids)
a=a.sort_values(['day','sector51']);a.to_csv(O/'ALL50_DAILY_EVIDENCE.csv',index=False,float_format='%.12g')
target=a[a.day.isin(TARGETS)].copy();assert len(target)==550;target.to_csv(O/'TARGET50_EVIDENCE.csv',index=False,float_format='%.12g')
pd.DataFrame(bench).to_csv(O/'MARKET_BENCHMARK.csv',index=False,float_format='%.12g');pd.DataFrame(stockrows).to_csv(O/'TARGET_STOCK_WINDOW_AUDIT.csv',index=False,float_format='%.12g')
ro.to_csv(O/'UNIVERSE1692.csv',index=False)
save(O/'SOURCE_HASHES.json',inputs)
meta=dict(status='PASS_READONLY_EVIDENCE_NO_ACCOUNT_RUN',universe_N=len(ids),sector_count=len(sectors),excluded_unclassified=17,target_days=[str(x.date()) for x in TARGETS],target_rows=len(target),all_daily_rows=len(a),market_benchmark_rows=len(bench),direct_window_check_cells=qa,all_m3_fields_match_prior=True,source_hashes_verified=len(ids),latest_allowed_date=str(END.date()),source_start=str(SOURCE_START.date()),output_start=str(START.date()),not_point_in_time_universe=True,not_point_in_time_sector_classification=True,not_forward_return_analysis=True,no_new_portfolio=True,return_definition='Adjusted close endpoint return over exactly h common trading-day intervals (h+1 bars), same source_kind/source_path/segment_id, all original valid complete OHLCV bars; returns missing if any missing/invalid day or lineage boundary.',relative_strength_definition='Sector median minus all1692-complete-window market median, or sector arithmetic mean minus matching market arithmetic mean. Columns ending _pp are actual percentage points (100 times return difference); raw return/drawdown/fraction columns are fractions.',streak_definition='M3 from complete known history beginning 2022-01-04; RS from 2024-01-02, initially left censored. Source is filtered through 2024-10-08 before any calculations; all windows trailing.',price_support='breakout20 requires current adjusted close strictly above max previous20 closes; drawdown20 current close/max current-and-prior20 closes-1; both use complete21-bar same-lineage set.',elapsed_seconds=round(time.monotonic()-t0,2))
save(O/'QA.json',meta)
print(json.dumps(meta,ensure_ascii=False,indent=2),flush=True)
focus=['证券保险','银行','软件与IT服务','半导体','电子元件材料','动力电池']
cols=['day','sector51','m3_N','m3_K','m3_n','m3_U','m3_state','m3_true_streak','m3_half_streak','m3_diff','return5_median','return10_median','return20_median','rs5_median_pp','rs10_median_pp','rs20_median_pp','rs10_and20_positive_streak','breakout20_fraction','drawdown20_median']
print(target[target.sector51.isin(focus)][cols].to_string(index=False),flush=True)
