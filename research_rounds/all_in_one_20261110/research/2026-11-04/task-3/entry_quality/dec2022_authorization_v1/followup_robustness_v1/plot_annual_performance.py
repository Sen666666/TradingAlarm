"""Standalone descriptive figures from completed, frozen native books only."""
from pathlib import Path
import hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
F=Path(__file__).resolve().parent
p=F/'performance/results_v1/FIXED_PERIOD_PERFORMANCE.json';rows=json.loads(p.read_text())
periods=['2022','2023','2024','2025_observed_H2','2026_observed_H1']
labels=['2022','2023','2024','Jul-Dec 2025','Jan-Jun 2026']
arms=['BASELINE','R_ONLY','P_ONLY','JOINT'];names=['Original','Relative weak','Price weak','Joint weak'];colors=['#262626','#e68624','#3578b7','#198a68']
ix={(r['arm'],r['period']):r for r in rows}
metrics=[('net_wealth_change',1e-4,'Wealth change (CNY 10,000)'),('period_rebased_max_DD',100,'Period-rebased maximum drawdown (%)'),('fees',1e-4,'Actual explicit fees (CNY 10,000)'),('conventional_oneway_turnover_over_mean_CLOSE_NAV',1,'One-way turnover / mean NAV (not annualized)'),('mean_previous_CLOSE_exposure',100,'Mean previous-CLOSE stock exposure (%)'),('top5',100,'Top 5 stocks / gross positive stock P&L (%)')]
fig,axes=plt.subplots(2,3,figsize=(18,9),constrained_layout=True)
x=np.arange(len(periods));width=.19
for ax,(key,scale,title) in zip(axes.flat,metrics):
 for j,(arm,name,color) in enumerate(zip(arms,names,colors)):
  values=[]
  for period in periods:
   r=ix[arm,period]
   v=r['concentration']['stock']['top']['5']['share_of_gross_positive'] if key=='top5' else r[key]
   values.append(float(v)*scale)
  ax.bar(x+(j-1.5)*width,values,width,label=name,color=color)
 ax.set_title(title,fontsize=11);ax.set_xticks(x,labels,rotation=20,ha='right');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
 if key=='net_wealth_change':ax.axhline(0,color='#555',linewidth=.7)
axes[0,0].legend(fontsize=9)
fig.suptitle('Frozen H2 authorization: all four arms, annual and observed-half-year results\n2022-24 is one continuous account; Jul 2025-Jun 2026 starts a separate CNY 1m account',fontsize=14)
for suffix in ('png','pdf'):fig.savefig(F/('ANNUAL_COST_EXPOSURE_CONCENTRATION.'+suffix),dpi=160)
(F/'ANNUAL_FIGURE_PROVENANCE.json').write_text(json.dumps({'data':str(p),'data_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'periods':periods,'all_four_original_frozen_arms':True,'new_accounts':0,'concentration_is_descriptive_not_deletion_backtest':True},indent=2)+'\n')
print('ANNUAL_FIGURE_COMPLETE')
