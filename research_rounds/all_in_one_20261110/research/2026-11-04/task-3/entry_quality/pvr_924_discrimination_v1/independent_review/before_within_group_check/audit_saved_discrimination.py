"""Saved2313 path arithmetic/all groups;3predeclared raw source checks, no models."""
from pathlib import Path
import json,hashlib,math,statistics
import numpy as np,pandas as pd
import pyarrow.dataset as ds

R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;P=R/'paths'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def close(a,b):
    if pd.isna(a)or pd.isna(b):assert pd.isna(a)and pd.isna(b),(a,b)
    else:assert abs(float(a)-float(b))<=1e-12,(a,b)
def quant(v,p):
    w=sorted(float(x)for x in v);u=(len(w)-1)*p;lo=math.floor(u);hi=math.ceil(u)
    return w[lo]+(w[hi]-w[lo])*(u-lo)if w else np.nan
def groups(q):
    yield 'ALL',q
    for d in range(1,11):yield 'D'+str(d),q[q._dec.eq(d)]
    for k in [20,100]:
        yield 'TOP'+str(k),q[q._rank.le(k)]
        yield 'REST'+str(k),q[q._rank.gt(k)]
def main():
    prior=pd.read_parquet(R/'FROZEN2313_PRIOR_RANKS.parquet').set_index('sid').sort_index()
    h=pd.read_parquet(P/'HORIZON_PATHS.parquet').set_index('sid').sort_index()
    long=pd.read_parquet(P/'LONG_PATHS.parquet');long=long.sort_values(['sid','future_observation'])
    assert len(prior)==len(h)==2313 and prior.index.equals(h.index)and len(long)==46260
    assert long.groupby('sid').size().eq(20).all()and not long.duplicated(['sid','future_observation']).any()
    assert long.close.gt(0).all()and np.isfinite(long.close).all()and long.amount_native.gt(0).all()
    assert long.source.notna().all()and long.source.eq('tushare').all()
    assert (long.observation_date>'2024-09-24').all()
    expected_coverage={}
    for sid,z in long.groupby('sid'):
        base=float(prior.loc[sid,'current_close_qfq']);row=h.loc[sid]
        assert np.float64(base).view(np.uint64)==np.float64(row.anchor_close).view(np.uint64)
        assert z.future_observation.tolist()==list(range(1,21))and z.observation_date.is_unique and z.observation_date.is_monotonic_increasing
        ret=np.array([float(c)/base-1 for c in z.close]);np.testing.assert_allclose(z.close_change_from_anchor,ret,rtol=0,atol=0)
        assert z.source.eq(row.anchor_source).all()
        for n in [5,20]:
            a=z.iloc[:n];r=ret[:n];prefix='h'+str(n)+'_'
            assert row[prefix+'complete']and not row[prefix+'right_censored']and row[prefix+'observations_available']==n
            assert row[prefix+'nth_date']==a.observation_date.iloc[-1]
            assert row[prefix+'calendar_span_days']==(pd.Timestamp(a.observation_date.iloc[-1])-pd.Timestamp('2024-09-24')).days
            assert row[prefix+'return']==float(r[-1])and row[prefix+'max_up']==max(0.,max(r))and row[prefix+'max_adverse']==min(0.,min(r))
            assert row[prefix+'source_union_missing_row_proxy']==a.global_source_union_missing_rows_since_prior.sum()
    for n in [5,20]:
        expected_coverage[str(n)]={'complete':int(h[f'h{n}_complete'].sum()),'censored':int(h[f'h{n}_right_censored'].sum()),'gap_proxy_stocks':int(h[f'h{n}_source_union_missing_row_proxy'].gt(0).sum()),'endpoint_counts':h[f'h{n}_nth_date'].value_counts().sort_index().to_dict()}
    meta=read(P/'COVERAGE_METADATA.json')
    for n in [5,20]:
        z=expected_coverage[str(n)];assert z['complete']==meta['horizons'][str(n)]['complete']==2313 and z['censored']==0
        assert z['endpoint_counts']==meta['horizons'][str(n)]['actual_nth_dates']and z['gap_proxy_stocks']==meta['horizon_gap_proxy_stock_counts'][str(n)]
    merged=pd.read_parquet(R/'FROZEN_RANKS_WITH_PRICE_LABELS.parquet').set_index('sid').sort_index()
    assert merged.index.equals(prior.index)
    for c in prior.columns:pd.testing.assert_series_equal(merged[c],prior[c],check_names=False)
    for c in h.columns:
        if c not in ['day','rank_ALL_LOCAL_I_BUY']:pd.testing.assert_series_equal(merged[c],h[c],check_names=False)
    # Independently rebuild every150 reported group row from frozen prior membership.
    x=merged.reset_index();actual=pd.read_csv(R/'GROUP_SUMMARIES.csv',float_precision='round_trip')
    labels=pd.read_csv(R/'EXPOST_DIAGNOSTIC_LABELS_ONLY.csv');tail_rows=pd.read_csv(R/'TAIL_PRICE_CONCENTRATION.csv',float_precision='round_trip')
    assert len(actual)==150 and len(tail_rows)==36 and len(labels)==280
    expectedkeys=[];expectedlabels=set();metrics_checked=0
    def check_group(g,n,view,scope,band,tailsets,denoms):
        nonlocal metrics_checked
        z=actual[(actual.view==view)&(actual.scope==scope)&(actual.band==band)&(actual.horizon==n)];assert len(z)==1;z=z.iloc[0]
        expectedkeys.append((view,scope,band,n));v=g[g[f'h{n}_complete']];N=len(g);nn=len(v)
        for col,value in [('prior_N',N),('complete_N',nn),('unknown_N',N-nn),('horizon_censored_N',g[f'h{n}_right_censored'].sum()),('source_gap_proxy_N',g[f'h{n}_source_union_missing_row_proxy'].gt(0).sum())]:assert z[col]==value
        for field,label in [('return','terminal'),('max_up','MFE'),('max_adverse','MAE_signed')]:
            vals=v[f'h{n}_{field}'].tolist()
            for suffix,value in [('mean',statistics.fmean(vals)),('median',statistics.median(vals)),('p10',quant(vals,.1)),('p90',quant(vals,.9)),('min',min(vals)),('max',max(vals))]:close(z[label+'_'+suffix],value);metrics_checked+=1
            if field=='return':close(z.terminal_p25,quant(vals,.25));close(z.terminal_p75,quant(vals,.75))
        returns=v[f'h{n}_return'];positive=int(returns.gt(0).sum());assert z.terminal_positive_N==positive
        close(z.terminal_positive_rate_complete,positive/nn);close(z.terminal_positive_fraction_prior,positive/N)
        for field,label in [('return','terminal'),('max_up','MFE')]:
            values=v[f'h{n}_{field}']
            for threshold in [.2,.5,1.]:
                k=int(values.ge(threshold).sum());assert z[f'{label}_ge{int(threshold*100)}pct_N']==k;close(z[f'{label}_ge{int(threshold*100)}pct_rate'],k/nn)
        for threshold in [.1,.2]:close(z[f'terminal_le_minus{int(threshold*100)}pct_rate'],sum(r<=-threshold for r in returns)/nn)
        close(z.positive_terminal_change_mass_share,math.fsum(max(0.,r)for r in returns)/denoms[0]);close(z.MFE_change_mass_share,math.fsum(v[f'h{n}_max_up'])/denoms[1])
        for name,ids in tailsets.items():
            hits=len(set(v.sid)&ids);assert z[name+'_global_N']==len(ids)and z[name+'_hits']==hits
            close(z[name+'_capture_global_complete'],hits/len(ids));close(z[name+'_precision_group_complete'],hits/nn)
        assert z.actual_nth_date_min==v[f'h{n}_nth_date'].min()and z.actual_nth_date_max==v[f'h{n}_nth_date'].max()
        assert z.calendar_span_min==v[f'h{n}_calendar_span_days'].min()and z.calendar_span_max==v[f'h{n}_calendar_span_days'].max()
        endpoint={5:'2024-10-08',20:'2024-10-29'}[n];a=v[v[f'h{n}_nth_date'].eq(endpoint)];assert z.common_endpoint_date==endpoint and z.common_endpoint_N==len(a)
        for field,label in [('return','terminal'),('max_up','MFE'),('max_adverse','MAE_signed')]:close(z['common_endpoint_'+label+'_mean'],statistics.fmean(a[f'h{n}_{field}']))
    for n in [5,20]:
        complete=x[x[f'h{n}_complete']];ranked=sorted(complete.to_dict('records'),key=lambda r:(-r[f'h{n}_return'],r['sid']))
        tails={f'EXPOST_TOP{pc}PCT':{r['sid']for r in ranked[:math.ceil(len(complete)*pc/100)]}for pc in [1,5]}
        for label,ids in tails.items():expectedlabels|={(sid,n,label,2313,True)for sid in ids}
        denoms=[math.fsum(max(0.,r)for r in complete[f'h{n}_return']),math.fsum(complete[f'h{n}_max_up'])]
        for scope,col,dcol in [('ALL','rank_ALL_LOCAL_I_BUY','decile_ALL'),('OLD','rank_OLD1709_STATIC_REFERENCE_I_BUY','decile_OLD'),('OUTSIDE','rank_OUTSIDE_OLD1709_I_BUY','decile_OUTSIDE')]:
            g=x[x[col].notna()].assign(_rank=lambda z:z[col],_dec=lambda z:z[dcol])
            for band,z in groups(g):check_group(z,n,'WITHIN_SCOPE_RANKS',scope,band,tails,denoms)
            for field,label in [('return','positive_terminal'),('max_up','MFE')]:
                values=[max(0.,float(v))for v in g[f'h{n}_{field}']];total=math.fsum(values)
                ordered=sorted(zip(g.sid,values),key=lambda p:(-p[1],p[0]))
                for k in [1,5,20]:
                    row=tail_rows[(tail_rows.scope==scope)&(tail_rows.horizon==n)&(tail_rows.price_mass_type==label)&(tail_rows.expost_largest_k==k)].iloc[0]
                    assert row.complete_N==len(g)and row.price_path_only_not_portfolio_profit
                    close(row.total_positive_price_change_mass,total);close(row.largest_k_mass,math.fsum(v for _,v in ordered[:k]));close(row.largest_k_share,math.fsum(v for _,v in ordered[:k])/total)
        globalgroup=x.assign(_rank=x.rank_ALL_LOCAL_I_BUY,_dec=x.decile_ALL)
        for band,g in groups(globalgroup):
            for scope,m in [('OLD',True),('OUTSIDE',False)]:check_group(g[g.in_old1709_exact.eq(m)],n,'GLOBAL_BANDS_BY_MEMBERSHIP',scope,band,tails,denoms)
    assert set(actual[['view','scope','band','horizon']].itertuples(index=False,name=None))==set(expectedkeys)
    assert set(labels[['sid','horizon','label','label_universe_complete_N','not_prior_rank']].itertuples(index=False,name=None))==expectedlabels
    main=pd.read_csv(R/'TOP_VS_REST_MAIN.csv',float_precision='round_trip');expected=actual[(actual.view=='WITHIN_SCOPE_RANKS')&actual.band.isin(['ALL','TOP20','REST20','TOP100','REST100'])]
    pd.testing.assert_frame_equal(main.reset_index(drop=True),expected.reset_index(drop=True))
    # Three predeclared source price checks only, each baseline+20 observations.
    source=Path(read(P/'FREEZE.json')['source_path']);targets=['600198.SH','300085.SZ','002583.SZ']
    condition=ds.field('symbol').isin(targets)&(ds.field('trade_date')>=pd.Timestamp('2024-09-24'))&(ds.field('trade_date')<=pd.Timestamp('2024-11-30'))
    raw=ds.dataset(source).to_table(columns=['symbol','trade_date','close','amount','source','adjustment_factor'],filter=condition).to_pandas()
    rawpath=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet')
    rawprices=ds.dataset(rawpath).to_table(columns=['symbol','trade_date','close'],filter=condition).to_pandas().set_index(['symbol','trade_date'])
    samples=[]
    for sid,g in raw.groupby('symbol'):
        g=g.sort_values('trade_date');anchor=g[g.trade_date.eq(pd.Timestamp('2024-09-24'))].iloc[0];accepted=[]
        for row in g[g.trade_date.gt(pd.Timestamp('2024-09-24'))].itertuples(index=False):
            if not(isinstance(row.source,str)and row.source.strip()and row.source==anchor.source and math.isfinite(row.close)and row.close>0 and math.isfinite(row.amount)and row.amount>0):break
            accepted.append(row)
            if len(accepted)==20:break
        assert len(accepted)==20
        sourcepoints=[anchor]+accepted
        for row in sourcepoints:
            factor=float(row['adjustment_factor']if isinstance(row,pd.Series)else row.adjustment_factor);date=row['trade_date']if isinstance(row,pd.Series)else row.trade_date
            adj=float(row['close']if isinstance(row,pd.Series)else row.close)
            assert factor>0 and math.isfinite(factor)
            underlying=float(rawprices.loc[(sid,date),'close']);assert np.float64(underlying*factor).view(np.uint64)==np.float64(adj).view(np.uint64)
        for n in [5,20]:
            part=accepted[:n];r=[float(z.close)/float(anchor.close)-1 for z in part];saved=h.loc[sid]
            assert saved[f'h{n}_return']==r[-1]and saved[f'h{n}_max_up']==max(0.,max(r))and saved[f'h{n}_max_adverse']==min(0.,min(r))
            assert saved[f'h{n}_nth_date']==str(part[-1].trade_date.date())
            samples.append({'sid':sid,'horizon':n,'C0':float(anchor.close),'endpoint':str(part[-1].trade_date.date()),'future_closes':[float(z.close)for z in part],'future_dates':[str(z.trade_date.date())for z in part],'terminal':r[-1],'MFE':max(0.,max(r)),'MAE':min(0.,min(r)),'raw_times_factor_bitexact_at_baseline_plus20':True})
    files=[R/'FREEZE.json',R/'FROZEN2313_PRIOR_RANKS.parquet',R/'PRIOR_RANKS_RECEIPT.json',R/'SUMMARY_RECEIPT.json',R/'summarize.py',R/'GROUP_SUMMARIES.csv',R/'TOP_VS_REST_MAIN.csv',R/'TAIL_PRICE_CONCENTRATION.csv',R/'EXPOST_DIAGNOSTIC_LABELS_ONLY.csv',R/'FROZEN_RANKS_WITH_PRICE_LABELS.parquet',P/'HORIZON_PATHS.parquet',P/'LONG_PATHS.parquet',P/'FREEZE.json',P/'build_paths.py',P/'COVERAGE_METADATA.json',O/'PRELABEL_SCOPE_AUDIT.json',Path(__file__)]
    result={'status':'PASS_BOUNDED_FIXED2313_PATHS_ALL_GROUPS_AND_TAIL_SUMMARIES','remaining_blocks':[],'counts':{'mother':2313,'long_future_rows':46260,'h5_complete':2313,'h20_complete':2313,'horizon_censored':0,'summary_rows_all_checked':150,'summary_statistical_cells_checked':metrics_checked,'tail_concentration_rows_all_checked':36,'expost_terminal_label_memberships':280,'raw_source_handchecked_stocks':3,'raw_adjusted_factor_price_checks':63},'coverage':expected_coverage,'raw_source_cases':samples,'findings':['Frozen rank/group membership reviewed before label reading; all150 fixed groups retain their source N and independent within-scope/global-cross labels.','All2313 H5/H20 outcomes independently recomputed from saved long paths. Both include C0=0 for MFE/MAE clipping. Dates/source/gap/complete flags consistent.','Full horizon complete for all2313; source-tail rightcensor metadata for indefinite block is not H5/H20 censoring.','Every reported metric, threshold count, global terminal-tail capture/precision, and36within-scope price-mass concentration rows checked; small1e-12 tolerance only for aggregate summation/quantile rounding.','Global top1/5percent terminal labels have24/116members at each horizon, never used to revise source ranks.','Common-endpoint sensitivity added after availability metadata is secondary:Oct8/Oct29 fixed, original primary group/outcome statistics unchanged.','Three predeclared raw source paths and63rawclose*factor coordinates independently checked, no model call.'],'limits':['Full2313 saved path arithmetic checked, but raw future price/source facts independently reread only for3stocks. No full-source path recomputation or per-stock corporate-action economic certification.','Effective-observation H5/H20 have unequal calendar endpoints for6/11 stocks. Missing source-union dates do not prove halt or tradability.','One historically consumed correlated market date, current static universe and qfq vintage; no independent alpha/trueOOS/PIT/causal ranking certification.','All outcomes are close-baseline price references with no OPEN/execution/fees/portfolio. MFE is not captured profit and overlapping top/rest/decile analyses are not additive.'],'source_sha256':{str(p.resolve()):sha(p)for p in files},'new_models':0,'new_accounts':0,'new_signal_dates':0}
    p=O/'OUTPUT_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'sha256':sha(p),'counts':result['counts'],'coverage':expected_coverage},ensure_ascii=False))
if __name__=='__main__':main()
