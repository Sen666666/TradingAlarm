from prepare import *
plt.rcParams['font.sans-serif']=['Arial Unicode MS','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
out=O/'graphs-v2';out.mkdir(exist_ok=False);roster,tr,agg,gates,sg=generate()
# Original OHLC/amount examples, fixed by earlier study not performance selection.
for sid in ['688498.SH','300308.SZ','300502.SZ','603256.SH']:
 raw=eligible_prices(pd.read_parquet(BASE/'prepared-v2/signals'/f'{sid}.parquet')).loc['2024':];fig,ax=plt.subplots(3,1,figsize=(14,8),sharex=True)
 for t,r in raw.iterrows():
  color='#c54538' if r.close>=r.open else '#348774';ax[0].plot([t,t],[r.low,r.high],color=color,lw=.5);ax[0].plot([t,t],[r.open,r.close],color=color,lw=1)
 ax[0].set_title(sid+' 原始OHLC（因果复权坐标）');ax[1].bar(raw.index,raw.amount/1e8,width=1);ax[1].set_ylabel('成交金额亿元');z=tr[sid].loc['2024':];ax[2].plot(z.index,z.m21,label='个股方向金额m21');ax[2].plot(z.index,z.m63,label='m63');ax[2].axhline(0,color='grey');ax[2].legend()
 for a in ax:a.grid(alpha=.2)
 fig.tight_layout();fig.savefig(out/f'raw-{sid}.png',dpi=110);plt.close(fig)
fig,ax=plt.subplots(2,1,figsize=(14,7),sharex=True);a=agg.loc['2024':];a.plot(ax=ax[0]);gates.loc['2024':].astype(int).plot(ax=ax[1]);fig.tight_layout();fig.savefig(out/'gates.png',dpi=120);plt.close(fig)
