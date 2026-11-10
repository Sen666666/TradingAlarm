"""Three prechosen maximal cross-source differences, not future outcomes."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from compare_four_sources import clock,recent,FORMULA,CAN,META,COLS,sha

HERE=Path(__file__).resolve().parent;BASE=HERE.parent
LEGACY=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/input-manifest.json')
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
    if isinstance(v,list):return [clean(x)for x in v]
    if isinstance(v,pd.Timestamp):return str(v.date())
    if hasattr(v,'item'):return clean(v.item())
    if isinstance(v,float)and not np.isfinite(v):return None
    return v
def main():
    table=BASE/'cache_comparison/ALL_EXACT_OLD_SYMBOL_DATE_COMPARISONS.csv';comparisons=pd.read_csv(table);comparisons['year']=comparisons.day.str[:4]
    selected=comparisons.loc[comparisons.groupby('year').score_abs_difference.idxmax()]
    assert set(zip(selected.sid,selected.day))=={('300620.SZ','2022-01-24'),('600032.SH','2024-09-24'),('002458.SZ','2026-05-15')}
    env={'pd':pd,'np':np};exec(compile(FORMULA.read_text(),str(FORMULA),'exec'),env);score=env['score']
    metas={r['symbol']:r for r in json.loads(META.read_text())};manifest={r['series_id']:r for r in json.loads(LEGACY.read_text())['series']}
    exported=pd.read_parquet(BASE/'features/LOCAL_FIXED_DATE_FEATURES.parquet');oldcache=pd.read_parquet(BASE.parent/'pvr_information_v1/export/features.parquet',columns=['sid','day',*COLS])
    details=[];windows=[];bindings={}
    for rr in selected.itertuples():
        sid,day=rr.sid,rr.day;t=pd.Timestamp(day)
        c=pd.read_parquet(CAN,filters=[('symbol','==',sid),('trade_date','<=',t)]).set_index('trade_date');c['segment_id']=0
        op=Path(next(k for k in metas[sid]['source_sha256']if k.endswith('/signal.parquet')));bindings[str(op)]=sha(op);assert bindings[str(op)]==metas[sid]['source_sha256'][str(op)]
        o=pd.read_parquet(op).loc[:day];o.index=pd.DatetimeIndex(o.index).tz_localize(None).normalize()
        cn=score(c);on=score(o);nr=exported[(exported.sid==sid)&exported.day.eq(day)].iloc[0];oc=oldcache[(oldcache.sid==sid)&oldcache.day.eq(day)].iloc[0]
        for f in COLS:
            assert np.asarray([cn.at[t,f]],float).view(np.uint64)[0]==np.asarray([nr[f]],float).view(np.uint64)[0],(sid,f,'new formula')
            assert np.asarray([on.at[t,f]],float).view(np.uint64)[0]==np.asarray([oc[f]],float).view(np.uint64)[0],(sid,f,'old formula')
        cr=recent(c,day);old=recent(o,day);same=cr.index.equals(old.index);common=cr.index.intersection(old.index)
        w=pd.DataFrame(index=common)
        w['sid']=sid;w['target_day']=day;w['canonical_C']=c.loc[common,'close'];w['legacy_C']=o.loc[common,'close'];w['price_ratio']=w.canonical_C/w.legacy_C
        w['canonical_raw_reconstructed']=c.loc[common,'close']/c.loc[common,'adjustment_factor'];w['legacy_raw_C']=o.loc[common,'raw_close']
        w['canonical_amount']=c.loc[common,'amount'];w['legacy_amount']=o.loc[common,'amount'];w['amount_ratio']=w.canonical_amount/w.legacy_amount
        w['canonical_raw_adjfactor']=c.loc[common,'raw_adjustment_factor'];w['legacy_signal_factor']=o.loc[common,'adjustment_factor']
        for f in ['r','scale','e']:
            w[f+'_canonical']=cn.loc[common,f];w[f+'_legacy']=on.loc[common,f];w[f+'_difference']=w[f+'_canonical']-w[f+'_legacy']
        for f in ['price_eligible','observed_bar','source_invalid','synthetic_event_bar','segment_id']:
            if f in o:w['legacy_'+f]=o.loc[common,f]
        action_ref=manifest[sid]['adjustment']['actions'];ap=Path(action_ref['path']);assert sha(ap)==action_ref['sha256'];bindings[str(ap)]=sha(ap)
        action=json.loads(ap.read_text());events=[z for z in action['events']if str(common[0].date())<=z['effective_date']<=day]
        factorchanges=[]
        cfull=c.copy();ofull=o.copy();joined=cfull[['raw_adjustment_factor']].join(ofull[['adjustment_factor']],how='inner');factor_ratio=joined.raw_adjustment_factor/joined.adjustment_factor
        # Source factor-ratio changes, no threshold fitted: log differences recorded at source CA days.
        for event in events:
            et=pd.Timestamp(event['effective_date'])
            if et not in joined.index:continue
            ci=c.index.get_loc(et);oi=o.index.get_loc(et)
            if ci<1 or oi<1:continue
            factorchanges.append(dict(day=event['effective_date'],canonical_raw_adj_jump=float(c.raw_adjustment_factor.iloc[ci]/c.raw_adjustment_factor.iloc[ci-1]),legacy_signal_factor_jump=float(o.adjustment_factor.iloc[oi]/o.adjustment_factor.iloc[oi-1]),source_event=event))
        if same:
            last=common[-21:];de=cn.loc[last,'e'].to_numpy()-on.loc[last,'e'].to_numpy();weights=.9**np.arange(20,-1,-1);weights/=weights.sum();contrib=de*weights
            assert np.isclose(contrib.sum(),cn.at[t,'E']-on.at[t,'E'],rtol=0,atol=1e-15)
            maxcontrib=dict(day=str(last[np.abs(contrib).argmax()].date()),weighted_e_difference=float(contrib[np.abs(contrib).argmax()]))
        else:maxcontrib=None
        details.append(dict(sid=sid,day=day,selection='Maximum saved finite score difference in fixed2022/2024/2026 year group; not future gain/loss selected',
            original_function_new_and_legacy_eight_fields_bitexact_to_their_own_outputs=True,
            new_score=float(cn.at[t,'score']),legacy_score=float(on.at[t,'score']),score_abs_difference=float(abs(cn.at[t,'score']-on.at[t,'score'])),
            recent85_dates_exact=same,canonical_recent85_n=len(cr),legacy_recent85_n=len(old),
            recent85_max_raw_close_difference=float((w.canonical_raw_reconstructed-w.legacy_raw_C).abs().max()),
            recent85_amount_ratio_min=float(w.amount_ratio.min()),recent85_amount_ratio_max=float(w.amount_ratio.max()),
            recent85_price_ratio_relative_range=float(w.price_ratio.max()/w.price_ratio.min()-1),
            legacy_validity=dict(price_eligible_all=bool(o.loc[common,'price_eligible'].all()),observed_all=bool(o.loc[common,'observed_bar'].all()),synthetic_count=int(o.loc[common,'synthetic_event_bar'].sum()),source_invalid_count=int(o.loc[common,'source_invalid'].sum()),segments=int(o.loc[common,'segment_id'].nunique())),
            source_kind_values=o.loc[common,'source_kind'].drop_duplicates().tolist(),amount_unit_values=o.loc[common,'amount_unit'].drop_duplicates().tolist(),
            factor_event_evidence=factorchanges,max_abs_weighted_e_contribution_in21=maxcontrib,
            scope_limit='Factor jump and documented CA coincide; raw closes/dates and amount scale checked. Provider-factor construction/publication correctness and economic CA truth not independently certified; do not repair either source.'))
        w.index.name='source_day';windows.append(w.reset_index())
    pd.concat(windows,ignore_index=True).to_csv(HERE/'THREE_MAX_DIFFERENCE_SOURCE_WINDOWS.csv',index=False)
    result=dict(status='PASS_BOUNDED_THREE_MAX_SOURCE_DIFFERENCE_EXPLANATION_WITH_UNKNOWNS',cases=details,
        pure_original_indicator_calculations=6,new_accounts=0,forward_labels_loaded=False,
        conclusion='Same pure PVR formula independently reproduces each source. Cross-source adjustment-factor changes explain numerical divergence on these matched clocks, not an implementation substitution. Vendor CA/factor truth remains unverified.',
        sources={str(p.resolve()):sha(p)for p in [CAN,FORMULA,META,LEGACY,table,BASE/'features/LOCAL_FIXED_DATE_FEATURES.parquet',Path(__file__)]}|bindings)
    out=HERE/'THREE_MAX_DIFFERENCE_AUDIT.json';out.write_text(json.dumps(clean(result),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(clean({'status':result['status'],'cases':[{k:r[k]for k in ['sid','day','score_abs_difference','recent85_dates_exact','recent85_max_raw_close_difference','recent85_price_ratio_relative_range','factor_event_evidence']}for r in details]}),ensure_ascii=False));print('SHA',sha(out))

if __name__=='__main__':main()
