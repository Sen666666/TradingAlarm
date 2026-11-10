"""Seven fixed research cross sections; reuse original scores, no account/models."""
from pathlib import Path
import hashlib, json, time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import candidate_view as cv

HERE = Path(__file__).resolve().parent
ENTRY = HERE.parent
FEATURES = ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
RANKS = ENTRY/'local_observable_selection_v1/ranks/ALL_FIXED_DATE_RANKS.parquet'
SOURCE = Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
ROSTER = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/roster-dispositions.json')
FIXED35 = ENTRY/'selection_qualification_closeout_v1/eligibility_source/fixed35/FIXED35_2024_09_24.parquet'
NAMES = ['000620.SZ','300085.SZ','002583.SZ','300666.SZ','603061.SH','301611.SZ',
         '300604.SZ','301308.SZ','002371.SZ','688012.SH','688498.SH',
         '301348.SZ','600198.SH','300925.SZ','688479.SH']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''): h.update(block)
    return h.hexdigest()


def save(name, value):
    (HERE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def rank_subset(frame, flag, column):
    frame[column] = pd.Series(pd.NA, index=frame.index, dtype='Int64')
    for _, g in frame.loc[frame[flag].eq(True)].groupby('day', sort=False):
        ix = g.sort_values(['score','sid'], ascending=[False,True]).index
        frame.loc[ix,column] = np.arange(1,len(ix)+1)


def main():
    started = time.monotonic()
    assert not (HERE/'NO_CAP_RESEARCH_CANDIDATES.parquet').exists()
    source_paths = [SOURCE, FEATURES, RANKS, ROSTER, FIXED35, HERE/'FREEZE.json',
                    HERE/'candidate_view.py', Path(__file__).resolve()]
    before = {str(p):dict(sha256=sha(p), bytes=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns) for p in source_paths}
    old = json.loads((ENTRY/'local_observable_selection_v1/features/RUN_STARTED.json').read_text())
    assert before[str(SOURCE)]['sha256'] == old['sources'][str(SOURCE)]['sha256']
    sealed = json.loads((ENTRY/'local_observable_selection_v1/features/SEAL.json').read_text())
    assert before[str(FEATURES)]['sha256'] == sealed['files'][FEATURES.name]
    expected = json.loads((ENTRY/'local_observable_selection_v1/independent_review/FINAL_OUTPUT_AUDIT.json').read_text())
    save('INPUT_IDENTITY.json', dict(inputs=before, no_new_PVR_or_E0_I_recomputation=True,
         previous_feature_seal=sealed, previous_output_audit=expected))
    features = pd.read_parquet(FEATURES)
    assert len(features)==38619 and features.sid.nunique()==5517 and sorted(features.day.unique())==sorted(cv.DATES)
    bars = pq.read_table(SOURCE, columns=['symbol','trade_date','close','amount','source']).to_pandas(categories=['symbol','source'])
    assert bars.source.notna().all() and bars.source.astype('string').str.strip().ne('').all()
    pieces=[]
    for sid, g in bars.groupby('symbol', observed=True, sort=True):
        z=cv.prior_liquidity20(g);z.insert(0,'sid',str(sid));pieces.append(z)
    liquidity=pd.concat(pieces, ignore_index=True)
    assert len(liquidity)==38619
    del bars, pieces
    out=cv.candidate_view(features, liquidity)
    assert len(out)==38619 and out.sid.nunique()==5517
    liquidity.to_parquet(HERE/'LIQUIDITY20.parquet',index=False,compression='zstd')
    out.to_parquet(HERE/'NO_CAP_RESEARCH_CANDIDATES.parquet',index=False,compression='zstd')

    # Comparator only: no snapshot field is ever an input to candidate_view.
    r=pd.DataFrame(json.loads(ROSTER.read_text())).rename(columns={'symbol':'sid'})
    assert not r.sid.duplicated().any()
    r=r[['sid','name','cap_cny','cap_observed_at']].rename(columns={'name':'current_name_annotation','cap_cny':'snapshot_2026_cap_cny'})
    current_names=pd.read_parquet(RANKS,columns=['sid','day','scope','current_name','in_old1709_exact'])
    current_names=current_names.loc[current_names.scope.eq('FULL_LOCAL')].drop(columns='scope')
    assert len(current_names)==38619 and not current_names.duplicated(['sid','day']).any()
    compare=out.merge(r,on='sid',how='left',validate='many_to_one',indicator='current_roster_join')
    compare=compare.merge(current_names,on=['sid','day'],validate='one_to_one')
    compare['current_name_annotation']=compare.current_name_annotation.fillna(compare.current_name)
    compare['snapshot_cap_status']=np.select(
        [compare.current_roster_join.eq('left_only'), compare.snapshot_2026_cap_cny.isna(), compare.snapshot_2026_cap_cny.gt(10_000_000_000)],
        ['MISSING_CURRENT_ROSTER','UNKNOWN_CURRENT_CAP','CURRENT_CAP_GT10BN'],default='CURRENT_CAP_NOT_GT10BN')
    q=pd.Series(pd.NA,index=compare.index,dtype='boolean')
    q.loc[compare.snapshot_cap_status.eq('CURRENT_CAP_GT10BN')]=True
    q.loc[compare.snapshot_cap_status.eq('CURRENT_CAP_NOT_GT10BN')]=False
    compare['snapshot_cap_q']=q
    compare['snapshot_cap_PVR_pool']=compare.research_no_cap_pool & q.eq(True).fillna(False)
    rank_subset(compare,'snapshot_cap_PVR_pool','snapshot_cap_PVR_rank')
    for _,g in compare.loc[compare.snapshot_cap_PVR_pool].groupby('day'):
        a=g.sort_values('no_cap_PVR_rank').sid.tolist();b=g.sort_values('snapshot_cap_PVR_rank').sid.tolist()
        assert a==b, 'relative order of retained stocks changed'
    assert np.array_equal(compare.score.to_numpy(float).view(np.uint64),out.score.to_numpy(float).view(np.uint64))
    compare.to_parquet(HERE/'SNAPSHOT_GATE_COMPARISON.parquet',index=False,compression='zstd')

    summaries=[]
    for day,g in compare.groupby('day',sort=True):
        pool=g.research_no_cap_pool
        summaries.append(dict(day=day,requested_series=len(g),observed_target_bars=int(g.target_row_present.sum()),
            missing_target_bars=int((~g.target_row_present).sum()),
            pvr_warmup_or_invalid_on_observed=int((g.target_row_present & ~pool).sum()),
            no_cap_PVR_pool=int(pool.sum()),snapshot_cap_PVR_pool=int(g.snapshot_cap_PVR_pool.sum()),
            additional_no_cap_PVR_candidates=int((pool & ~g.snapshot_cap_PVR_pool).sum()),
            pool_known_current_cap_false=int((pool & g.snapshot_cap_status.eq('CURRENT_CAP_NOT_GT10BN')).sum()),
            pool_current_cap_unknown=int((pool & g.snapshot_cap_status.eq('UNKNOWN_CURRENT_CAP')).sum()),
            pool_not_in_current_roster=int((pool & g.snapshot_cap_status.eq('MISSING_CURRENT_ROSTER')).sum()),
            prior20_known_all_observed=int(g.amount20_status.eq('KNOWN_PRIOR20_SOURCE_OBSERVATIONS').sum()),
            prior20_known_in_no_cap_pool=int((pool & g.amount20_status.eq('KNOWN_PRIOR20_SOURCE_OBSERVATIONS')).sum()),
            historical_legal_status_unknown_in_pool=int(pool.sum()),
            executable_eligibility_true=0))
    summary=pd.DataFrame(summaries);summary.to_csv(HERE/'SEVEN_DATE_COVERAGE.csv',index=False)
    top=[]
    for day,g in compare.groupby('day'):
        for view,rank in [('NO_FUTURE_CAP','no_cap_PVR_rank'),('CURRENT_2026_CAP_COMPARATOR','snapshot_cap_PVR_rank')]:
            z=g.loc[g[rank].le(20).fillna(False)].sort_values(rank).copy();z['view']=view;z['view_rank']=z[rank];top.append(z)
    top=pd.concat(top,ignore_index=True);assert len(top)==280
    top.to_csv(HERE/'TOP20_TWO_VIEWS.csv',index=False)
    named=compare.loc[compare.sid.isin(NAMES)].copy();assert len(named)==105
    named.to_csv(HERE/'NAMED_105_DATE_ROWS.csv',index=False)

    stock=pd.read_parquet(FIXED35)
    fields=['sid','day','e0_ready','e0_target','i_target','i_buy','g_grade','g_fresh_up','numeric_event',
            'stock_hold_signal','stock_fresh_core_signal','signal_status']
    fixed=compare.merge(stock[fields],on=['sid','day'],how='inner',validate='one_to_one')
    assert len(fixed)==35
    assert fixed.research_no_cap_pool.all()
    fixed['fresh_no_cap']=fixed.stock_fresh_core_signal.eq(True)
    fixed['fresh_current_cap_comparator']=fixed.fresh_no_cap & fixed.snapshot_cap_q.eq(True).fillna(False)
    fixed['hold_no_cap']=fixed.stock_hold_signal.eq(True)
    fixed['hold_current_cap_comparator']=fixed.hold_no_cap & fixed.snapshot_cap_q.eq(True).fillna(False)
    for flag in ['fresh_no_cap','fresh_current_cap_comparator','hold_no_cap','hold_current_cap_comparator']:
        rank_subset(fixed,flag,flag+'_rank_within_fixed35')
    fixed=fixed.sort_values('no_cap_PVR_rank')
    fixed.to_csv(HERE/'FIXED35_SIGNAL_COMPARISON.csv',index=False)
    fixed.to_parquet(HERE/'FIXED35_SIGNAL_COMPARISON.parquet',index=False,compression='zstd')
    fixed_summary={k:int(fixed[k].sum()) for k in ['fresh_no_cap','fresh_current_cap_comparator','hold_no_cap','hold_current_cap_comparator']}
    fixed_summary.update(rows=35,day='2024-09-24',no_cap_all_PVR=35,current_cap_PVR=int(fixed.snapshot_cap_PVR_pool.sum()),
        additional_fresh=int((fixed.fresh_no_cap & ~fixed.fresh_current_cap_comparator).sum()),
        global_signal_qualified_pool_computed=False)
    save('FIXED35_SUMMARY.json',fixed_summary)
    retired=pd.read_csv(ENTRY/'local_observable_selection_v1/coverage_audit/DAILY_COVERAGE.csv')
    retired.to_csv(HERE/'SEPARATE_RETIRED239_OBSERVED_COVERAGE.csv',index=False)
    for p in source_paths:
        z=before[str(p)];assert p.stat().st_size==z['bytes'] and p.stat().st_mtime_ns==z['mtime_ns'],('source changed',str(p))
    outputs={p.name:sha(p) for p in HERE.iterdir() if p.is_file() and p.suffix in ['.parquet','.csv','.json'] and p.name!='COMPLETION.json'}
    save('COMPLETION.json',dict(status='COMPLETE_BOUNDED_NO_FUTURE_CAP_RESEARCH_VIEW',rows=len(out),symbols=5517,dates=cv.DATES,
        coverage=summaries,fixed35=fixed_summary,score_bits_unchanged=True,retained_pair_order_unchanged=True,
        liquidity_no_threshold_no_rank_weight=True,account_or_new_market_model_calls=0,network_calls=0,
        source_inputs=before,outputs=outputs,elapsed_seconds=time.monotonic()-started,
        caveats=['Not full historical all-A/PIT; canonical survivor/provider mother and239retired separate.',
                 'Historical listing/ST/halt/limit status unknown; no executable permission.',
                 'Global E0/I/sector/H1/CP gates not recomputed; fixed35 only.',
                 'Native amount feature not marketcap, order capacity, or tradability proof.',
                 'Qfq factor vintage and daily bar publication time not PIT certified.']))
    print(summary.to_string(index=False),flush=True)
    print(json.dumps(fixed_summary,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
