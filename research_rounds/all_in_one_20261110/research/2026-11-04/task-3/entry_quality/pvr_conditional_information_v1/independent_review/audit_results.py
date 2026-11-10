"""Audit saved conditional memberships, labels and weighted summaries only."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;BASE=HERE.parent;PRE=BASE/'prepared';OUT=BASE/'results'
KEY=['window','day','sid'];CELL=['window','day','sector','sector_decile']
MET=['ret20_open','mfe20_open','mae20_open','ret20_close','mfe20_close','mae20_close']
FEAT={'RS20':'relative_return20','frontier':'close_gap_prior_high20','low_improvement':'low_improvement'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def period(s):return np.where(s<'2024-01-01','2022_23',np.where(s<'2025-01-01','2024','2025H2_2026H1'))
def compare(a,b,keys,cols):
    a=a.sort_values(keys).reset_index(drop=True);b=b.sort_values(keys).reset_index(drop=True)
    assert a[keys].equals(b[keys]),keys
    assert np.allclose(a[cols],b[cols],rtol=1e-10,atol=1e-12,equal_nan=True)

def main():
    prepared=json.loads((PRE/'COMPLETION_PRE_FUTURE_LABELS.json').read_text());complete=json.loads((OUT/'COMPLETION.json').read_text())
    assert prepared['status']=='MEMBERSHIP_FROZEN_BEFORE_LOADING_FUTURE_LABELS'
    assert complete['status']=='COMPLETE_FIXED_CONDITIONAL_DESCRIPTIVE_OBSERVATION'
    for n,h in prepared['outputs'].items():assert sha(PRE/n)==h,n
    oldscript=BASE/'conditional_saved_pre_global_metadata_fix.py.txt'
    assert sha(oldscript)==prepared['sources'][str((BASE/'conditional_saved.py').resolve())]
    for p,h in complete['sources'].items():assert sha(p)==h,p
    for n,h in complete['outputs'].items():assert sha(OUT/n)==h,n
    labelpath=BASE/'path20_labels/PATH20_LABELS.parquet';lr=json.loads((BASE/'path20_labels/RUN_RECEIPT.json').read_text())
    assert sha(labelpath)==lr['output_sha256']
    y=pd.read_parquet(labelpath);assert len(y)==133713 and not y.duplicated(KEY).any()
    good=y.path20_complete.to_numpy(bool);assert good.sum()==128387
    assert np.array_equal(good,y.path20_status.eq('KNOWN'))
    assert np.array_equal(good,y.h20_status.eq('KNOWN')&y.path20_shared_sessions_available.eq(20)&y.path20_known_comparable_close_count.eq(20))
    assert y.loc[~good,MET].isna().all().all()
    path=np.vstack(y.loc[good,'path20_close_values'].to_numpy());assert path.shape==(128387,20)
    assert np.isfinite(path).all()and(path>0).all()
    for suffix,denom in [('open',y.loc[good,'path20_next_OPEN_reference'].to_numpy(float)),('close',y.loc[good,'path20_current_CLOSE_reference'].to_numpy(float))]:
        assert np.isfinite(denom).all()and(denom>0).all()
        for name,value in [('ret20',path[:,-1]),('mfe20',path.max(axis=1)),('mae20',path.min(axis=1))]:
            assert np.allclose(y.loc[good,name+'_'+suffix],value/denom-1,rtol=1e-12,atol=1e-12)
    assert (y.loc[good,'mfe20_open']<0).sum()==18867
    assert (y.loc[good,'mae20_open']>0).sum()==14938
    originalmanifest=BASE.parent/'pvr_information_v1/export/FEATURE_MANIFEST_PRE_LABEL.json'
    calendars=json.loads(originalmanifest.read_text())['calendars']
    for window,g in y.loc[good].groupby('window'):
        dates=calendars[window];where={d:j for j,d in enumerate(dates)}
        for r in g[['day','path20_close_days','path20_terminal_shared_day']].itertuples(index=False):
            j=where[r.day];assert list(r.path20_close_days)==dates[j+1:j+21] and r.path20_terminal_shared_day==dates[j+20]
    # Nine deterministic original signal-price samples; no indicator execution.
    metas={r['symbol']:r for r in json.loads(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
    yy=y.loc[good].copy();yy['period']=period(yy.day);samples=[];raw_sources={}
    for p,g in yy.groupby('period'):
        ordered=g.sort_values(['day','sid'])
        for pos in [0,len(ordered)//2,len(ordered)-1]:
            r=ordered.iloc[pos];meta=metas[r.sid];source=Path(next(k for k in meta['source_sha256']if k.endswith('/signal.parquet')))
            if str(source)not in raw_sources:
                raw_sources[str(source)]=sha(source);assert raw_sources[str(source)]==meta['source_sha256'][str(source)]
            dates=[r.day,*list(r.path20_close_days)]
            f=pd.read_parquet(source,filters=[('date','>=',pd.Timestamp(dates[0])),('date','<=',pd.Timestamp(dates[-1]))])
            f.index=pd.DatetimeIndex(f.index).tz_localize(None).normalize();v=f.reindex(pd.DatetimeIndex(dates))
            assert v.close.notna().all()and np.isfinite(v.close).all()and(v.close>0).all()
            assert v.segment_id.notna().all()and v.segment_id.nunique()==1
            for c in ['price_eligible','observed_bar','is_observed_bar']:
                if c in v:assert v[c].fillna(False).astype(bool).all()
            for c in ['source_invalid','synthetic_event_bar']:
                if c in v:assert not v[c].fillna(True).astype(bool).any()
            assert np.array_equal(v.close.to_numpy(float)[1:],np.asarray(r.path20_close_values,float))
            assert v.close.iloc[0]==r.path20_current_CLOSE_reference and v.open.iloc[1]==r.path20_next_OPEN_reference
            samples.append(dict(period=p,sid=r.sid,decision_day=r.day,terminal_day=dates[-1],twenty_shared_close_rows_exact=True,source=str(source)))
    a=pd.read_parquet(PRE/'sector_MEMBERSHIP_PRE_LABEL.parquet');assert len(a)==49612
    assert not a.duplicated(KEY).any()
    for tag,col in FEAT.items():
        expected=np.sign(a[col]-a.groupby(CELL)[col].transform('median'))
        assert np.array_equal(expected.to_numpy(),a[tag+'_arm'].to_numpy(),equal_nan=True)
    a=a.merge(y[KEY+['path20_complete']+MET],on=KEY,validate='one_to_one')
    validcells=a.groupby(CELL).path20_complete.all()
    savedfunnel=pd.read_parquet(OUT/'COMPLETE_CELL_COVERAGE.parquet')
    sectorfunnel=savedfunnel[savedfunnel.scope=='sector']
    deltas=[];coverage=[]
    sourcecells=pd.read_parquet(PRE/'SOURCE_CELL_COVERAGE.parquet')
    for tag,col in FEAT.items():
        c=sourcecells[(sourcecells.scope=='sector')&(sourcecells.feature==tag)].copy().set_index(CELL)
        c['entire_cell_future_complete']=validcells;c['evaluable']=c.paired_source&c.entire_cell_future_complete
        got=sectorfunnel[sectorfunnel.feature==tag].set_index(CELL)
        assert c['evaluable'].sort_index().equals(got['evaluable'].sort_index())
        allowed=c[c.evaluable].reset_index()[CELL];z=a.merge(allowed,on=CELL,validate='many_to_one')
        cols=MET+['score','PVR_percentile']
        high=z[z[tag+'_arm']==1].groupby(CELL)[cols].mean();low=z[z[tag+'_arm']==-1].groupby(CELL)[cols].mean()
        d=(high-low).add_prefix('delta_').reset_index();d['feature']=tag;d['period']=period(d.day);deltas.append(d)
        for p,g in c.reset_index().groupby('period'):
            ok=g[g.evaluable]
            coverage.append(dict(period=p,feature=tag,cells=len(ok),arm_rows=int((ok.n_high+ok.n_low).sum()),days=ok.day.nunique(),sector_dates=ok[['window','day','sector']].drop_duplicates().shape[0]))
    d=pd.concat(deltas,ignore_index=True);metrics=['delta_'+m for m in MET]+['delta_score','delta_PVR_percentile']
    stored=pd.read_parquet(OUT/'EVALUABLE_CELL_DELTAS.parquet')
    compare(d,stored,CELL+['feature'],metrics)
    sd=d.groupby(['period','window','day','sector','feature'])[metrics].mean().reset_index()
    compare(sd,pd.read_parquet(OUT/'SECTOR_DATE_EQUAL_CELL_DELTAS.parquet'),['period','window','day','sector','feature'],metrics)
    daily=sd.groupby(['period','window','day','feature'])[metrics].mean().reset_index()
    compare(daily,pd.read_csv(OUT/'DAY_EQUAL_SECTOR_DELTAS.csv'),['period','window','day','feature'],metrics)
    summary=pd.read_csv(OUT/'PERIOD_CONDITIONAL_SUMMARY.csv');keyresults=[]
    for(p,tag),g in daily.groupby(['period','feature']):
        sub=sd[(sd.period==p)&(sd.feature==tag)]
        for m in metrics:
            row=summary[(summary.period==p)&(summary.feature==tag)&(summary.metric==m)].iloc[0]
            assert row.dates==len(g)and row.sector_dates==len(sub)and row.industries==sub.sector.nunique()
            for k,v in [('day_equal_mean_delta',g[m].mean()),('day_equal_median_delta',g[m].median()),('positive_date_fraction',g[m].gt(0).mean()),('sector_date_mean_delta',sub[m].mean())]:
                assert np.isclose(row[k],v,rtol=1e-10,atol=1e-12)
        if tag=='RS20':keyresults.append(dict(period=p,ret20_open_mean_pp=100*g.delta_ret20_open.mean(),mfe20_open_mean_pp=100*g.delta_mfe20_open.mean(),mae20_open_mean_pp=100*g.delta_mae20_open.mean(),raw_PVR_score_imbalance=g.delta_score.mean()))
    calendar=pd.DataFrame([dict(window=w,day=d,block20=j//20)for w,ds in calendars.items()for j,d in enumerate(ds)])
    blocks=daily.merge(calendar,on=['window','day'],validate='many_to_one').groupby(['period','window','block20','feature'])[metrics].mean().reset_index()
    compare(blocks,pd.read_csv(OUT/'FIXED20_SESSION_BLOCK_DELTAS.csv'),['period','window','block20','feature'],metrics)
    bs=pd.read_csv(OUT/'FIXED20_SESSION_BLOCK_SUMMARY.csv')
    for(p,tag),g in blocks.groupby(['period','feature']):
        for m in metrics:
            row=bs[(bs.period==p)&(bs.feature==tag)&(bs.metric==m)].iloc[0]
            assert row.blocks==len(g)and row.positive_blocks==int(g[m].gt(0).sum())and row.negative_blocks==int(g[m].lt(0).sum())
    dec=d.groupby(['period','window','day','sector_decile','feature'])[metrics].mean().groupby(['period','sector_decile','feature']).mean().reset_index()
    compare(dec,pd.read_csv(OUT/'PER_DECILE_DAY_EQUAL_SUMMARY.csv'),['period','sector_decile','feature'],metrics)
    fcsv=pd.read_csv(OUT/'COVERAGE_FUNNEL.csv');assert fcsv.loc[fcsv.scope=='market','eval_sector_dates'].isna().all()
    for r in coverage:
        row=fcsv[(fcsv.scope=='sector')&(fcsv.period==r['period'])&(fcsv.feature==r['feature'])].iloc[0]
        for field,col in [('cells','eval_cells'),('arm_rows','eval_arm_rows'),('days','eval_dates'),('sector_dates','eval_sector_dates')]:assert r[field]==row[col]
    paths=[BASE/'FREEZE.json',BASE/'conditional_saved.py',oldscript,BASE/'GLOBAL_METADATA_CLARIFICATION.json',PRE/'COMPLETION_PRE_FUTURE_LABELS.json',OUT/'COMPLETION.json',labelpath,BASE/'path20_labels/RUN_RECEIPT.json',BASE/'path20_labels/export_path20.py',BASE/'path20_labels/add_schema_aliases.py',OUT/'PERIOD_CONDITIONAL_SUMMARY.csv',OUT/'COVERAGE_FUNNEL.csv',HERE/'PRELABEL_COVERAGE_AUDIT.json',Path(__file__)]
    result=dict(status='PASS_BOUNDED_COMPLETE_PATH_CELLS_AND_EQUAL_WEIGHT_CONDITIONAL_RESULTS_WITH_LIMITS',original_rows=133713,complete20_path_rows=128387,
        legacy_known_rejected_for_internal_missing=495,all_saved128387_paths_six_metric_arithmetic_and20shared_dates_checked=True,
        original_signal_source_samples=samples,original_signal_source_sample_count=len(samples),prelabel_membership_SHA_unchanged=True,
        all_sector_cell_medians_arms_and_entire_cell_complete_masks_checked=True,four_level_equal_weight_aggregation_checked=True,calendar_block_means_signs_and_per_decile_summary_checked=True,
        market_scope_no_future_performance_by_static_source=True,market_sector_date_placeholder_corrected_to_null=True,
        sector_coverage=coverage,RS20_results=keyresults,
        limits=['Sourceprice exact samples9, not all133713 original histories reconstructed','Signed max/min are close-reference path extrema, not executable prices or portfolio returns','Same PVR decile retains rawPVR/pct imbalance; no independent incremental alpha proof','Complete-cell selection and large-sector coverage are selective; sparse cases not explained','Overlapping20horizons, repeated stocks and industries are dependent; block direction notIID inference','Static universe and sector map nonPIT, original pending pools depend on old account path'],
        remaining_blocks_for_reviewed_scope=[],new_accounts=0,new_price_models=0,new_residual_or_composite_scores=0,source_sha256={str(p.resolve()):sha(p)for p in paths}|raw_sources)
    out=HERE/'CONDITIONAL_RESULT_AUDIT.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['status','complete20_path_rows','legacy_known_rejected_for_internal_missing','original_signal_source_sample_count','RS20_results']},ensure_ascii=False));print('AUDIT_SHA256',sha(out))

if __name__=='__main__':main()
