"""Four source/clock comparisons using the original pure PVR function only."""
from pathlib import Path
import ast,hashlib,json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;BASE=HERE.parent
CAN=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
META=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
FORMULA=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-current-v3-information-capital-20261101/original_score_function.py')
CACHE=BASE.parent/'pvr_information_v1/export/features.parquet'
SIDS=['000620.SZ','002583.SZ','300085.SZ','300666.SZ']
DATES=['2022-01-10','2022-01-24','2024-09-24','2024-10-08','2026-01-15','2026-01-20','2026-05-15']
COLS=['r','scale','amount_ref','u','b','e','E','score']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def scalar(v):return None if pd.isna(v)else float(v)
def clock(f):
    good=np.isfinite(f.close)&(f.close>0)&np.isfinite(f.amount)&(f.amount>0)
    for c in ['price_eligible','observed_bar','is_observed_bar']:
        if c in f:good&=f[c].fillna(False).astype(bool)
    for c in ['source_invalid','synthetic_event_bar']:
        if c in f:good&=~f[c].fillna(True).astype(bool)
    block=((~good)|(~good.shift(fill_value=False))|f.segment_id.ne(f.segment_id.shift())).cumsum()
    return good,block
def recent(f,day):
    valid,block=clock(f);t=pd.Timestamp(day)
    if t not in f.index or not valid.loc[t]:return f.iloc[:0]
    return f.loc[(f.index<=t)&valid&block.eq(block.loc[t])].tail(85)
def main():
    env={'pd':pd,'np':np};text=FORMULA.read_text();assert hashlib.sha256(text.encode()).hexdigest()=='9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
    exec(compile(text,str(FORMULA),'exec'),env);score=env['score']
    canonical=pd.read_parquet(CAN,filters=[('symbol','in',SIDS),('trade_date','<=',pd.Timestamp(DATES[-1]))])
    cache=pd.read_parquet(CACHE,columns=['window','day','sid',*COLS]);cache=cache[cache.sid.isin(SIDS)&cache.day.isin(DATES)]
    assert len(cache)==28 and not cache.duplicated(['sid','day']).any()
    metas={r['symbol']:r for r in json.loads(META.read_text())};rows=[];summaries=[];bindings={}
    for sid in SIDS:
        c=canonical[canonical.symbol.eq(sid)].sort_values('trade_date').set_index('trade_date').copy();c['segment_id']=0
        assert c.source.eq('tushare').all()and c.adjustment_type.eq('qfq').all()
        op=Path(next(p for p in metas[sid]['source_sha256']if p.endswith('/signal.parquet')));bindings[str(op)]=sha(op);assert bindings[str(op)]==metas[sid]['source_sha256'][str(op)]
        o=pd.read_parquet(op).loc[:DATES[-1]].copy();o.index=pd.DatetimeIndex(o.index).tz_localize(None).normalize()
        cn=score(c);on=score(o);sidrows=[]
        for d in DATES:
            t=pd.Timestamp(d);oldcache=cache[(cache.sid==sid)&cache.day.eq(d)].iloc[0]
            row=dict(sid=sid,day=d,canonical_present=t in c.index,legacy_present=t in o.index)
            if t not in c.index or t not in o.index:rows.append(row);continue
            row.update(canonical_C=float(c.at[t,'close']),legacy_C=float(o.at[t,'close']),price_ratio=float(c.at[t,'close']/o.at[t,'close']),canonical_amount=float(c.at[t,'amount']),legacy_amount=float(o.at[t,'amount']),amount_ratio=float(c.at[t,'amount']/o.at[t,'amount']),reference_trade_date=str(c.at[t,'reference_trade_date'].date()))
            for name in COLS:
                a=float(cn.at[t,name]);b=float(on.at[t,name]);k=float(oldcache[name])
                assert np.isfinite(b)==np.isfinite(k)
                if np.isfinite(b):assert np.asarray([b],float).view(np.uint64)[0]==np.asarray([k],float).view(np.uint64)[0],(sid,d,name,'legacy-to-cache mismatch')
                row.update({name+'_canonical':scalar(a),name+'_legacy':scalar(b),name+'_old_cache':scalar(k),name+'_delta_canonical_minus_cache':scalar(a-k)})
            cr=recent(c,d);orr=recent(o,d);common=cr.index.intersection(orr.index)
            ratios=c.loc[common,'close']/o.loc[common,'close'];am=c.loc[common,'amount']/o.loc[common,'amount']
            row.update(canonical_recent85_n=len(cr),legacy_recent85_n=len(orr),recent85_dates_exact=cr.index.equals(orr.index),recent85_common_n=len(common),
                canonical_recent85_first=None if cr.empty else str(cr.index[0].date()),legacy_recent85_first=None if orr.empty else str(orr.index[0].date()),
                recent85_price_ratio_min=None if ratios.empty else float(ratios.min()),recent85_price_ratio_max=None if ratios.empty else float(ratios.max()),
                recent85_price_ratio_relative_range=None if ratios.empty else float(ratios.max()/ratios.min()-1),
                recent85_amount_ratio_min=None if am.empty else float(am.min()),recent85_amount_ratio_max=None if am.empty else float(am.max()))
            sidrows.append(row);rows.append(row)
        summaries.append(dict(sid=sid,canonical_source_rows=len(c),legacy_source_rows=len(o),points=len(sidrows),all_recent85_dates_equal=all(r['recent85_dates_exact']for r in sidrows),
            max_abs_e_difference=max(abs(r['e_delta_canonical_minus_cache'])for r in sidrows),max_abs_score_difference=max(abs(r['score_delta_canonical_minus_cache'])for r in sidrows),
            max_recent85_price_ratio_relative_range=max(r['recent85_price_ratio_relative_range']for r in sidrows)))
    HERE.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(HERE/'FOUR_SOURCE_28_POINTS.csv',index=False)
    paths=[CAN,META,FORMULA,CACHE,BASE/'FREEZE.json',BASE/'features/derive.py',BASE/'features/export_once.py',Path(__file__)]
    result=dict(status='PASS_BOUNDED_FOUR_SOURCE_INPUT_CLOCK_AND_LEGACY_CACHE_COMPARISON_WITH_LIMITS',symbols=SIDS,fixed_dates=DATES,points=len(rows),
        pure_original_PVR_indicator_calculations=8,original_legacy_cache_28points_eight_fields_bitexact=True,summary=summaries,
        interpretation=['Canonical source=tushare/qfq; old financial prepared signal identified only by bound manifest/path, no unsupported provider alias','Constant per-stock positive price scale and constant amount unit rescale cancel analytically in the PVR formula; binary arithmetic may differ','Nonconstant adjustment ratios or different observation/reset windows can legitimately produce different canonical indicators; do not force old-cache equality','qfq reference date is terminal metadata, not historical publication-vintage certification','This is a local score universe, not original pending/E0I/CP/industry admission or tradability'],
        limits=['Only4stocks7dates; no global5517 source equivalence assertion','Original pure function reference on canonical inputs is not a strategy/account run','No H1 fabricated, no forward labels or future-performance stock selection','Final feature-export values/prefix receipts and top20 main output still pending separate audit'],new_accounts=0,network_calls=0,refreshes=0,
        source_sha256={str(p.resolve()):sha(p)for p in paths}|bindings)
    out=HERE/'FOUR_SOURCE_COMPARISON_AUDIT.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'summary':summaries},ensure_ascii=False));print('AUDIT_SHA',sha(out))

if __name__=='__main__':main()
