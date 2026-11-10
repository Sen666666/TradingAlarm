import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/temp-regimes-mpl')
import pandas as pd,numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from common import *
from temperature_v1 import temperature_frame
from three_layer_v1 import three_layer
from policies import project,original,layer3,initial
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
def main():
 (HERE/'contexts').mkdir(exist_ok=False);(HERE/'prepared').mkdir(exist_ok=False);cases=read(HERE/'cases.json');prefix=[];identity=[];stats=[]
 for sym in sorted({x['symbol'] for x in cases}):
  d=pd.read_parquet(HERE/'inputs'/(sym+'.parquet'));t,_=temperature_frame(d);l,_=three_layer(d);states={p:project(t,*p.split('_')) for p in TEMP_POLICIES};states['T_ORIG']=original(t);states['L3']=layer3(l)
  out=HERE/'contexts'/sym;out.mkdir();t.to_parquet(out/'temperature.parquet');l.to_parquet(out/'three-layer.parquet')
  for p,s in states.items():s.to_parquet(out/(p+'.parquet'))
  for n in sorted(set([len(d)//2,len(d)-21,len(d)-1])):
   sub=d.iloc[:n];tt,_=temperature_frame(sub);ll,_=three_layer(sub)
   pd.testing.assert_frame_equal(tt,t.iloc[:n],check_exact=True,check_freq=False);pd.testing.assert_frame_equal(ll,l.iloc[:n],check_exact=True,check_freq=False)
   for p in TEMP_POLICIES:pd.testing.assert_frame_equal(project(tt,*p.split('_')),states[p].iloc[:n],check_exact=True,check_freq=False)
   prefix.append(dict(symbol=sym,cut=str(sub.index[-1].date()),temperature_columns=len(t.columns),three_layer_columns=len(l.columns),temperature_rules=12,passed=True))
  # Replay the previous exact input clock, separately from this matched scene
  # clock, to prove the prototypes themselves were not changed.
  for folder,func,kind in [('temperature-prototype-20261023',temperature_frame,'temp'),('three-layer-prototype-20261024',three_layer,'L3')]:
   ip=ROOT/'research_rounds'/folder/'inputs'/(sym+'.parquet');old=ROOT/'research_rounds'/folder/'results/v0/daily'/(sym+'.parquet')
   if not ip.exists():continue
   oldbars=pd.read_parquet(ip);parts=[func(g)[0] for _,g in oldbars.groupby('segment_id',sort=False)];v=pd.concat(parts).reindex(oldbars.index);saved=pd.read_parquet(old)
   for col in v:
    source=('new_'+col if kind=='L3' and col in ['target','entered','exited','floor'] else col)
    pd.testing.assert_series_equal(v[col],saved[source],check_exact=True,check_names=False,check_freq=False)
   identity.append(dict(symbol=sym,prototype=kind,rows=len(v),columns=len(v.columns),exact=True))
  for c in [x for x in cases if x['symbol']==sym]:
   out=HERE/'prepared'/c['id'];out.mkdir();z=d.loc[c['start']:c['end']];init={}
   for p,s in states.items():
    s.loc[z.index].to_parquet(out/(p+'.parquet'));init[p]=initial(d,s,c['start']);stats.append(dict(case=c['id'],policy=p,signal_entries=int(s.loc[z.index,'entered'].sum()),signal_exits=int(s.loc[z.index,'exited'].sum()),active_fraction=float(s.loc[z.index,'target'].mean()),carry=init[p]['active']))
   write(out/'initial.json',init)
  print({'prepared_symbol':sym,'observations':len(d)},flush=True)
 # Per-case raw price, grade, source models, and predeclared representative rules.
 fixed=[x for x in cases if x['role']=='fixed_scenario'];fig,axs=plt.subplots(4,3,figsize=(18,14));axs=axs.ravel()
 for ax,c in zip(axs,fixed):
  d=pd.read_parquet(HERE/'inputs'/(c['symbol']+'.parquet')).loc[c['start']:c['end']];g=pd.read_parquet(HERE/'contexts'/c['symbol']/'temperature.parquet').loc[d.index];price=d.close/d.close.iloc[0]
  ax.plot(d.index,price,color='#1c2d3d',lw=.8);ax.set_title(c['id']+' '+c['name'],fontproperties=FONT,fontsize=9)
  for p,color in [('E0','#5878b9'),('R','#1a917e'),('C4_S','#cd9143'),('E34_X6','#a95773')]:
   path=(OLD if p in ['E0','R'] else HERE)/'prepared'/c['id']/(p+'.parquet');s=pd.read_parquet(path);ax.scatter(s.index[s.entered.astype(bool)],price.loc[s.index[s.entered.astype(bool)]],s=12,color=color,label=p)
  ax2=ax.twinx();ax2.step(g.index,g.level+1,where='post',color='#d6a898',alpha=.4,lw=.7);ax2.set_ylim(.5,7.5);ax2.set_yticks([1,4,7]);ax.grid(alpha=.15)
 for ax in axs[len(fixed):]:ax.axis('off')
 fig.tight_layout();fig.savefig(HERE/'review/signals-fixed.png',dpi=120);plt.close(fig)
 pd.DataFrame(stats).to_csv(HERE/'signal-review.csv',index=False,encoding='utf-8-sig');write(HERE/'audit/preflight.json',dict(passed=True,recorded_at=now(),physical_prefix_sets=prefix,exact_old_prototype_replays=identity,new_economic_accounts=0,formula_changes=0))
 print({'preflight':True,'prefix_sets':len(prefix),'old_identity':len(identity)},flush=True)
if __name__=='__main__':main()
