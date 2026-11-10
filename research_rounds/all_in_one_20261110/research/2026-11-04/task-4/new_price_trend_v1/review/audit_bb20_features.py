"""Independent bounded scalar audit of saved BB features; no accounts/imported engine."""
from pathlib import Path
import hashlib, json, math, pickle, statistics, time
import pandas as pd

O=Path(__file__).resolve().parents[1]
R=Path(__file__).resolve().parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def scalar(f):
    history=[]; previous_segment=None; previous_upper=None; previous_close=None
    out=[]
    for day,row in f.iterrows():
        c=float(row.close); segment=row.segment_id
        valid=math.isfinite(c) and c>0 and pd.notna(segment)
        same=valid and previous_segment is not None and segment==previous_segment
        if not same:
            history=[]; previous_upper=None; previous_close=None
        upper=(statistics.fmean(history[-20:])+2*statistics.pstdev(history[-20:])) if len(history)>=20 else None
        known=valid and upper is not None and previous_close is not None and previous_upper is not None
        cross=known and c>upper and previous_close<=previous_upper
        out.append(dict(day=str(day.date()),known=bool(known),cross=bool(cross),upper=upper))
        if valid:
            history.append(c);previous_close=c;previous_upper=upper;previous_segment=segment
        else:
            history=[];previous_close=None;previous_upper=None;previous_segment=None
    return out

def main():
    start=time.monotonic();records=json.loads(M.read_text());saved=pickle.loads((O/'PRICE_FEATURES.pkl').read_bytes())
    manifest=json.loads((O/'PRICE_FEATURE_MANIFEST.json').read_text())
    assert sha(O/'PRICE_FEATURES.pkl')==manifest['output_sha256']
    assert set(saved)=={r['symbol'] for r in records} and len(saved)==1709
    assert sum(len(v) for v in saved.values())==manifest['rows']==1731880
    chosen={'002151.SZ','300623.SZ','688362.SH','600584.SH'} | {records[i]['symbol'] for i in [0,400,800,1200,1708]}
    checks=[];total=0;known=0;crosses=0;maximum_error=0.;sources={str(M):sha(M),str(O/'PROTOCOL.txt'):sha(O/'PROTOCOL.txt'),str(O/'build_price_features.py'):sha(O/'build_price_features.py'),str(O/'PRICE_FEATURE_MANIFEST.json'):sha(O/'PRICE_FEATURE_MANIFEST.json')}
    for r in records:
        z=saved[r['symbol']]
        assert z.index.is_unique and z.index.is_monotonic_increasing
        assert not (z.bb20_cross & ~z.bb20_cross_known).any()
        if r['symbol'] not in chosen:continue
        p=Path(r['refs']['facts']);sources[str(p)]=sha(p);assert sources[str(p)]==r['output_sha256'][str(p)]
        f=pd.read_parquet(p,columns=['close','segment_id']);s=scalar(f)
        by_day={v['day']:v for v in s};errors=[]
        for day,row in z.iterrows():
            v=by_day[str(day.date())]
            assert bool(row.bb20_cross_known)==v['known'],(r['symbol'],day,'known')
            assert bool(row.bb20_cross)==v['cross'],(r['symbol'],day,'cross',v)
            if v['upper'] is not None:
                err=abs(float(row.bb20_prior_upper)-v['upper']);errors.append(err)
                assert math.isclose(float(row.bb20_prior_upper),v['upper'],rel_tol=1e-10,abs_tol=1e-8),(r['symbol'],day,'upper',err)
        # Physical truncation evaluated by a distinct scalar implementation.
        for cut in ['2023-12-29','2024-09-30','2026-03-31']:
            truncated=scalar(f.loc[:cut]);assert truncated==s[:len(truncated)]
        k=sum(v['known'] for v in s if '2022-01-01'<=v['day']<='2026-06-30')
        b=sum(v['cross'] for v in s if '2022-01-01'<=v['day']<='2026-06-30')
        total+=len(z);known+=k;crosses+=b;maximum_error=max(maximum_error,max(errors,default=0.))
        checks.append(dict(sid=r['symbol'],audited_rows=len(z),known=k,crosses=b,max_upper_abs_error=max(errors,default=0.),physical_prefix_checks=3))
    # Deliberately broken prices and source changes: each requires 22 fresh valid
    # same-source observations before the two-boundary crossing becomes known.
    idx=pd.date_range('2020-01-01',periods=75)
    synthetic=pd.DataFrame(dict(close=[10.+i*.03 for i in range(75)],segment_id=[1]*35+[2]*40),index=idx)
    synthetic.loc[idx[10],'close']=float('nan');synthetic.loc[idx[60],'close']=0.
    q=scalar(synthetic)
    assert [i for i,v in enumerate(q) if v['known']]==list(range(32,35))+list(range(56,60))
    result=dict(status='PASS_BOUNDED_FORMULA_AND_CLOCK',accounts=0,projection_runs=0,all_pool_saved_index_and_known_consistency=True,stocks=1709,rows=manifest['rows'],independent_scalar_stocks=len(checks),independent_scalar_rows=total,known=known,crosses=crosses,physical_prefix_checks=3*len(checks),synthetic_invalid_and_source_reset=True,max_upper_abs_error=maximum_error,checks=checks,source_sha256=sources,feature_manifest_seconds=manifest['seconds'],seconds=time.monotonic()-start,scope='Formula and saved features only; account adapter, OFF identity and economic admission are not evaluated here.')
    (R/'BB20_FEATURE_FORMULA_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['checks','source_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
