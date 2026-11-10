"""Causal price-association groups; deliberately not historical industry membership."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from sector_factors import expanded_assets
OUT=Path('results/sector-stock-daily-mapping')

def associate(stock,proxies):
    corr=pd.DataFrame({s:stock.rolling(126,min_periods=100).corr(proxies[s]) for s in sorted(proxies)})
    # Positive correlations only; sorting provides deterministic ties.
    valid=corr.where(corr.gt(0));best=valid.max(axis=1)
    winner=valid.fillna(-np.inf).idxmax(axis=1).where(best.notna())
    return pd.DataFrame({'proxy':winner,'correlation':best})

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(window=126,min_observations=100,selection='Maximum positive past paired daily return correlation; deterministic alphabetical ties; no forward fill of prices or returns',scope='485 validated A shares versus 9 surviving A-listed sector ETFs,2024-2026Oct16',purpose='Mapping coverage and stability before stock portfolio experiment',common_move_control='Subtract equal-weight available nine ETF daily return from stock and each proxy; same126/100 association; diagnostic only, not beta-neutral or industry identification',limitations=['Price associations are not historical industry membership','Selected surviving stock/ETF sample; development data','No account return or tradable strategy claim'])
    p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==protocol
    p.write_text(json.dumps(protocol,indent=2))
    assets={s:a for s,a in expanded_assets().items() if a['kind']=='equity' and a['currency']=='CNY' and a['sector']!='broad_cn'}
    closes=pd.DataFrame({s:a['signal'].close.where(a['raw'].volume.gt(0)) for s,a in assets.items()}).sort_index()
    pr=closes.pct_change(fill_method=None);calendar=pr.index
    market=pr.mean(axis=1);relative_proxies=pr.sub(market,axis=0)
    root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text())
    rows=[];hashes={}
    for r in manifest['records']:
        p=root/f"{r['ths_symbol']}-signal.parquet";h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==r['signal_sha256'];hashes[str(p)]=h
        f=pd.read_parquet(p);c=f.signal_close.where(f.observed_bar&f.volume.gt(0)).reindex(calendar);ret=c.pct_change(fill_method=None)
        out=associate(ret,pr);relative=associate(ret-market,relative_proxies);out['relative_proxy']=relative.proxy;out['relative_correlation']=relative.correlation;out['symbol']=r['symbol'];out['observed']=c.notna();out['changed']=out.proxy.ne(out.proxy.shift())&out.proxy.notna()&out.proxy.shift().notna()
        out=out.loc['2024-01-01':'2026-10-16'];out.index.name='date';rows.append(out.reset_index())
    allrows=pd.concat(rows,ignore_index=True);allrows.to_parquet(OUT/'assignments.parquet',index=False)
    observed=allrows.loc[allrows.observed].copy();observed['year']=observed.date.dt.year
    summary=[]
    for year,g in observed.groupby('year'):
        covered=g.loc[g.proxy.notna()]
        summary.append(dict(year=int(year),observed_stock_days=len(g),assigned=len(covered),coverage=float(g.proxy.notna().mean()),median_correlation=float(covered.correlation.median()),p10_correlation=float(covered.correlation.quantile(.1)),daily_assignment_change_fraction=float(covered.changed.mean()),relative_coverage=float(g.relative_proxy.notna().mean()),raw_relative_agreement=float(covered.loc[covered.relative_proxy.notna(),'proxy'].eq(covered.loc[covered.relative_proxy.notna(),'relative_proxy']).mean()),median_relative_correlation=float(g.relative_correlation.median()),groups=covered.proxy.value_counts().to_dict()))
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    observed.loc[observed.year.eq(2026)].assign(month=lambda x:x.date.dt.strftime('%Y-%m')).groupby(['month','proxy']).agg(stock_days=('symbol','size'),mean_correlation=('correlation','mean'),changes=('changed','sum')).to_csv(OUT/'2026-monthly-groups.csv')
    for s,a in assets.items():
        code=s[4:]
        for path in [Path(f'data/tencent-sh{code}-raw.json'),Path(f'data/eastmoney-fhsp-{code}.html')]:hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT/'validation.json').write_text(json.dumps(dict(stock_hashes_verified=len(manifest['records']),proxy_count=len(assets),first=str(allrows.date.min()),last=str(allrows.date.max()),source_hashes=hashes),indent=2))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
