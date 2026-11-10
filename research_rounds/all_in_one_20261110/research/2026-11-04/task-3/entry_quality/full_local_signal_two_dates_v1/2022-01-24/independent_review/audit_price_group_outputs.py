"""Saved path/group arithmetic and bounded3-stock raw checks only; no models."""
from pathlib import Path
import hashlib,json,math,statistics
import numpy as np,pandas as pd
import pyarrow.dataset as ds

R=Path(__file__).resolve().parents[1];O=R/'independent_review';P=R/'paths';DAY=R.name
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
def check(a,b):
    if pd.isna(a)or pd.isna(b):assert pd.isna(a)and pd.isna(b),(a,b)
    elif isinstance(b,str):assert a==b,(a,b)
    else:assert abs(float(a)-float(b))<=1e-12,(a,b)
def q(v,p):
    if not v:return np.nan
    v=sorted(v);u=(len(v)-1)*p;i=math.floor(u);j=math.ceil(u);return v[i]+(v[j]-v[i])*(u-i)
def avg(v):return statistics.fmean(v)if len(v)else np.nan
def ratio(a,b):return a/b if b else np.nan
def main():
    priorpath=R/'FROZEN_IBUY_PRIOR_RANKS.parquet';prior=pd.read_parquet(priorpath).set_index('sid').sort_index();N=len(prior)
    h=pd.read_parquet(P/'HORIZON_PATHS.parquet').set_index('sid').sort_index();long=pd.read_parquet(P/'LONG_PATHS.parquet').sort_values(['sid','future_observation'])
    assert prior.index.equals(h.index)and N==read(R/'PRIOR_RANKS_RECEIPT.json')['N']
    shared=[]
    for c in prior.columns.intersection(h.columns):
        for sid in prior.index:check(h.loc[sid,c],prior.loc[sid,c])
        shared.append(c)
    joined=pd.read_parquet(R/'FROZEN_RANKS_WITH_PRICE_LABELS.parquet').set_index('sid').sort_index()
    assert joined.index.equals(prior.index)
    for c in prior.columns:pd.testing.assert_series_equal(joined[c],prior[c],check_names=False)
    for c in h.columns:
        if c not in prior.columns:pd.testing.assert_series_equal(joined[c],h[c],check_names=False)
    bysid={sid:g for sid,g in long.groupby('sid')};coverage={}
    assert not long.duplicated(['sid','future_observation']).any()
    for sid,r in h.iterrows():
        g=bysid.get(sid,long.iloc[:0]);assert g.future_observation.tolist()==list(range(1,len(g)+1))and len(g)==min(20,r.block_available_future_observations)
        assert g.observation_date.is_unique and g.observation_date.is_monotonic_increasing and (g.observation_date>DAY).all()
        base=float(prior.loc[sid,'current_close_qfq']);assert np.float64(base).view(np.uint64)==np.float64(r.anchor_close).view(np.uint64)
        assert g.source.eq(r.anchor_source).all()and g.close.gt(0).all()and g.amount_native.gt(0).all()
        values=[float(c)/base-1 for c in g.close];np.testing.assert_allclose(g.close_change_from_anchor,values,rtol=0,atol=0)
        for n in [5,20]:
            z=g.iloc[:n];v=values[:n];complete=len(v)==n;prefix=f'h{n}_'
            assert bool(r[prefix+'complete'])==complete and bool(r[prefix+'right_censored'])==(not complete)
            assert r[prefix+'observations_available']==len(v)
            for col,value in [('return',v[-1]if complete else np.nan),('max_up',max([0.]+v)if complete else np.nan),('max_adverse',min([0.]+v)if complete else np.nan)]:check(r[prefix+col],value)
            check(r[prefix+'nth_date'],z.observation_date.iloc[-1]if complete else np.nan)
            if complete:assert r[prefix+'calendar_span_days']==(pd.Timestamp(z.observation_date.iloc[-1])-pd.Timestamp(DAY)).days
            assert r[prefix+'source_union_missing_row_proxy']==z.global_source_union_missing_rows_since_prior.sum()
    meta=read(P/'COVERAGE_METADATA.json');common=meta['common_endpoint_dates']
    for n in [5,20]:
        complete=h[f'h{n}_complete'];coverage[str(n)]={'complete':int(complete.sum()),'censored':int((~complete).sum()),'gap_stocks':int(h[f'h{n}_source_union_missing_row_proxy'].gt(0).sum()),'endpoints':h.loc[complete,f'h{n}_nth_date'].value_counts().sort_index().to_dict()}
        assert coverage[str(n)]['complete']==meta['horizons'][str(n)]['complete']and coverage[str(n)]['censored']==meta['horizons'][str(n)]['censored']
        assert coverage[str(n)]['endpoints']==meta['horizons'][str(n)]['actual_nth_dates']and coverage[str(n)]['gap_stocks']==meta['horizon_gap_proxy_stock_counts'][str(n)]
    x=joined.reset_index();actual=pd.read_csv(R/'GROUP_SUMMARIES.csv',float_precision='round_trip');tailtable=pd.read_csv(R/'TAIL_PRICE_CONCENTRATION.csv',float_precision='round_trip');labels=pd.read_csv(R/'EXPOST_DIAGNOSTIC_LABELS_ONLY.csv')
    bands=['ALL','RANKABLE','PVR_UNKNOWN']+[f'D{d}'for d in range(1,11)]+['TOP20','REST20','TOP100','REST100']
    keys={(view,scope,b,n)for n in [5,20]for view,scopes in [('WITHIN_SCOPE_RANKS',['ALL','OLD','OUTSIDE']),('GLOBAL_BANDS_BY_MEMBERSHIP',['OLD','OUTSIDE'])]for scope in scopes for b in bands}
    assert len(actual)==170 and set(actual[['view','scope','band','horizon']].itertuples(index=False,name=None))==keys
    tails={};denoms={};expectedlabels=set();checks=0
    for n in [5,20]:
        c=x[x[f'h{n}_complete']];ordered=c.sort_values([f'h{n}_return','sid'],ascending=[False,True])
        tails[n]={f'EXPOST_TOP{pc}PCT':set(ordered.head(math.ceil(len(c)*pc/100)).sid)for pc in [1,5]}
        for name,ids in tails[n].items():expectedlabels|={(sid,n,name,len(c),True)for sid in ids}
        denoms[n]=[math.fsum(max(0.,v)for v in c[f'h{n}_return']),math.fsum(c[f'h{n}_max_up'])]
    assert set(labels[['sid','horizon','label','label_universe_complete_N','not_prior_rank']].itertuples(index=False,name=None))==expectedlabels
    rankcols={'ALL':'rank_ALL_LOCAL_I_BUY','OLD':'rank_OLD1709_STATIC_REFERENCE_I_BUY','OUTSIDE':'rank_OUTSIDE_OLD1709_I_BUY'}
    for row in actual.to_dict('records'):
        n=int(row['horizon']);scope=row['scope'];band=row['band'];g=x if scope=='ALL'else x[x.in_old1709_exact.eq(scope=='OLD')]
        scope_for_rank='ALL'if row['view']=='GLOBAL_BANDS_BY_MEMBERSHIP'else scope;rank=rankcols[scope_for_rank];dec='decile_'+scope_for_rank
        if band=='RANKABLE':g=g[g[rank].notna()]
        elif band=='PVR_UNKNOWN':g=g[g[rank].isna()]
        elif band.startswith('D'):g=g[g[dec].eq(int(band[1:]))]
        elif band.startswith('TOP'):g=g[g[rank].le(int(band[3:]))]
        elif band.startswith('REST'):g=g[g[rank].gt(int(band[4:]))]
        c=g[g[f'h{n}_complete']];nn=len(c);vals=c[f'h{n}_return'].tolist();mfe=c[f'h{n}_max_up'].tolist();mae=c[f'h{n}_max_adverse'].tolist()
        expected={'prior_N':len(g),'prior_rankable_N':int((~g.PVR_rank_unknown).sum()),'prior_PVR_unknown_N':int(g.PVR_rank_unknown.sum()),'complete_N':nn,'unknown_N':len(g)-nn,'horizon_censored_N':int(g[f'h{n}_right_censored'].sum()),'source_gap_proxy_N':int(g[f'h{n}_source_union_missing_row_proxy'].gt(0).sum())}
        for label,v in [('terminal',vals),('MFE',mfe),('MAE_signed',mae)]:
            expected.update({label+'_mean':avg(v),label+'_median':statistics.median(v)if v else np.nan,label+'_p10':q(v,.1),label+'_p90':q(v,.9),label+'_min':min(v)if v else np.nan,label+'_max':max(v)if v else np.nan})
        expected.update(terminal_p25=q(vals,.25),terminal_p75=q(vals,.75));positive=sum(v>0 for v in vals)
        expected.update(terminal_positive_N=positive,terminal_positive_rate_complete=ratio(positive,nn),terminal_positive_fraction_prior=ratio(positive,len(g)))
        for label,v in [('terminal',vals),('MFE',mfe)]:
            for t in [.2,.5,1.]:k=sum(z>=t for z in v);expected[f'{label}_ge{int(t*100)}pct_N']=k;expected[f'{label}_ge{int(t*100)}pct_rate']=ratio(k,nn)
        for t in [.1,.2]:expected[f'terminal_le_minus{int(t*100)}pct_rate']=ratio(sum(z<=-t for z in vals),nn)
        mass=math.fsum(max(0.,v)for v in vals);expected['positive_terminal_change_mass_share']=ratio(mass,denoms[n][0]);expected['MFE_change_mass_share']=ratio(math.fsum(mfe),denoms[n][1])
        ordered=c.sort_values([f'h{n}_return','sid'],ascending=[False,True]);v=ordered[f'h{n}_return'].tolist()
        for k in [1,5,20]:expected[f'within_group_largest{k}_positive_terminal_mass_share']=ratio(math.fsum(max(0.,z)for z in v[:k]),mass)
        expected['terminal_mean_excluding_expost_largest1_diagnostic']=avg(v[1:])
        for name,ids in tails[n].items():hits=len(set(c.sid)&ids);expected.update({name+'_global_N':len(ids),name+'_hits':hits,name+'_capture_global_complete':ratio(hits,len(ids)),name+'_precision_group_complete':ratio(hits,nn)})
        expected.update(actual_nth_date_min=c[f'h{n}_nth_date'].min()if nn else np.nan,actual_nth_date_max=c[f'h{n}_nth_date'].max()if nn else np.nan,calendar_span_min=c[f'h{n}_calendar_span_days'].min(),calendar_span_max=c[f'h{n}_calendar_span_days'].max(),common_endpoint_date=common[str(n)])
        aligned=c[c[f'h{n}_nth_date'].eq(common[str(n)])];expected['common_endpoint_N']=len(aligned)
        for field,label in [('return','terminal'),('max_up','MFE'),('max_adverse','MAE_signed')]:expected['common_endpoint_'+label+'_mean']=avg(aligned[f'h{n}_{field}'].tolist())
        assert set(expected)==set(actual.columns)-{'view','scope','band','horizon'}
        for key,value in expected.items():check(row[key],value);checks+=1
    assert len(tailtable)==36
    for row in tailtable.to_dict('records'):
        n=int(row['horizon']);g=x if row['scope']=='ALL'else x[x.in_old1709_exact.eq(row['scope']=='OLD')];g=g[g[f'h{n}_complete']]
        col=f'h{n}_return'if row['price_mass_type']=='positive_terminal'else f'h{n}_max_up';m=[max(0.,v)for v in g[col]];total=math.fsum(m);largest=math.fsum(sorted(m,reverse=True)[:int(row['expost_largest_k'])])
        assert row['complete_N']==len(g)and row['price_path_only_not_portfolio_profit'];check(row['total_positive_price_change_mass'],total);check(row['largest_k_mass'],largest);check(row['largest_k_share'],ratio(largest,total))
    main=pd.read_csv(R/'TOP_VS_REST_MAIN.csv',float_precision='round_trip');subset=actual[(actual.view=='WITHIN_SCOPE_RANKS')&actual.band.isin(['ALL','RANKABLE','PVR_UNKNOWN','TOP20','REST20','TOP100','REST100'])]
    pd.testing.assert_frame_equal(main.reset_index(drop=True),subset.reset_index(drop=True))
    # Bounded raw checks chosen from prior signal/unknown status, never future gain.
    candidates=(['000620.SZ']+prior.index[prior.PVR_rank_unknown].tolist())if DAY=='2022-01-24'else['300666.SZ','603061.SH','301611.SZ']
    targets=list(dict.fromkeys(sid for sid in candidates if sid in prior.index))[:3]
    for sid in prior.sort_values('rank_ALL_LOCAL_I_BUY',na_position='last').index:
        if len(targets)==3:break
        if sid not in targets:targets.append(sid)
    source=Path(read(P/'FREEZE.json')['source_path']);condition=ds.field('symbol').isin(targets)&(ds.field('trade_date')>=pd.Timestamp(DAY))
    raw=ds.dataset(source).to_table(columns=['symbol','trade_date','close','amount','source','adjustment_factor'],filter=condition).to_pandas()
    rawpath=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet');underlying=ds.dataset(rawpath).to_table(columns=['symbol','trade_date','close'],filter=condition).to_pandas().set_index(['symbol','trade_date'])
    samples=[];coordinate_checks=0
    for sid,g in raw.groupby('symbol'):
        g=g.sort_values('trade_date');anchor=g[g.trade_date.eq(pd.Timestamp(DAY))].iloc[0];accepted=[]
        for row in g[g.trade_date.gt(pd.Timestamp(DAY))].itertuples(index=False):
            if not(isinstance(row.source,str)and row.source.strip()and row.source==anchor.source and math.isfinite(row.close)and row.close>0 and math.isfinite(row.amount)and row.amount>0):break
            accepted.append(row)
            if len(accepted)==20:break
        for row in [anchor]+accepted:
            date=row['trade_date']if isinstance(row,pd.Series)else row.trade_date;close=float(row['close']if isinstance(row,pd.Series)else row.close);factor=float(row['adjustment_factor']if isinstance(row,pd.Series)else row.adjustment_factor)
            assert np.float64(float(underlying.loc[(sid,date),'close'])*factor).view(np.uint64)==np.float64(close).view(np.uint64);coordinate_checks+=1
        for n in [5,20]:
            values=[z.close/anchor.close-1 for z in accepted[:n]];complete=len(values)==n;r=h.loc[sid]
            check(r[f'h{n}_return'],values[-1]if complete else np.nan);check(r[f'h{n}_max_up'],max([0.]+values)if complete else np.nan);check(r[f'h{n}_max_adverse'],min([0.]+values)if complete else np.nan)
            samples.append({'sid':sid,'PVR_unknown':bool(prior.loc[sid,'PVR_rank_unknown']),'horizon':n,'baseline':float(anchor.close),'future_closes':[float(z.close)for z in accepted[:n]],'future_dates':[str(z.trade_date.date())for z in accepted[:n]],'terminal':float(values[-1])if complete else None})
    files=[R/'FREEZE.json',R/'PRIOR_RANKS_RECEIPT.json',R/'SUMMARY_RECEIPT.json',priorpath,R/'GROUP_SUMMARIES.csv',R/'TOP_VS_REST_MAIN.csv',R/'TAIL_PRICE_CONCENTRATION.csv',R/'EXPOST_DIAGNOSTIC_LABELS_ONLY.csv',R/'FROZEN_RANKS_WITH_PRICE_LABELS.parquet',R/'summarize.py',P/'FREEZE.json',P/'COVERAGE_METADATA.json',P/'HORIZON_PATHS.parquet',P/'LONG_PATHS.parquet',P/'build_paths.py',O/'PRIOR_COHORT_AUDIT.json',Path(__file__)]
    result={'status':'PASS_BOUNDED_DATE_ALL_PRICE_PATHS_GROUPS_UNKNOWN_AND_EMPTY_BUCKETS','day':DAY,'remaining_blocks':[],'N':N,'known_PVR':int((~prior.PVR_rank_unknown).sum()),'PVR_unknown':int(prior.PVR_rank_unknown.sum()),'long_rows':len(long),'group_rows':170,'group_statistic_cells_checked':checks,'tail_concentration_rows':36,'expost_label_memberships':len(labels),'coverage':coverage,'shared_prior_path_metadata_checked':shared,'raw_price_hand_cases':samples,'raw_times_factor_coordinate_checks':coordinate_checks,'findings':['Every full i_buy member retained, including missingPVR; all future path arithmetic/complete/unknown/date fields compared.','Prior/path duplicate annotations equal before merge; final prior columns authoritative and unchanged.','170fixed groups/empty buckets/all statistics/36tail concentrations/global labels independently checked with1e-12 aggregate tolerance.','ALL=RANKABLE+PVR_UNKNOWN; oldTOP100 may be whole ranked61,REST100empty; empty means/precision/ownmass ratiosNA.','Three prior-selected raw source cases include missingPVR members when present; no model call.'],'limits':['Full saved path arithmetic checked; original raw future data independently reread only3stocks,not whole mother.','Fixed observation horizons may have different actual dates; source-union gap is not certified halt/tradability.','Static/current universe/qfq vintage/historical availability notPIT; no S0/CP/order/fees/portfolio/account/alpha certification.','Expost tails/leave-largest1/common-endpoint diagnostics are evaluation only, not new selection rules.'],'source_sha256':{str(p.resolve()):sha(p)for p in files},'new_models':0,'new_accounts':0}
    out=O/'PRICE_GROUP_AUDIT.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':result['status'],'day':DAY,'sha256':sha(out),'N':N,'coverage':coverage,'group_stats':checks,'raw_stocks':targets},ensure_ascii=False))
if __name__=='__main__':main()
