from pathlib import Path
import gzip,json
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parent;R=O.parent/'trend_exit_controls_v1'
ARMS={'BASELINE':('Original','#222222'),'R_ONLY':('Relative weak','#dd8327'),'P_ONLY':('Price weak','#3079bb'),'JOINT':('Joint weak','#24906c')}
def main():
 data={};fig,ax=plt.subplots(2,2,figsize=(14,8),layout='constrained')
 for col,window in enumerate(['2022_2024','strong']):
  for arm,(label,color) in ARMS.items():
   p=(R if arm=='BASELINE' else O)/'runs'/arm/window;assert json.loads((p/'DONE.json').read_text())['completed']
   with gzip.open(p/'pair/daily.jsonl.gz','rt') as f:rr=[json.loads(x) for x in f]
   data[arm,window]=rr;d=pd.to_datetime([x['at'][:10] for x in rr]);v=np.array([float(x['nav']) for x in rr]);dd=(v/np.maximum.accumulate(np.r_[1e6,v])[1:]-1)*100
   ax[0,col].plot(d,v/10000,label=label,color=color,lw=2 if arm=='BASELINE' else 1.5);ax[1,col].plot(d,dd,color=color,lw=1.5)
  ax[0,col].set_title('Continuous 2022-2024' if col==0 else 'Jul 2025-Jun 2026');ax[0,col].set_ylabel('NAV (CNY 10,000)');ax[1,col].set_ylabel('Running-peak drawdown (%)')
  for a in ax[:,col]:a.grid(alpha=.2);a.tick_params(axis='x',rotation=25)
 ax[0,0].legend();fig.suptitle('Same-action mobile authorization ablation; CORE retains original rules');fig.savefig(O/'H2_EQUITY_DRAWDOWN.png',dpi=160)
 fig,ax=plt.subplots(2,1,figsize=(12,7),layout='constrained')
 for arm,(label,color) in ARMS.items():
  rr=data[arm,'2022_2024'];start=next(x for x in rr if x['at'][:10]=='2022-11-30');ix=[j for j,x in enumerate(rr) if x['at'][:7]=='2022-12'];d=pd.to_datetime([rr[j]['at'][:10] for j in ix]);v=[float(rr[j]['nav'])/float(start['nav'])*100 for j in ix];w=[float(rr[j-1]['inventory'])/float(rr[j-1]['nav'])*100 for j in ix]
  ax[0].plot(d,v,label=label,color=color);ax[1].plot(d,w,label=label,color=color)
 p=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USZI399300.csv');m=pd.read_csv(p,index_col=0,parse_dates=True);z=m.loc['2022-12-01':'2022-12-30','close']/m.loc['2022-11-30','close']*100;ax[0].plot(z.index,z,label='HS300 price index, no fees',color='#985199',ls='--')
 ax[0].set_title('Dec 2022: normalized to each own Nov-30 NAV; exposure is not identical');ax[0].set_ylabel('Nov-30 = 100');ax[1].set_ylabel('Previous-CLOSE stock exposure (%)')
 for a in ax:a.grid(alpha=.2);a.tick_params(axis='x',rotation=25)
 ax[0].legend(ncol=3);fig.savefig(O/'DEC2022_NAV_AND_EXPOSURE.png',dpi=160);print('H2_PLOTS_COMPLETE')
if __name__=='__main__':main()
