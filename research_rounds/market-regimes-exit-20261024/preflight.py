from pathlib import Path
import json
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from model import context,state,POLICIES
R=Path(__file__).resolve().parent;D=R/'prepared';D.mkdir(exist_ok=False);cases=json.loads((R/'cases.json').read_text());checks=[];rows=[]
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False,'font.size':9})
for c in cases:
 d=pd.read_parquet(R/'inputs'/f'{c["symbol"]}.parquet').loc[:c['end']];z=d.loc[c['start']:];e,b,f=context(d);folder=D/c['id'];folder.mkdir();f.loc[z.index].to_parquet(folder/'features.parquet');states={}
 for p in POLICIES:
  s,ini=state(d,e,b,f,c['start'],c['end'],p);s.to_parquet(folder/f'{p}.parquet');states[p]=s
  for fraction in [.5,.75]:
   dt=z.index[int((len(z)-1)*fraction)];dd=d.loc[:dt];ee,bb,ff=context(dd);ss,_=state(dd,ee,bb,ff,c['start'],str(dt.date()),p);pd.testing.assert_frame_equal(ss,s.loc[:dt],check_exact=True);checks.append(dict(case=c['id'],policy=p,cut=str(dt.date()),passed=True))
 (folder/'initial.json').write_text(json.dumps(ini,indent=2));lr=np.log(z.close/z.close.iloc[0]);rows.append(dict(id=c['id'],symbol=c['symbol'],name=c['name'],type=c['type'],first=str(z.index[0].date()),last=str(z.index[-1].date()),observations=len(z),warmup=int((d.index<z.index[0]).sum()),price_return=z.close.iloc[-1]/z.close.iloc[0]-1,range=z.close.max()/z.close.min()-1,annualized_vol=lr.diff().std()*np.sqrt(252),efficiency=abs(lr.iloc[-1])/lr.diff().abs().sum(),initial_active=ini['active']))
 for page in [0]:
  fig,axes=plt.subplots(4,1,figsize=(13,9),sharex=True,layout='constrained')
  for ax,p,col in zip(axes,POLICIES,['#176b78','#d57235','#8b66a5','#bd4453']):
   s=states[p];ax.plot(z.index,z.close,c='#a69567',lw=1);ax.plot(s.index,s.exit_line.where(s.target.astype(bool)),c=col,lw=.9);ax.fill_between(z.index,z.close.min()*.95,z.close.max()*1.03,where=s.target.astype(bool),color=col,alpha=.08,step='post');ax.set_yscale('log');ax.set_title(p+' '+c['id']+' '+c['name'],loc='left');ax.grid(alpha=.13)
  fig.savefig(R/'review'/f'signals-{c["id"]}.png',dpi=90);plt.close(fig)
 print('signal only',c['id'],flush=True)
pd.DataFrame(checks).to_csv(D/'prefix-checks.csv',index=False);pd.DataFrame(rows).to_csv(D/'case-prices.csv',index=False);print('No accounts run;',len(checks),'prefixes pass')
# Contact sheets allow all signal charts to be reviewed before dispatching any account.
for k in range(0,len(cases),2):
 fig,axes=plt.subplots(1,2,figsize=(18,7),layout='constrained')
 for ax,c in zip(axes,cases[k:k+2]):ax.imshow(plt.imread(R/'review'/f'signals-{c["id"]}.png'));ax.axis('off')
 fig.savefig(R/'review'/f'signals-sheet-{k//2+1}.png',dpi=110);plt.close(fig)
