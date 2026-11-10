from pathlib import Path
import datetime,hashlib,json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=HERE.parent/'three-layer-prototype-20261024'
SYMBOLS=['AU0','USHJ518880','USHJ512480','USHJ510300','600059.SH','600919.SH','600917.SH','HK00002','HK00101','HK00700','HK09618','HK03690','HK03033']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    (HERE/'inputs').mkdir(exist_ok=False);(HERE/'raw').mkdir(exist_ok=False)
    meta={x['symbol']:x for x in json.loads((OLD/'input-freeze.json').read_text())['series']};records=[]
    for sid in SYMBOLS:
        src=HERE.parent/'gold-czsc-backtest-20261024/inputs/AU0-main.parquet' if sid=='AU0' else OLD/'inputs'/(sid+'.parquet')
        d=pd.read_parquet(src).loc[:'2026-10-13',['open','high','low','close','volume']].copy();d.index.name='date'
        assert d.index.is_unique and d.index.is_monotonic_increasing and not d.isna().any().any()
        assert (d[['open','high','low','close']]>0).all().all() and (d.volume>0).all()
        assert ((d.low<=d[['open','close']].min(axis=1))&(d.high>=d[['open','close']].max(axis=1))).all()
        dst=HERE/'inputs'/(sid+'.parquet');d.to_parquet(dst)
        r=dict(symbol=sid,name=meta[sid]['name'],source=str(src.relative_to(ROOT)),source_sha256=sha(src),input_sha256=sha(dst),first=str(d.index[0].date()),last=str(d.index[-1].date()),rows=len(d),pre2024=int((d.index<'2024-01-02').sum()),pre2025=int((d.index<'2025-01-02').sum()),price_basis=meta[sid]['price_basis'])
        records.append(r)
    font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False})
    for start in range(0,len(records),4):
        subset=records[start:start+4];fig,axs=plt.subplots(8,1,figsize=(15,14),gridspec_kw={'height_ratios':[3,1]*4},layout='constrained')
        for j,r in enumerate(subset):
            d=pd.read_parquet(HERE/'inputs'/(r['symbol']+'.parquet')).loc['2024-01-01':];a,v=axs[2*j:2*j+2]
            a.vlines(d.index,d.low,d.high,lw=.45,color='#a5b3bd');a.plot(d.index,d.close,c='#344f62',lw=.9);a.set_yscale('log');a.set_title(r['name']+' '+r['symbol']+'；既有因果信号价格口径，未叠加退出策略',loc='left',fontsize=11)
            v.bar(d.index,d.volume,color='#acb8c0',width=1);v.set_ylabel('量')
            for ax in [a,v]:ax.grid(alpha=.15)
        for ax in axs[2*len(subset):]:ax.set_visible(False)
        fig.savefig(HERE/'raw'/f'raw-{start//4+1}.png',dpi=105);plt.close(fig)
    record=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),series=records,primary=['2025-01-02','2026-10-13'],historical=['2024-01-02','2024-12-31'],requests=0,selection='All13 tradable-price proxies from fixed19-series prototype; six index/sector series are not account assets.')
    with (HERE/'inputs.json').open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
    print('prepared',len(records),'fixed series and4 raw-price pages')
if __name__=='__main__':main()
