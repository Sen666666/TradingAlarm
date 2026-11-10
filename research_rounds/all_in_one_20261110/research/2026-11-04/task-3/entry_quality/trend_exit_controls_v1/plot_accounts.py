"""Standalone complete-account equity and drawdown comparison, no fitted parameter."""
from pathlib import Path
import gzip,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parent
ARMS={'BASELINE':('Original','#222222'),'EARLY_EMA20':('EMA20 extra exit','#1f77b4'),'EARLY_EMA60':('EMA60 extra exit','#e48b22'),'EARLY_BOLL20_MID':('Boll20 mid extra exit','#289469'),'EARLY_BOLL20_LOWER':('Boll20 lower extra exit','#ae489b')}
def main():
 fig,axes=plt.subplots(2,2,figsize=(15,8),layout='constrained')
 for col,window in enumerate(['2022_2024','strong']):
  for arm,(label,color) in ARMS.items():
   p=O/'runs'/arm/window;assert json.loads((p/'DONE.json').read_text())['completed']
   with gzip.open(p/'pair/daily.jsonl.gz','rt') as f:r=[json.loads(x) for x in f]
   d=pd.to_datetime([x['at'][:10] for x in r]);v=np.array([float(x['nav']) for x in r]);peak=np.maximum.accumulate(np.r_[1000000.,v])[1:];dd=100*(v/peak-1)
   axes[0,col].plot(d,v/10000,label=label,color=color,lw=2 if arm=='BASELINE' else 1.35)
   axes[1,col].plot(d,dd,label=label,color=color,lw=2 if arm=='BASELINE' else 1.35)
  axes[0,col].set_title('Continuous 2022-2024' if col==0 else 'Strong window Jul 2025-Jun 2026')
  axes[0,col].set_ylabel('Account NAV (CNY 10,000)');axes[1,col].set_ylabel('Drawdown from running NAV peak (%)')
  for a in axes[:,col]:a.grid(alpha=.2);a.tick_params(axis='x',rotation=25)
 axes[0,0].legend(fontsize=9);fig.suptitle('One additional exit trigger within the original No60 framework',fontsize=15)
 fig.savefig(O/'ACCOUNT_EQUITY_DRAWDOWN.png',dpi=170);print('ACCOUNT_PLOT_COMPLETE')
if __name__=='__main__':main()
