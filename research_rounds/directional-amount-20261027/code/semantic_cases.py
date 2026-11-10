from prepare import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
if __name__=='__main__':
 found={}
 for path in sorted((O/'R3/traces').glob('*.parquet')):
  f=eligible_prices(pd.read_parquet(ORIG/'signals'/path.name));z=pd.read_parquet(path);r=np.log(f.close).diff();q=z.q
  masks={'high_amount_small_price':(q>=4)&(r.abs()<=.5*z.scale),'large_decline':z.shock.eq(1),'low_amount_persistent_up':(q.rolling(5).mean()<.8)&(r.gt(0).rolling(5).sum()>=4)&(np.log(f.close/f.close.shift(5))>=np.sqrt(5)*z.scale)}
  for kind,mask in masks.items():
   dates=f.index[mask.fillna(False)&(f.index>=pd.Timestamp('2024-01-01'))&z.ready.eq(1)]
   if len(dates):
    t=dates[0];cand=(str(t.date()),path.stem)
    if kind not in found or cand<found[kind]:found[kind]=cand
 fig=plt.figure(figsize=(17,8));grid=fig.add_gridspec(3,3,height_ratios=[3,1,1],hspace=.1,wspace=.2);receipts=[]
 for j,(kind,(date,sid)) in enumerate(sorted(found.items())):
  raw=eligible_prices(pd.read_parquet(ORIG/'signals'/f'{sid}.parquet'));z=pd.read_parquet(O/'R3/traces'/f'{sid}.parquet');n=raw.index.get_loc(pd.Timestamp(date));s=max(0,n-21);f=raw.iloc[s:n+22];v=z.loc[f.index];x=np.arange(len(f));ax=fig.add_subplot(grid[0,j]);av=fig.add_subplot(grid[1,j],sharex=ax);ast=fig.add_subplot(grid[2,j],sharex=ax)
  for k,b in enumerate(f.itertuples()):
   color='#2c8c73' if b.close>=b.open else '#bd554d';ax.vlines(k,b.low,b.high,color=color,lw=.7);ax.add_patch(Rectangle((k-.3,min(b.open,b.close)),.6,max(abs(b.open-b.close),b.close*.0002),color=color,lw=0))
  ax.set_title(kind+'\n'+sid+' '+date,fontsize=10);av.bar(x,f.amount/1e8,color='#8397a6');av.set_ylabel('CNY 100m',fontsize=8);ast.step(x,v.grade,where='post',color='#8554a2');ast.set_ylabel('temperature');ast.set_yticks([-2,0,1,2,3]);ticks=np.linspace(0,len(f)-1,4).astype(int);ast.set_xticks(ticks,[f.index[i].strftime('%m-%d') for i in ticks],fontsize=8)
  for a in [ax,av,ast]:a.axvline(n-s,color='#d08621',ls='--');a.grid(alpha=.15)
  ax.tick_params(labelbottom=False);av.tick_params(labelbottom=False);row=z.loc[date];receipts.append(dict(kind=kind,date=date,symbol=sid,q=float(row.q),grade=int(row.grade),shock=int(row.shock),event=int(row.event),reason=row.reason))
 fig.suptitle('Earliest qualifying examples across 407 stocks; selection uses only contemporaneous data');fig.savefig(O/'semantic-cases.png',dpi=140,bbox_inches='tight');pd.DataFrame(receipts).to_csv(O/'semantic-cases.csv',index=False);print(receipts)
