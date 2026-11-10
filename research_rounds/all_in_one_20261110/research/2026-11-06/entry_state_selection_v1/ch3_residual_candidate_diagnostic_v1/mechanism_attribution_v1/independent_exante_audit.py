"""Read-only audit of pre-entry descriptors and score arithmetic, not P&L causation."""
from pathlib import Path
import ast, hashlib, json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;L=P/'lifecycle_comparison_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csv(p):return pd.read_csv(p,float_precision='round_trip',low_memory=False)
def eq(a,b):assert np.allclose(a,b,rtol=1e-10,atol=1e-10,equal_nan=True),(a,b)
for p,h in json.loads((O/'EXANTE_SOURCE_HASHES.json').read_text()).items():assert sha(p)==h
for n,h in json.loads((L/'report/OUTPUT_HASHES.json').read_text()).items():assert sha(L/'report'/n)==h
feat=csv(O/'EXANTE_ALL_STOCK_MONTH_FEATURES.csv');old=csv(L/'ALL_MARKET_STOCK_MONTH_FEATURES.csv')
assert len(feat)==len(old)==14635 and not feat.duplicated(['sid','month']).any()
joined=feat.merge(old,on=['sid','month'],validate='one_to_one',suffixes=('_a','_b'))
assert joined.status_a.eq(joined.status_b).all()
for col in ['RM','RAW_MOM11','RAW_EXCESS_STANDARDIZED','alpha','beta_market','beta_size','beta_value','residual_sd']:eq(joined[col+'_a'],joined[col+'_b'])
events=csv(L/'ALL_MARKET_EVENT_KEYS.csv');mapping=events[['sid','sector']].drop_duplicates()
assert not mapping.sid.duplicated().any();mapping=mapping.set_index('sid').sector.to_dict()
assert feat.sector.eq(feat.sid.map(mapping)).all()
sm={x['symbol']:x for x in json.loads((U/'STOCK_MANIFEST.json').read_text())}
im={x['series']:x for x in json.loads((U/'INDUSTRY_MANIFEST.json').read_text())}
with np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
lastday=pd.Series(cal,index=cal.to_period('M')).groupby(level=0).max()
f=pd.read_excel(P/'CH3_factors_monthly_202608.xlsx',sheet_name='Returnseries');f.index=pd.to_datetime(f.pop('mnthdt').astype(str),format='%Y%m%d').dt.to_period('M')
industry={};industry_cache={};physical=[];tested=set();maxerr=0.;n=0
text=(O/'exante_attribution.py').read_text();node=next(x for x in ast.parse(text).body if isinstance(x,ast.FunctionDef) and x.name=='industry_returns')
ns={'pd':pd,'np':np};exec(compile(ast.Module(body=[node],type_ignores=[]),'industry_returns_only','exec'),ns)
for sid,rows in feat.groupby('sid'):
    stock_path=next(p for p in sm[sid]['source_sha256'] if p.endswith('/signal.parquet'))
    assert sha(stock_path)==sm[sid]['source_sha256'][stock_path];stock=pd.read_parquet(stock_path).sort_index()
    sec=mapping[sid]
    if sec not in industry:
        path=next(p for p in im[sec]['source_sha256'] if p.endswith('/signal.parquet'))
        assert sha(path)==im[sec]['source_sha256'][path];industry[sec]=pd.read_parquet(path).sort_index()
    for r in rows.itertuples():
        if r.status!='CALENDAR_COMPUTABLE_RELEASE_UNKNOWN':
            assert r.industry_status=='STOCK_FEATURE_UNKNOWN'
            assert all(pd.isna(getattr(r,c)) for c in ['industry_beta36','raw_vol36','raw_vol11','normalization_component','alpha_component'])
            continue
        n+=1;m=pd.Period(r.month,freq='M');ms=pd.period_range(m-36,m-1,freq='M')
        ix=pd.DatetimeIndex(lastday.loc[pd.period_range(m-37,m-1,freq='M')].to_numpy())
        assert str(ix[-1].date())==r.max_input_date and ix[-1]<m.start_time
        sp=stock.loc[ix,'close'].to_numpy();ret=np.diff(sp)/sp[:-1];fac=f.loc[ms];y=ret-fac.rf_mon.to_numpy();recent=y[24:35]
        sy=np.std(recent,ddof=1);se=r.residual_sd;fm=fac[['mktrf','SMB','VMG']].iloc[24:35].mean().to_numpy()
        components=np.r_[recent.mean()*(1/se-1/sy),-r.alpha/se,-np.array([r.beta_market,r.beta_size,r.beta_value])*fm/se]
        for name,value in zip(['normalization_component','alpha_component','market_component','size_component','value_component'],components):eq(getattr(r,name),value)
        eq(r.raw_vol36,np.std(ret,ddof=1));eq(r.raw_vol11,np.std(ret[24:35],ddof=1));eq(r.raw_excess_mean11,recent.mean());eq(r.raw_excess_sd11,sy)
        reconstructed=recent.mean()/sy+components.sum();maxerr=max(maxerr,abs(reconstructed-r.RM));eq(r.RM,reconstructed)
        key=(sec,r.month)
        if key not in industry_cache:
            p=industry[sec];a=p.reindex(ix);span=p.loc[ix[0]:ix[-1]]
            assert np.isfinite(a[['close','raw_close','adjustment_factor']]).all().all() and a[['close','raw_close','adjustment_factor']].gt(0).all().all()
            assert a[['observed_bar','price_eligible']].eq(True).all().all() and a[['source_invalid','synthetic_event_bar']].eq(False).all().all()
            eq(a.close,a.raw_close*a.adjustment_factor)
            assert all(not span[c].isna().any() and span[c].nunique()==1 for c in ['source_kind','source_path','segment_id'])
            v=a.close.to_numpy();industry_cache[key]=np.diff(v)/v[:-1]
        ir=industry_cache[key];x=ir-fac.rf_mon.to_numpy();xc=x-x.mean()
        assert np.linalg.matrix_rank(np.c_[np.ones(36),x])==2
        beta=np.dot(xc,y-y.mean())/np.dot(xc,xc);alpha=y.mean()-beta*x.mean()
        assert r.industry_status=='KNOWN';eq(r.industry_beta36,beta);eq(r.industry_alpha36,alpha);eq(r.industry_vol36,np.std(ir,ddof=1));eq(r.industry_mom11,np.prod(1+ir[24:35])-1)
        if r.month not in tested:
            p=industry[sec];cut=(m-1).end_time
            a=ns['industry_returns'](p,ix);b=ns['industry_returns'](p[p.index<=cut].copy(),ix)
            assert a[0]==b[0] and np.array_equal(a[1],b[1])
            changed=p.copy();changed.loc[changed.index>=m.start_time,'close']=np.nan;changed.loc[changed.index>=m.start_time,'source_path']='FUTURE'
            c=ns['industry_returns'](changed,ix);assert a[0]==c[0] and np.array_equal(a[1],c[1])
            physical.append(dict(month=r.month,sector=sec,physical_prefix_and_future_invariant=True));tested.add(r.month)
