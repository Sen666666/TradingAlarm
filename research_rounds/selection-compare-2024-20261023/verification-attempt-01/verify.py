"""Independent final identity, price-coordinate and frozen-order audit."""
import collections,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import pandas as pd
from study import HERE,ROOT,sha,dump,bridge

prot=json.loads((HERE/'freeze.json').read_text())
assert all(sha(p)==h for p,h in prot['code'].items())
assert sha(HERE/'universe.csv')==prot['universe_sha256']
stock_checks=0;endpoint_checks=0
for p in sorted((HERE/'daily').glob('*.parquet')):
    f=pd.read_parquet(p);assert f.index.is_unique and f.index.is_monotonic_increasing
    assert f.index.min()>=pd.Timestamp('2024-01-01') and f.index.max()<=pd.Timestamp('2024-12-31')
    assert np.allclose(f.close,f.raw_close*f.adjustment_factor,rtol=1e-12,atol=1e-12)
    a=f.loc[f.own_target.eq(1)];assert (a.close>a.own_floor).all()
    b=f.loc[f.chan_up.eq(1)];assert (b.low>=b.chan_floor).all()
    e=f.chan_endpoint.dropna();e=e.loc[e.ne('')]
    if len(e):assert (pd.to_datetime(e)<=e.index).all();endpoint_checks+=len(e)
    stock_checks+=1
d=pd.read_csv(HERE/'daily-candidates.csv',usecols=['date','method','sector_id','symbol','rs','sector_rank','stock_rank'],dtype={'symbol':str})
stock_groups=0;fallbacks=0
for (dt,m,g),f in d.groupby(['date','method','sector_id'],sort=False):
    scores={s:(None if pd.isna(v) else float(np.round(v,12))) for s,v in zip(f.symbol,f.rs)}
    ff=[];expected=bridge.admission._ordered(f.symbol.tolist(),scores,'audit',ff)
    assert expected==f.sort_values('stock_rank').symbol.tolist(),(dt,m,g)
    stock_groups+=1;fallbacks+=bool(ff)
s=pd.read_csv(HERE/'sector-daily.csv').set_index(['date','sector_id'])
sector_groups=0
for (dt,m),f in d.groupby(['date','method'],sort=False):
    r=f[['sector_id','sector_rank']].drop_duplicates()
    scores={g:float(np.round(s.at[(dt,g),'rs'],12)) for g in r.sector_id}
    expected=bridge.admission._ordered(r.sector_id.tolist(),scores,'audit',[])
    assert expected==r.sort_values('sector_rank').sector_id.tolist();sector_groups+=1
assert fallbacks==8556
x=ROOT/'outputs/selection-compare-2024-20261023/2024选股对照.xlsx'
assert sha(x)==sha(HERE/'downloads/2024选股对照.xlsx')
z=zipfile.ZipFile(x);ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};sheets=[]
for i,n in [(1,96),(2,4250),(3,1089),(4,1428)]:
    r=ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'));rs=r.findall('m:sheetData/m:row',ns)
    # first worksheet has 70 rather than 72 examples when fewer than three sectors pass.
    actual=int(rs[-1].attrib['r']);assert actual==n,(i,actual,n)
    assert r.find('m:sheetViews/m:sheetView/m:pane',ns) is not None
    sheets.append(dict(sheet=i,last_row=actual))
dump(HERE/'final-verification.json',dict(code_unchanged=True,stocks_checked=stock_checks,stock_rank_groups=stock_groups,
    sector_rank_groups=sector_groups,code_fallback_groups=fallbacks,endpoint_recognition_observations=endpoint_checks,
    raw_price_coordinate_checks=True,active_support_checks=True,workbook_sheets=sheets,output_sha256=sha(x),output_bytes=x.stat().st_size,
    output_reconciliation=json.loads((HERE/'analysis-complete.json').read_text())['summary'],
    artifacts={p.name:sha(p) for p in [HERE/'index.html',HERE/'study.py',HERE/'analyze.py',HERE/'report.mjs',HERE/'workbook.mjs']}))
print((HERE/'final-verification.json').read_text())
