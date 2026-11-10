from study_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']=['Arial Unicode MS','DejaVu Sans']
CASES=[('688498.SH','源杰科技','2025-06-01','2025-09-01'),('688195.SH','腾景科技','2025-09-01','2025-12-31'),('603115.SH','海星股份','2026-02-01','2026-07-31'),('688048.SH','长光华芯','2026-08-01','2026-10-26')]
def main(overlay=False):
 records={r['series_id']:r for r in read(CORE/'manifest.json')['series']};fig,axs=plt.subplots(4,2,figsize=(14,12))
 for (sid,name,start,end), (a,b) in zip(CASES,axs):
  rec=records[sid];f=read_raw(rec['raw']['path'],rec).loc[start:end];a.fill_between(f.index,f.low,f.high,alpha=.3,color='#7892aa');a.plot(f.index,f.close,color='#233d4d');b.bar(f.index,f.volume/1e6,color='#829e9c');a.set_ylabel(name+'原价');b.set_ylabel('成交股数/百万')
  if overlay:
   z=pd.read_parquet(PREP/'facts'/f'{sid}.parquet').loc[start:end];a.plot(z.index,z.i_floor/z.factor,color='#cc8a35',lw=.9);ix=z.i_buy.astype(bool);a.scatter(z.index[ix],z.raw_close[ix],s=18,color='#c84949',label='原I事件')
   for aid,col in [('I__S0_base','#27865f'),('I__S0_delay1','#7b48ae')]:
    obj=read(BASE/'accounts-v2'/f'{aid}.json');ts=[pd.Timestamp(x['at']).tz_localize(None) for x in obj['fills'] if x['security_id']==sid and x['side']=='buy' and start<=x['at'][:10]<=end];vs=[float(x['gross_cny'])/x['shares'] for x in obj['fills'] if x['security_id']==sid and x['side']=='buy' and start<=x['at'][:10]<=end];a.scatter(ts,vs,s=45,marker='^',color=col,label=aid)
   a.legend(fontsize=7)
  for ax in [a,b]:ax.grid(alpha=.2);ax.tick_params(axis='x',rotation=15,labelsize=8)
 fig.suptitle('量价与原I/延迟I参与（已见开发归因）' if overlay else '原始量价复核：账户解释之前');fig.tight_layout();fig.savefig(HERE/('overlay-v2.png' if overlay else 'raw-v2.png'),dpi=125)
if __name__=='__main__':main(len(sys.argv)>1)
