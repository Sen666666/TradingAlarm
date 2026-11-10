"""Six preselected raw price/volume charts, no states or accounts."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'sector-data-v2'
font='/System/Library/Fonts/PingFang.ttc'
if Path(font).exists():font_manager.fontManager.addfont(font);plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
plt.rcParams['axes.unicode_minus']=False
manifest=json.loads((OUT/'manifest.json').read_text());series={x['symbol']:x for x in manifest['series']}
protocol=json.loads((OUT/'PROTOCOL.json').read_text())
charts=OUT/'charts';charts.mkdir(exist_ok=False)
rows=[]
for selected in protocol['selection_frozen_before_chart_review']:
 sid=selected['symbol'];record=series[sid];f=pd.read_parquet(record['bars']['path'])
 fig,(ax,vax)=plt.subplots(2,1,figsize=(15.5,8.5),sharex=True,gridspec_kw={'height_ratios':[3,1]},layout='constrained')
 fig.set_facecolor('#f7f7f2');ax.set_facecolor('white');vax.set_facecolor('white')
 valid=f.loc[f.price_eligible];starts=[0]+[int(valid.index.get_loc(pd.Timestamp(g['right']))) for g in record['gaps_over_20_days']]
 ends=starts[1:]+[len(valid)]
 for start,end in zip(starts,ends):
  part=valid.iloc[start:end]
  ax.plot(part.index,part.close,color='#154b6a',linewidth=.75)
  ax.fill_between(part.index,part.low,part.high,color='#3d95b8',alpha=.23,linewidth=0)
 for gap in record['gaps_over_20_days']:
  l,r=pd.Timestamp(gap['left']),pd.Timestamp(gap['right'])
  for panel in (ax,vax):panel.axvspan(l,r,color='#d95d39',alpha=.16)
  ax.text(l+(r-l)/2,.95,f"来源空档 {gap['calendar_days']} 日\n{gap['left']} → {gap['right']}",ha='center',va='top',transform=ax.get_xaxis_transform(),fontsize=9,color='#a93925')
 vax.vlines(f.index,0,f.volume/1e9,color='#52696e',linewidth=.8)
 bad=f.loc[~f.price_eligible]
 if not bad.empty:ax.scatter(bad.index,bad.close,color='#cb3c2c',marker='x',s=22,label='不合格价格观察')
 ax.set_yscale('log');ax.set_ylabel('原始指数点位（对数轴）',fontsize=11)
 vax.set_ylabel('成交量 / 10⁹\n原始指数源单位',fontsize=10)
 ax.set_title(f"{record['name']} · {sid}   |   完整已取得量价",loc='left',fontweight='bold',fontsize=17,pad=17)
 source_text=f"{record['first']} 至 {record['last']} · {record['rows']:,} 条原始记录 · 有效价格 {record['price_eligible_rows']:,} · 正量 {record['positive_volume_rows']:,}"
 ax.text(0,1.018,source_text,transform=ax.transAxes,fontsize=10,color='#45555c')
 for panel in (ax,vax):
  panel.grid(axis='y',alpha=.16)
  panel.spines[['top','right']].set_visible(False)
 loc=mdates.AutoDateLocator(minticks=5,maxticks=10);vax.xaxis.set_major_locator(loc);vax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
 note='只展示来源量价，不包含模型状态或收益；空档不连线、不补成交。单位未作跨行业可比声明。'
 if record['first']>'2013-01-01':note+=' 起点晚于目标2013预热期，不能据此称此前无该行业。'
 fig.supxlabel(note,fontsize=9,color='#45555c')
 path=charts/(sid+'.png');fig.savefig(path,dpi=140);plt.close(fig)
 rows.append({'symbol':sid,'file':str(path.resolve()),'selection_reason':selected['reason']})
(charts/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'charts':len(rows),'output':str(charts),'accounts_run':0},ensure_ascii=False))
