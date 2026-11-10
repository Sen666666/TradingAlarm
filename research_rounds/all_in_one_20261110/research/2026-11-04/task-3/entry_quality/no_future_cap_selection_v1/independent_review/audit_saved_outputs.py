"""All saved output rows/ranks plus four-stock28-point prior20 hand checks."""
from pathlib import Path
import hashlib,json,statistics
import numpy as np,pandas as pd
import pyarrow.parquet as pq

R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;E=R.parent
KEY=['sid','day'];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def bits(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float);assert np.array_equal(a.view(np.uint64),b.view(np.uint64))
def main():
    receipt=read(R/'COMPLETION.json');identity=read(R/'INPUT_IDENTITY.json');bound={}
    for p,z in identity['inputs'].items():
        if p.endswith('/run_comparison.py'):
            current=Path(p).read_text();old=current.replace("['.parquet','.csv','.json']","['parquet','csv','json']")
            assert sha(p)==z['sha256'] or hashlib.sha256(old.encode()).hexdigest()==z['sha256'],'driver changed beyond declared suffix-only metadata fix'
        else:assert sha(p)==z['sha256'],('input hash',p)
        bound[p]=sha(p)
    x=pd.read_parquet(R/'NO_CAP_RESEARCH_CANDIDATES.parquet').set_index(KEY).sort_index()
    c=pd.read_parquet(R/'SNAPSHOT_GATE_COMPARISON.parquet').set_index(KEY).sort_index()
    f=pd.read_parquet(E/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet').set_index(KEY).sort_index()
    rankings=pd.read_parquet(E/'local_observable_selection_v1/ranks/ALL_FIXED_DATE_RANKS.parquet')
    liq=pd.read_parquet(R/'LIQUIDITY20.parquet').set_index(KEY).sort_index()
    assert len(x)==38619 and len(c)==38619 and len(liq)==38619 and x.index.equals(f.index)and c.index.equals(x.index)
    assert x.index.is_unique and x.groupby('day').size().eq(5517).all()
    bits(x.score,f.score);bits(c.score,x.score)
    for col in ['current_close_qfq','raw_close','current_amount_passthrough']:bits(x[col],f[col])
    for col in ['target_row_present','pvr_valid_observation','pvr_status','source','current_block_observations_through_t']:pd.testing.assert_series_equal(x[col],f[col],check_names=False)
    for col in liq.columns:pd.testing.assert_series_equal(x[col],liq[col],check_names=False)
    assert not any('cap'in col.lower()or'roster'in col.lower()or'industry'in col.lower()for col in x.columns if col not in ['research_no_cap_pool','no_cap_PVR_rank'])
    knownsource=x.source.notna()&x.source.astype('string').str.strip().ne('').fillna(False)
    expected=x.target_row_present.eq(True)&knownsource&x.pvr_valid_observation.eq(True)&x.pvr_status.eq('KNOWN')&np.isfinite(x.score)
    assert np.array_equal(x.research_no_cap_pool,expected)
    for col in ['historical_listing_identity','historical_ST','historical_halt','historical_limit_state','executable_eligibility']:assert x[col].eq('UNKNOWN_NOT_CERTIFIED').all()
    full=rankings[rankings.scope.eq('FULL_LOCAL')].set_index(KEY).sort_index()
    np.testing.assert_allclose(x.no_cap_PVR_rank.to_numpy(float,na_value=np.nan),full.rank_PVR,rtol=0,atol=0,equal_nan=True)
    original_roster={r['symbol']:r for r in read(Path(next(p for p in identity['inputs']if p.endswith('/roster-dispositions.json'))))}
    for (sid,day),r in c.iterrows():
        ro=original_roster.get(sid)
        status='MISSING_CURRENT_ROSTER'if ro is None else'UNKNOWN_CURRENT_CAP'if ro['cap_cny']is None else'CURRENT_CAP_GT10BN'if ro['cap_cny']>10_000_000_000 else'CURRENT_CAP_NOT_GT10BN'
        assert r.snapshot_cap_status==status
        assert pd.isna(r.snapshot_cap_q)if status in ['MISSING_CURRENT_ROSTER','UNKNOWN_CURRENT_CAP']else bool(r.snapshot_cap_q)==(status=='CURRENT_CAP_GT10BN')
    assert np.array_equal(c.snapshot_cap_PVR_pool,c.research_no_cap_pool&c.snapshot_cap_status.eq('CURRENT_CAP_GT10BN'))
    summaries=[];top_expected=[]
    for day,g in c.reset_index().groupby('day'):
        for flag,rank,view in [('research_no_cap_pool','no_cap_PVR_rank','NO_FUTURE_CAP'),('snapshot_cap_PVR_pool','snapshot_cap_PVR_rank','CURRENT_2026_CAP_COMPARATOR')]:
            q=g[g[flag]].sort_values(['score','sid'],ascending=[False,True]);assert q[rank].tolist()==list(range(1,len(q)+1))
            top_expected.extend((day,view,sid,i+1)for i,sid in enumerate(q.sid.head(20)))
        retained=g[g.snapshot_cap_PVR_pool]
        assert retained.sort_values('no_cap_PVR_rank').sid.tolist()==retained.sort_values('snapshot_cap_PVR_rank').sid.tolist()
        old=rankings[rankings.scope.eq('OLD1709_EXACT_SUBPOOL')&rankings.day.eq(day)].set_index('sid')
        assert set(retained.sid)==set(old.index[old.rank_PVR.notna()])
        assert retained.set_index('sid').snapshot_cap_PVR_rank.to_dict()==old.rank_PVR.dropna().to_dict()
        mask=g.research_no_cap_pool
        summaries.append(dict(day=day,requested_series=len(g),observed_target_bars=int(g.target_row_present.sum()),missing_target_bars=int((~g.target_row_present).sum()),pvr_warmup_or_invalid_on_observed=int((g.target_row_present&~mask).sum()),no_cap_PVR_pool=int(mask.sum()),snapshot_cap_PVR_pool=int(g.snapshot_cap_PVR_pool.sum()),additional_no_cap_PVR_candidates=int((mask&~g.snapshot_cap_PVR_pool).sum()),pool_known_current_cap_false=int((mask&g.snapshot_cap_status.eq('CURRENT_CAP_NOT_GT10BN')).sum()),pool_current_cap_unknown=int((mask&g.snapshot_cap_status.eq('UNKNOWN_CURRENT_CAP')).sum()),pool_not_in_current_roster=int((mask&g.snapshot_cap_status.eq('MISSING_CURRENT_ROSTER')).sum()),prior20_known_all_observed=int(g.amount20_status.eq('KNOWN_PRIOR20_SOURCE_OBSERVATIONS').sum()),prior20_known_in_no_cap_pool=int((mask&g.amount20_status.eq('KNOWN_PRIOR20_SOURCE_OBSERVATIONS')).sum()),historical_legal_status_unknown_in_pool=int(mask.sum()),executable_eligibility_true=0))
    pd.testing.assert_frame_equal(pd.DataFrame(summaries),pd.read_csv(R/'SEVEN_DATE_COVERAGE.csv'),check_dtype=False)
    tops=pd.read_csv(R/'TOP20_TWO_VIEWS.csv',float_precision='round_trip')
    assert len(tops)==280 and set(tops[['day','view','sid','view_rank']].itertuples(index=False,name=None))==set(top_expected)
    overlaps=[]
    for day,g in tops.groupby('day'):
        a=set(g.loc[g.view.eq('NO_FUTURE_CAP'),'sid']);b=set(g.loc[g.view.eq('CURRENT_2026_CAP_COMPARATOR'),'sid']);overlaps.append({'day':day,'top20_intersection':len(a&b)})
    assert [r['top20_intersection']for r in overlaps]==[3,5,5,16,11,9,5]
    fixed=pd.read_parquet(R/'FIXED35_SIGNAL_COMPARISON.parquet').set_index(KEY).sort_index()
    source=E/'selection_qualification_closeout_v1/eligibility_source/fixed35/FIXED35_2024_09_24.parquet'
    oldfixed=pd.read_parquet(source).set_index(KEY).sort_index();assert len(fixed)==35 and fixed.index.equals(oldfixed.index)
    for col in ['e0_ready','e0_target','i_target','i_buy','g_grade','g_fresh_up','numeric_event','stock_hold_signal','stock_fresh_core_signal','signal_status']:pd.testing.assert_series_equal(fixed[col],oldfixed[col],check_names=False)
    for name,original in [('fresh','stock_fresh_core_signal'),('hold','stock_hold_signal')]:
        assert np.array_equal(fixed[name+'_no_cap'],fixed[original].eq(True))
        assert np.array_equal(fixed[name+'_current_cap_comparator'],fixed[name+'_no_cap']&fixed.snapshot_cap_PVR_pool)
    actual={k:int(fixed[k].sum())for k in ['fresh_no_cap','fresh_current_cap_comparator','hold_no_cap','hold_current_cap_comparator']}
    assert actual=={'fresh_no_cap':32,'fresh_current_cap_comparator':17,'hold_no_cap':34,'hold_current_cap_comparator':19}
    # Four exact user-requested stocks,7dates: raw source median only, no PVR/state calculation.
    targets=['000620.SZ','300666.SZ','300085.SZ','002583.SZ']
    sourcepath=Path(next(p for p in identity['inputs']if p.endswith('/adjusted_daily_bars.parquet')))
    bars=pq.read_table(sourcepath,columns=['symbol','trade_date','close','amount','source'],filters=[('symbol','in',targets)]).to_pandas()
    checks=[]
    for sid,g in bars.groupby('symbol'):
        g=g.sort_values('trade_date').reset_index(drop=True)
        for day in receipt['dates']:
            j=g.index[g.trade_date.eq(pd.Timestamp(day))].tolist();assert len(j)==1;j=j[0]
            window=g.iloc[j-20:j];current=g.iloc[j]
            assert len(window)==20 and len(set(window.source)|{current.source})==1
            assert np.isfinite(window.close).all()and window.close.gt(0).all()and np.isfinite(window.amount).all()and window.amount.gt(0).all()
            manual=statistics.median(window.amount.tolist());r=liq.loc[(sid,day)]
            assert manual==r.amount20_prior_native and r.amount20_prior_observations==20
            assert r.amount20_window_start==window.trade_date.iloc[0] and r.amount20_window_end==window.trade_date.iloc[-1]and window.trade_date.max()<pd.Timestamp(day)
            checks.append({'sid':str(sid),'day':day,'median20_native':manual,'start':str(window.trade_date.iloc[0].date()),'end':str(window.trade_date.iloc[-1].date()),'twenty_prior_amount_values':window.amount.tolist()})
    assert len(checks)==28
    # Guard repair must not change the existing real saved output values.
    before=R/'initial_before_source_guard';same=[]
    for name in ['LIQUIDITY20.parquet','NO_CAP_RESEARCH_CANDIDATES.parquet','SNAPSHOT_GATE_COMPARISON.parquet','FIXED35_SIGNAL_COMPARISON.parquet']:
        pd.testing.assert_frame_equal(pd.read_parquet(before/name),pd.read_parquet(R/name));same.append(name)
    pd.DataFrame(checks).drop(columns='twenty_prior_amount_values').to_csv(O/'FOUR_STOCK_PRIOR20_28_POINT_CHECKS.csv',index=False)
    for p in [R/'COMPLETION.json',R/'INPUT_IDENTITY.json',R/'candidate_view.py',R/'run_comparison.py',source,Path(__file__),O/'SMALL_CASES_AUDIT.json']+[R/n for n in ['LIQUIDITY20.parquet','NO_CAP_RESEARCH_CANDIDATES.parquet','SNAPSHOT_GATE_COMPARISON.parquet','FIXED35_SIGNAL_COMPARISON.parquet','TOP20_TWO_VIEWS.csv','SEVEN_DATE_COVERAGE.csv']]:bound[str(p.resolve())]=sha(p)
    result={'status':'PASS_BOUNDED_NO_FUTURE_CAP_VIEW_SAVED_OUTPUTS_WITH_LIMITS','remaining_blocks':[],'counts':{'all_requested_rows':38619,'symbols':5517,'dates':7,'both_view_top20_rows':280,'fixed35':actual,'independent_source_medians':28},'coverage':summaries,'top20_overlap':overlaps,'source_prior20_checks':checks,'guarded_output_equal_to_prior':same,'metadata_note':'Original COMPLETION.outputs={} due suffix strings without dots. Parent corrected only output-inventory code after run; reconstructing that one string replacement matches executed driver SHA. This audit binds actual output SHA directly; parent adds separate output seal without numeric rerun.','limits':['No current cap/roster/classification enters candidate_view white-listed fields or ranking. Snapshot roster is comparator-only after research view is generated.','No-cap removes only that research selection gate; canonical5517 static provider/survivor universe, factor vintages and daily availability remain non-PIT.','Legal/ST/halt/limit/executable fields remain UNKNOWN, not permission. Prior20 native amount has no threshold or rank weight and is not certified CNY/capacity.','Full original S0/E0/I/H1/CP/account qualification not recomputed. Only saved35 original stock signal examples reused; fresh32/hold34 are not global qualified orders.','All saved pools/ranks/score bits and four stocks28 source medians independently checked; full5517 prior20 medians not independently recalculated.','No new PVR/E0/I/market model/account/forward-label/parameter search or data refresh. Isolated synthetic function checks are separately recorded.'],'bindings':bound}
    p=O/'SAVED_OUTPUT_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'sha256':sha(p),'no_cap_pools':[r['no_cap_PVR_pool']for r in summaries],'cap_pools':[r['snapshot_cap_PVR_pool']for r in summaries],'fixed35':actual,'source_medians':28},ensure_ascii=False))
if __name__=='__main__':main()
