from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
def main():
 cases=pd.read_csv(PREV/'trade-review.csv');records={r['series_id']:r for r in read(OLD/'inputs-v2/input-manifest.json')['series']};plt.rcParams['font.family']=['Arial Unicode MS','DejaVu Sans'];fig,axes=plt.subplots(4,3,figsize=(16,12),gridspec_kw={'width_ratios':[2,1,1.5]});summary=[]
 for n,(_,r) in enumerate(cases.iterrows()):
  f=pd.read_parquet(records[r.symbol]['raw']['path']);f.index=pd.DatetimeIndex(pd.to_datetime(f.trade_date if 'trade_date' in f else f.index));g=pd.read_parquet(IX/'signals'/f'{r.symbol}.parquet');en=pd.Timestamp(r.entry_at).tz_localize(None).normalize();ex=pd.Timestamp(r.exit_at).tz_localize(None).normalize();left=en-pd.Timedelta(days=30);right=ex+pd.Timedelta(days=15);w=f.loc[left:right];v=g.loc[left:right];inside=g.loc[en:ex]
  axes[n,0].plot(w.index,w.close);axes[n,0].set_title(f"{r['name']}：原始收盘价与旧E0参与");axes[n,1].bar(w.index,w.volume/1e6,width=2);axes[n,1].set_title('量（百万股）');axes[n,2].step(v.index,v.grade*25,where='post');ff=v[v.fresh_up.astype(bool)];axes[n,2].scatter(ff.index,ff.grade*25,s=8,color='red');axes[n,2].set_title('原G1温度；红点为新上行证据');axes[n,2].set_ylim(-85,110)
  for ax in axes[n]:ax.axvline(en,color='green');ax.axvline(ex,color='red');ax.grid(alpha=.2);ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3,maxticks=4));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
  summary.append(dict(symbol=r.symbol,name=r['name'],old_entry=r.entry_at,old_exit=r.exit_at,rows=len(inside),grade_cold=int((inside.grade<=-2).sum()),fresh_up=int(inside.fresh_up.sum()),temperature_downgrades=int((inside.grade.diff()<0).sum())))
 fig.suptitle('仓位前置图检：同一原始量价及冻结G1，不根据正反例改档位');fig.tight_layout();fig.savefig(HERE/'facts-review.png',dpi=140);plt.close(fig);write(HERE/'facts-review.json',summary)
if __name__=='__main__':main()