q=csv(P/'CANDIDATE_RANKS_PRELABEL.csv');extra=[c for c in feat if c not in q]+['sid','month'];q=q.merge(feat[extra],on=['sid','month'],validate='many_to_one')
sw=csv(O/'EXANTE_FIXED_QUEUE_CH3_RAW_SWAPS.csv');metrics=[c[:-4] for c in sw if c.endswith('_CH3')]
expected_groups=0
for key,g in q.groupby(['window','day','sector']):
    a=g[g.RM_selected&~g.RAW_MOM11_selected];b=g[g.RAW_MOM11_selected&~g.RM_selected]
    if not len(a):assert not len(b);continue
    expected_groups+=1;s=sw[sw.window.astype(str).eq(str(key[0]))&sw.day.eq(key[1])&sw.sector.eq(key[2])];assert len(s)==1;s=s.iloc[0]
    assert len(a)==len(b)==s.slots and a.known.all() and b.known.all()
    assert set(s.CH3_exclusive.split('|'))==set(a.sid) and set(s.RAW_exclusive.split('|'))==set(b.sid)
    for c in metrics:
        eq(s[c+'_CH3'],a[c].mean());eq(s[c+'_RAW'],b[c].mean());eq(s[c+'_delta'],a[c].mean()-b[c].mean())
        assert s[c+'_nCH3']==a[c].notna().sum() and s[c+'_nRAW']==b[c].notna().sum()
assert expected_groups==len(sw)==512
summary=csv(O/'EXANTE_FIXED_QUEUE_SUMMARY.csv')
for r in summary.itertuples():
    g=sw[sw.window.astype(str).eq(str(r.window))];v=g[r.metric+'_delta'];daily=g.groupby('day')[r.metric+'_delta'].mean()
    assert r.queues==len(g) and r.known_queues==v.notna().sum() and r.slots==g.slots.sum()
    eq(r.queue_mean_delta,v.mean());eq(r.date_equal_mean_delta,daily.mean());eq(r.median_delta,v.median())
    assert r.positive==v.gt(0).sum() and r.negative==v.lt(0).sum() and r.zero==v.eq(0).sum()
z=csv(O/'EXANTE_ALL_ACTUAL_ROUNDS.csv');original=csv(L/'report/CORE_AND_FULL_ROUNDS.csv')
assert len(z)==len(original)==12241 and set(z.round_id)==set(original.round_id)
for col in original:
    a=z.set_index('round_id').sort_index()[col] if col!='round_id' else None
    if col=='round_id':continue
    b=original.set_index('round_id').sort_index()[col]
    assert (a.eq(b)|(a.isna()&b.isna())).all(),col
admissions=csv(O/'EXANTE_ALL_ADMISSION_SUMMARY.csv')
for r in admissions.itertuples():
    g=z[z.window.astype(str).eq(str(r.window))&z.arm.eq(r.arm)];v=g[r.metric]
    assert r.admissions==len(g) and r.known==v.notna().sum() and r.unknown==v.isna().sum()
    eq(r.mean,v.mean());eq(r.median,v.median())
report=dict(status='PASS_EXANTE_DESCRIPTOR_AND_SCORE_ARITHMETIC',stock_months=len(feat),known_stock_months_recomputed=n,
            industry_series=len(industry),industry_months=len(industry_cache),max_score_identity_error=maxerr,
            industry_OLS_recomputed_by_covariance=True,raw_volatility_recomputed=True,physical_prefix_cases=physical,
            all_fixed_disagreement_queues=expected_groups,actual_admissions=len(z),unknowns_retained=len(feat)-n,
            industry_source_and_static_mapping_verified=True,new_economic_runs=0,new_filters=0,
            limitation='Post-result descriptive audit. Same-clock raw momentum does not also control normalization or intercept removal. Score arithmetic is not cash P&L causation; total industry beta is not market-neutral industry alpha. No executable filter is justified.',
            inputs={n:sha(O/n) for n in ['exante_attribution.py','EXANTE_ATTRIBUTION_FREEZE.json','EXANTE_ALL_STOCK_MONTH_FEATURES.csv','EXANTE_FIXED_QUEUE_CH3_RAW_SWAPS.csv','EXANTE_ALL_ACTUAL_ROUNDS.csv']})
(O/'INDEPENDENT_EXANTE_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='physical_prefix_cases'},ensure_ascii=False,indent=2))
