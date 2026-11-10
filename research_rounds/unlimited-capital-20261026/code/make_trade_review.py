from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
cases=pd.read_csv(HERE/'trade-review.csv')
records={r['series_id']:r for r in json.loads((ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json').read_text())['series']}
plt.rcParams['font.family']=['Arial Unicode MS','DejaVu Sans']
fig,axs=plt.subplots(4,2,figsize=(14,12),gridspec_kw={'width_ratios':[3,1]})
for n,(_,r) in enumerate(cases.iterrows()):
 f=pd.read_parquet(records[r.symbol]['raw']['path']);f=f.copy();f.index=pd.DatetimeIndex(pd.to_datetime(f.trade_date if 'trade_date' in f else f.index))
 en=pd.Timestamp(r.entry_at).tz_localize(None).normalize();ex=pd.Timestamp(r.exit_at).tz_localize(None).normalize();w=f.loc[en-pd.Timedelta(days=60):ex+pd.Timedelta(days=45)]
 axs[n,0].plot(w.index,w.close,lw=1);axs[n,0].axvline(en,color='green',label='买入');axs[n,0].axvline(ex,color='red',label='卖出')
 axs[n,0].set_title(f"{r['name']} {r.symbol}：净收益 {r.net_return:+.1%}，净贡献 {r.net_pnl/1e4:+.1f}万元");axs[n,0].set_ylabel('原始收盘价（元）');axs[n,0].legend();axs[n,0].grid(alpha=.2)
 axs[n,1].bar(w.index,w.volume/1e6,width=2);axs[n,1].set_ylabel('成交量（百万股）')
 for ax in axs[n]:
  ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3,maxticks=5));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
fig.suptitle('结果后实际周期核对：两笔最大盈利与两笔最大亏损；原始价格未复权，权息由账本单独处理')
fig.tight_layout();fig.savefig(HERE/'trade-review-v2.png',dpi=140);plt.close(fig)
