"""Copy only existing audited inputs; inspect raw prices before freezing the model."""
from pathlib import Path
import json,hashlib,shutil,datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'temperature-prototype-20261023'
GOLD=HERE.parent/'gold-chart-fit-20261024'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
    (HERE/'inputs').mkdir(exist_ok=False);(HERE/'raw').mkdir(exist_ok=False)
    fr=json.loads((OLD/'input-freeze.json').read_text());records=[]
    for r in fr['series']:
        p=OLD/'inputs'/(r['symbol']+'.parquet');assert sha(p)==r['input_sha256']
        shutil.copy2(p,HERE/'inputs'/p.name)
        ctrl=OLD/'results/v0/daily'/p.name
        records.append(dict(r,control_path=str(ctrl.resolve()),control_sha256=sha(ctrl)))
    p=GOLD/'data/sina-AU0.parquet';d=pd.read_parquet(p).set_index('date')
    d.index=pd.to_datetime(d.index);d.index.name='date';d=d[['open','high','low','close','volume']];d['segment_id']=0
    dst=HERE/'inputs/AU0.parquet';d.to_parquet(dst)
    controls={}
    for m in ['original','temperature_entry4']:
        cp=GOLD/'results/v0/daily'/(m+'.parquet');controls[m]=dict(path=str(cp.resolve()),sha256=sha(cp))
    records.append(dict(symbol='AU0',name='沪金主连',kind='vendor_continuous',source=str(p.resolve()),
        source_sha256=sha(p),input_sha256=sha(dst),first=str(d.index.min().date()),last=str(d.index.max().date()),
        rows=len(d),segments=1,price_basis='Sina AU0 vendor continuous; adjustment/roll not independently certified; not a tradable contract',controls=controls))
    cases=json.loads((OLD/'cases.json').read_text())
    # Keep all old windows; new AU0 windows were chosen from already known failure/success questions.
    for cid,a,b in [('AU-LONG','2025-01-01','2026-03-31'),('AU-FAST','2025-08-01','2025-11-30'),('AU-REBOUND','2026-04-01','2026-10-23')]:
        cases.append(dict(id=cid,symbol='AU0',start=a,end=b,selection='user-directed known-history diagnostic'))
    dump(HERE/'cases.json',cases)
    dump(HERE/'input-freeze.json',dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        series=records,primary=['AU0']+fr['primary'],pairs=fr['pairs'],baseline_code=fr['baseline_code'],
        scope='19 existing series; no refresh; stock/industry pairs use current classification, selected development samples; no population or OOS claim',
        excluded_new_semiconductor_stocks='Local 688981/002371 available as raw unadjusted bars only in inspected prepared master; do not silently substitute raw prices for causal total-return controls in this bounded comparison'))
    font=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    for page in range(0,len(records),4):
        fig,axes=plt.subplots(8,1,figsize=(16,14),gridspec_kw={'height_ratios':[3,1]*4})
        for j,r in enumerate(records[page:page+4]):
            d=pd.read_parquet(HERE/'inputs'/(r['symbol']+'.parquet')).loc['2022-01-01':]
            ax=axes[j*2];av=axes[j*2+1]
            ax.vlines(d.index,d.low,d.high,color='#b3bec9',lw=.45);ax.plot(d.index,d.close,lw=.8,color='#263f57')
            ax.set_title(r['name']+' '+r['symbol']+'  原始OHLCV（信号价格口径；未叠加算法）',fontproperties=font,fontsize=12,loc='left')
            av.bar(d.index,d.volume,color='#a5b6c5',width=1);av.set_ylabel('Volume')
            for a in (ax,av):a.grid(alpha=.15)
        for a in axes[len(records[page:page+4])*2:]:a.set_visible(False)
        fig.tight_layout();fig.savefig(HERE/'raw'/f'raw-{page//4+1:02}.png',dpi=115);plt.close(fig)
    print('prepared',len(records),'series; 5 raw sheets; no model run')
if __name__=='__main__':main()
