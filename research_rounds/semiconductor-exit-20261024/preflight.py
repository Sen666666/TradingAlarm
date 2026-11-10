from pathlib import Path
import json,datetime
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from model import context,state,POLICIES
R=Path(__file__).resolve().parent;P=R/'../exit-posture-20261024';S=R/'prepared';S.mkdir(exist_ok=False)
d=pd.read_parquet(R/'inputs/USHJ512480.parquet');e,b,f=context(d);z=d.loc['2025-01-02':'2026-06-30'];states={};checks=[]
pd.concat({'events':e,'base':b,'features':f},axis=1).to_parquet(S/'context.parquet');f.to_parquet(S/'features.parquet')
for policy in POLICIES:
 s,ini=state(d,e,b,f,'2025-01-02','2026-06-30',policy);states[policy]=s;s.to_parquet(S/f'{policy}.parquet')
 old=pd.read_parquet(P/'results/v0/states'/f'USHJ512480-primary-{policy}.parquet');pd.testing.assert_frame_equal(s,old.loc[s.index],check_exact=True)
 checks.append({'check':'prior_round_exact_signal_identity','policy':policy,'passed':True})
 for cut in ['2025-04-30','2025-12-31','2026-03-31']:
  dd=d.loc[:cut];ee,bb,ff=context(dd);ss,_=state(dd,ee,bb,ff,'2025-01-02',cut,policy);pd.testing.assert_frame_equal(ss,s.loc[:cut],check_exact=True);checks.append({'check':'exact_prefix','policy':policy,'cut':cut,'passed':True})
(S/'initial.json').write_text(json.dumps(ini,indent=2));(S/'checks.json').write_text(json.dumps(checks,indent=2))
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams['font.family']='Arial Unicode MS';plt.rcParams['axes.unicode_minus']=False
fig,axes=plt.subplots(4,1,figsize=(15,12),sharex=True,layout='constrained')
for ax,policy,col in zip(axes,POLICIES,['#176b78','#d57235','#8b66a5','#bd4453']):
 s=states[policy];ax.plot(z.index,z.close,c='#9a8c60',lw=1,label='收盘');ax.plot(s.index,s.exit_line.where(s.target.astype(bool)),c=col,lw=1,label=policy+'当时保护线');ax.fill_between(s.index,z.close.min()*.9,z.close.max()*1.02,where=s.target.astype(bool),color=col,alpha=.09,step='post')
 for flag,marker in [('entered','^'),('exited','v')]:
  days=s.index[s[flag].astype(bool)];ax.scatter(days,z.close.loc[days],marker=marker,s=30,color=col,zorder=3)
 ax.set_yscale('log');ax.set_title(policy+' · 三角仅为收盘状态转变，不是当日成交');ax.legend(fontsize=8);ax.grid(alpha=.15)
fig.savefig(R/'charts/signals.png',dpi=120);plt.close(fig)
print('Signals only:16checks pass, including12real-prefix checks; no accounts run. Initial:',ini)
