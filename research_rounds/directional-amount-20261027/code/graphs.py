from prepare import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
if __name__=='__main__':
 name=sys.argv[1];out=O/name;figdir=out/'graphs';figdir.mkdir(exist_ok=False);diagnostics=[]
 for sid in SYMS:
  raw=eligible_prices(pd.read_parquet(ORIG/'signals'/f'{sid}.parquet'));z=pd.read_parquet(out/'traces'/f'{sid}.parquet');old=pd.read_parquet(ORIG/'facts'/f'{sid}.parquet');fig=plt.figure(figsize=(18,8));grid=fig.add_gridspec(3,3,height_ratios=[3,1,1.4],hspace=.12,wspace=.18)
  for j,year in enumerate([2024,2025,2026]):
   f=raw.loc[str(year)];v=z.loc[f.index];ax=fig.add_subplot(grid[0,j]);av=fig.add_subplot(grid[1,j],sharex=ax);ast=fig.add_subplot(grid[2,j],sharex=ax);xx=np.arange(len(f))
   for k,b in enumerate(f.itertuples()):
    col='#278975' if b.close>=b.open else '#b74e4e';ax.vlines(k,b.low,b.high,color=col,lw=.5);ax.add_patch(Rectangle((k-.3,min(b.open,b.close)),.6,max(abs(b.open-b.close),b.close*.0002),facecolor=col,linewidth=0))
   ax.plot(xx,v.h_floor,color='#777777',lw=.7,label='H support');marks=[(v.event.eq(1),'^','#16874b','up'),(v.event.eq(-1),'v','#4679b5','down'),(v.shock.eq(1),'x','#cc2222','large decline')]
   for mask,marker,col,label in marks:ax.scatter(xx[mask],f.close[mask],marker=marker,color=col,s=20,label=label,zorder=5)
   ax.set_title(str(year));ax.legend(fontsize=6,ncol=2);ax.set_yscale('log');ax.tick_params(labelbottom=False)
   av.bar(xx,f.amount/1e8,color='#8299ac');av.set_ylabel('CNY 100m',fontsize=7);av.tick_params(labelbottom=False)
   ast.step(xx,old.loc[f.index].i_target.astype(float)*.8+4,where='post',label='old I',color='#777777');ast.step(xx,v.h_target*.8+2.7,where='post',label='new H',color='#278975');ast.step(xx,v.c_target*.8+1.4,where='post',label='new C',color='#b66a3a');ast.step(xx,v.grade*.22,where='post',label='temperature',color='#7a53a1');ast.legend(fontsize=6,ncol=2);ast.set_yticks([]);ticks=np.linspace(0,len(f)-1,5).astype(int);ast.set_xticks(ticks,[f.index[k].strftime('%m-%d') for k in ticks],fontsize=7)
   for a in [ax,av,ast]:a.grid(alpha=.12)
   for t,r in v[v.event.eq(1)].iterrows():
    ix=raw.index.get_loc(t);past=float(raw.close.iloc[ix]/raw.close.iloc[max(0,ix-21)]-1);aft=raw.iloc[ix+1:ix+22];diagnostics.append(dict(symbol=sid,date=str(t.date()),past21=past,mu21=r.mu21,grade=r.grade,next21=float(aft.close.iloc[-1]/raw.close.iloc[ix]-1) if len(aft)==21 else np.nan,shock_before_5=bool(z.shock.iloc[max(0,ix-5):ix].any())))
  fig.suptitle(f'{name} | {sid} | OHLC, actual amount, states (all known development windows)',fontsize=13);fig.savefig(figdir/f'{sid}.png',dpi=120,bbox_inches='tight');plt.close(fig)
 pd.DataFrame(diagnostics).to_csv(out/'graph-events.csv',index=False);print(name,'graphs',len(SYMS),'windows',3*len(SYMS),'up_events',len(diagnostics))
