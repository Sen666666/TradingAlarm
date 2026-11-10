"""Freeze existing local inputs and draw raw panels before model design. Offline."""
from pathlib import Path
import os, sys, json, hashlib, datetime
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PRIOR=ROOT/'research_rounds/pv-participation-response-20261020'
SECTOR=ROOT/'research_rounds/current-pool-20261022/sector-trajectories-v1'
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.tools/czsc/mpl'))
sys.path.insert(0,str(PRIOR/'code'))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from data_utils import load_inputs

NAMES={'USHJ518880':'黄金ETF','USHJ512480':'半导体ETF','USHJ510300':'沪深300ETF',
 'HK00002':'中电控股','HK09618':'京东集团','HK00700':'腾讯控股','HK03033':'南方恒生科技',
 'HK00101':'恒隆地产','HK03690':'美团','600919.SH':'江苏银行','600059.SH':'古越龙山',
 '600917.SH':'重庆燃气','URFI881129':'通信设备指数','UZZI000994':'中证信息安全指数',
 'URFI881121':'半导体行业指数','URFI881133':'饮料制造指数','URFI881146':'燃气行业指数','URFI881155':'银行行业指数'}
PRIMARY=['USHJ518880','USHJ512480','URFI881121','600919.SH','600059.SH','600917.SH','HK00700','HK09618']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')

def main():
    out=HERE/'inputs';out.mkdir(exist_ok=False)
    (HERE/'raw').mkdir()
    frames,cases,manifest=load_inputs(PRIOR)
    source_records={r['symbol']:r for r in manifest['series']}
    records=[]
    for sid,d in frames.items():
        p=PRIOR/'prepared/source-precision-v1'/source_records[sid]['file']
        records.append(dict(symbol=sid,name=NAMES[sid],source=str(p),source_sha256=sha(p),kind='legacy_audited',
            price_basis=source_records[sid]['source_metadata']['adjustment'],last=str(d.index[-1].date())))
    sm=json.loads((SECTOR/'prepared/manifest.json').read_text())
    for sid in ['URFI881121','URFI881133','URFI881146','URFI881155']:
        r=next(x for x in sm['series'] if x['series_id']==sid)
        p=SECTOR/'prepared'/r['files']['signal']['path']
        assert sha(p)==r['files']['signal']['sha256']
        d=pd.read_parquet(p)
        d=d.loc[d.price_eligible & d.volume_eligible].copy()
        frames[sid]=d
        records.append(dict(symbol=sid,name=NAMES[sid],source=str(p),source_sha256=sha(p),kind='same_source_sector',price_basis='unadjusted_index',last=str(d.index[-1].date())))
    for r in records:
        d=frames[r['symbol']]
        assert d.index.is_unique and d.index.is_monotonic_increasing
        assert np.isfinite(d[['open','high','low','close','volume']]).all().all() and d.volume.gt(0).all()
        if 'segment_id' not in d:d['segment_id']=0
        p=out/(r['symbol']+'.parquet');d.to_parquet(p)
        r.update(input_sha256=sha(p),rows=len(d),first=str(d.index[0].date()),segments=int(d.segment_id.nunique()))
    dump(HERE/'cases.json',cases)
    dump(HERE/'input-freeze.json',dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
      purpose='One user-authorized temperature prototype; old algorithm retained. No accounts or new downloads.',
      primary=PRIMARY,series=records,baseline_code={n:sha(PRIOR/'code'/n) for n in ['numeric.py','participation.py','data_utils.py']},
      cases_sha256=sha(HERE/'cases.json'),selection='All 14 old audited series + four matching THS A-industry indices. Eight primary displays; all 18 old fixed windows retained. Already-seen development history, not unseen.',
      pairs={'600919.SH':'URFI881155','600059.SH':'URFI881133','600917.SH':'URFI881146'},
      hk_sector_gate='Unknown in this bounded prototype. HK charts are single-asset diagnostics, not joint stock-selection claims.',
      source_cutoffs='Legacy inputs end 2026-10-16; sector inputs end 2026-10-22. Pairing uses only dates observed by both; no future fill.',account_runs=0,market_downloads=0))
    font=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    views=[]
    # Show all fixed windows and primary full paths, without model overlays.
    for sid in PRIMARY:views.append(dict(id='full-'+sid,symbol=sid,start='2023-01-01',end='2026-10-22'))
    views+=cases
    for page in range(0,len(views),6):
        specs=views[page:page+6]
        fig,axs=plt.subplots(len(specs),2,figsize=(16,2.5*len(specs)),gridspec_kw={'width_ratios':[4,1.5]},squeeze=False)
        for row,s in enumerate(specs):
            d=frames[s['symbol']].loc[s['start']:s['end']]
            ax=axs[row,0];ax.plot(d.index,d.close,color='#354754',lw=.9);ax.fill_between(d.index,d.low,d.high,color='#7893a1',alpha=.2)
            ax.set_yscale('log');ax.set_title(s['id']+' '+NAMES[s['symbol']]+'｜既有复权口径OHLC',fontproperties=font,loc='left',fontsize=11)
            axs[row,1].bar(d.index,d.volume,width=1.7,color='#9db1bf');axs[row,1].set_title('原成交量单位，仅纵向比较',fontproperties=font,fontsize=9)
            axs[row,1].ticklabel_format(axis='y',style='sci',scilimits=(0,0))
            for a in axs[row]:a.grid(alpha=.15);a.tick_params(labelsize=7);a.spines[['top','right']].set_visible(False)
        fig.tight_layout();fig.savefig(HERE/'raw'/f'raw-{page//6+1:02}.png',dpi=110);plt.close(fig)
    dump(HERE/'raw/views.json',views)
    print(json.dumps({'series':len(records),'windows':len(cases),'raw_sheets':(len(views)+5)//6,'cutoffs':sorted(set(r['last'] for r in records))},ensure_ascii=False))
if __name__=='__main__':main()
