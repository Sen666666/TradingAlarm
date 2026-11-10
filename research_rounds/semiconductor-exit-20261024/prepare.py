from pathlib import Path
import shutil,json,hashlib,datetime
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parent;P=R/'../exit-posture-20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
freeze=json.loads((P/'freeze.json').read_text())
for x in ['model.py','engine.py','inputs/USHJ512480.parquet']:
 assert sha(P/x)==freeze['sha256'][x]
for x in ['model.py','engine.py']:shutil.copyfile(P/x,R/x)
(R/'inputs').mkdir();(R/'charts').mkdir()
d=pd.read_parquet(P/'inputs/USHJ512480.parquet').loc[:'2026-06-30'];assert d.index.is_unique and d.index.is_monotonic_increasing and d.notna().all().all();assert (d>0).all().all();assert (d.high>=d[['open','close']].max(axis=1)).all() and (d.low<=d[['open','close']].min(axis=1)).all()
p=R/'inputs/USHJ512480.parquet';d.to_parquet(p)
meta={'prepared_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'../exit-posture-20261024/inputs/USHJ512480.parquet','source_sha256':sha(P/'inputs/USHJ512480.parquet'),'input_sha256':sha(p),'first':str(d.index[0].date()),'last':str(d.index[-1].date()),'prewindow':int((d.index<'2025-01-02').sum()),'window_observations':int((d.index>='2025-01-02').sum()),'window':['2025-01-02','2026-06-30'],'price_basis':'causal reinvested total-return proxy, common positive daily adjustment to all OHLC; same proxy execution, no extra dividends','requests':0}
(R/'inputs.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams['font.family']='Arial Unicode MS';plt.rcParams['axes.unicode_minus']=False
z=d.loc['2024-01-01':];fig,axes=plt.subplots(2,1,figsize=(15,8),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[3,1]});axes[0].plot(z.index,z.close,c='#84713f');axes[0].set_yscale('log');axes[0].axvline(pd.Timestamp('2025-01-02'),c='#555',ls='--',lw=1);axes[0].set_title('半导体ETF512480：原始量价先审阅；2025起仅计算指定窗口收益');axes[0].set_ylabel('既有权息价格代理 / 对数轴');axes[1].bar(z.index,z.volume,width=1.4,color='#989b96');axes[1].set_ylabel('原输入成交量')
for ax in axes:ax.grid(alpha=.15)
fig.savefig(R/'charts/raw.png',dpi=120);plt.close(fig);print(json.dumps(meta,ensure_ascii=False,indent=2))
