from sec_common import *
from prepare import restore,original_inputs,project
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

def main():
 out=HERE/'technical';out.mkdir(exist_ok=True);pairs=pd.read_parquet(HERE/'pairs/events.parquet');checks=0
 for sid,g in pairs.groupby('symbol'):
  f=pd.read_parquet(IX/'signals'/f'{sid}.parquet');i=pd.read_parquet(HERE/'signals'/f'{sid}.parquet')
  for _,r in g.iloc[::max(1,len(g)//4)].iterrows():
   for p,t in [('IX',f.ix_target),('I',i.i_target)]:
    later=t.loc[pd.Timestamp(r.event_day)+pd.Timedelta(days=1):];end=later.index[later.eq(0)];closed=len(end)>0 and f.index.get_loc(end[0])+1<=f.index.searchsorted(END,side='right')-1
    assert bool(r[p+'_closed'])==closed
    if closed:day=f.index[f.index.get_loc(end[0])+1];price=float(f.open.loc[day]);fac=(1-.0005)**2/(1+.0005)**2
    else:day=f.loc[:END].index[-1];price=float(f.close.loc[day]);fac=1/(1+.0005)**2
    assert str(day.date())==r[p+'_exit_day'];assert abs(price/float(f.open.loc[r.entry_day])*fac-1-r[p+'_return'])<1e-12;checks+=1
 # Physical prefixes of the unchanged I restoration and original projection.
 prefixes=0
 for sid in ['688256.SH','300308.SZ','600276.SH','000001.SZ']:
  f=pd.read_parquet(IX/'signals'/f'{sid}.parquet');full=pd.read_parquet(HERE/'signals'/f'{sid}.parquet')
  for day in ['2021-12-31','2023-12-29','2025-12-31']:
   x=f.loc[:day];r=restore(x);pd.testing.assert_frame_equal(r,full.loc[:day],check_freq=False);e,b,g=original_inputs(x);p=project(e,b,g,'G1_I');np.testing.assert_array_equal(p.target,r.i_target);prefixes+=1
 font=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False});fig,axs=plt.subplots(4,2,figsize=(16,13));selected=[]
 for row,(k,g) in enumerate(pairs.groupby('group',sort=False)):
  for col,order in enumerate([False,True]):
   r=g[g.both_closed].sort_values('difference',ascending=order).iloc[0];sid=r.symbol;f=pd.read_parquet(IX/'signals'/f'{sid}.parquet');start=pd.Timestamp(r.entry_day)-pd.Timedelta(days=30);end=pd.Timestamp(max(r.I_exit_day,r.IX_exit_day))+pd.Timedelta(days=20);f=f.loc[start:end];ax=axs[row,col];vol=ax.twinx();vol.bar(f.index,f.volume,color='#999',alpha=.14,width=1.5);vol.set_ylim(0,float(f.volume.max())*4);vol.set_yticks([]);ax.set_zorder(2);ax.patch.set_visible(False);ax.plot(f.index,f.close,color='#273747',lw=1);ax.axvline(pd.Timestamp(r.entry_day),color='#777',ls=':',label='共同买入');
   for p,c in [('IX','#5279bd'),('I','#c66532')]:ax.axvline(pd.Timestamp(r[p+'_exit_day']),color=c,ls='--',label=p+'退出')
   ax.set_title(f'{GROUPS[k][0]} {r["name"]} {sid}｜I−IX {r.difference:+.1%}',fontsize=10);ax.grid(alpha=.15);ax.legend(fontsize=8);selected.append(dict(group=k,symbol=sid,event_day=r.event_day,difference=r.difference,selection='largest positive/negative paired difference; diagnostic only'))
 fig.suptitle('配对复查：原始量价轨迹上的退出差异（信号复权价；淡灰为成交量）',fontsize=16);fig.tight_layout(rect=(0,0,1,.97));fig.savefig(out/'paired-price-review.png',dpi=125);plt.close(fig)
 write(out/'preflight.json',dict(passed=True,independent_pair_price_and_exit_checks=checks,physical_signal_prefixes=prefixes,review_events=selected,review='I retains some long rises and extends many failed trends; no new exit/entry condition added',recorded_at=now()));print(dict(passed=True,checks=checks,prefixes=prefixes))
if __name__=='__main__':main()
