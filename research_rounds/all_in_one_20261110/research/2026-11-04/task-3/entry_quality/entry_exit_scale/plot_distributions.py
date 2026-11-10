"""Standalone descriptive ECDF, financial labels only color evaluation groups."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parent/'analysis_summary'
a=json.loads((O/'2022_2024_JOINED_ROWS.json').read_text());b=json.loads((O/'strong_JOINED_ROWS.json').read_text())
groups=[('2022-23 losing layers',[x for x in a if x['opened'][:10]<='2023-12-29' and float(x['net'])<0],'#bd3942'),('Post Oct-8 losing layers',[x for x in a if x['opened'][:10]>'2024-10-08' and float(x['net'])<0],'#e18c24'),('Strong-window closed winners',[x for x in b if not x['qty'] and float(x['net'])>0],'#268065')]
fig,ax=plt.subplots(1,3,figsize=(13.5,4.5),layout='constrained')
for axi,(key,label) in zip(ax,[('width_pct','Entry protection distance (%)'),('r5_pct','Past 5-price-observation return (%)'),('r20_pct','Past 20-price-observation return (%)')]):
 for name,rows,color in groups:
  x=np.sort([float(r[key]) for r in rows if r[key] is not None]);y=np.arange(1,len(x)+1)/len(x);axi.step(x,y,where='post',label=f'{name} (n={len(x)})',color=color,lw=1.8)
 axi.set_xlabel(label);axi.set_ylabel('Cumulative fraction of layers');axi.grid(alpha=.2);axi.set_ylim(0,1)
 vals=np.array([float(r[key]) for _,rows,_ in groups for r in rows if r[key] is not None]);axi.set_xlim(min(0,np.quantile(vals,.005)),np.quantile(vals,.99))
ax[0].legend(fontsize=8,loc='lower right');fig.suptitle('Entry context overlaps across weak-window losses and strong-window winners',fontsize=13)
fig.savefig(O/'ENTRY_CONTEXT_ECDF.png',dpi=170)
print('PLOT_COMPLETE')
