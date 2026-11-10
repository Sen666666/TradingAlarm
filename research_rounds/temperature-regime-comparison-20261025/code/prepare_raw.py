import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/temp-regimes-mpl')
import numpy as np,pandas as pd
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from common import *
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
def main():
 manifest=read(ROOT/'research_rounds/fixed-scenarios-v1/manifest.json');sources=[];cases=read(HERE/'cases.json');symbols=sorted({x['symbol'] for x in cases});assert len(cases)==18 and len(symbols)==7
 names={x['symbol']:x['name'] for x in cases}
 for sym in symbols:
  p=SOURCE/'inputs'/(sym+'.parquet');assert sha(p)==manifest['data_snapshot'][sym]['sha256'];os.link(p,HERE/'inputs'/(sym+'.parquet'));sources.append(ref(p))
 for g,group in enumerate([symbols[:4],symbols[4:]]):
  fig,axs=plt.subplots(len(group),2,figsize=(14,3*len(group)),squeeze=False)
  for j,sym in enumerate(group):
   d=pd.read_parquet(HERE/'inputs'/(sym+'.parquet')).loc['2021-01-01':'2026-10-23']
   assert d.index.is_unique and d.index.is_monotonic_increasing and np.isfinite(d[['open','high','low','close','volume']]).all().all() and d[['open','high','low','close','volume']].gt(0).all().all()
   axs[j,0].plot(d.index,d.close,color='#285a8e',lw=.8);axs[j,0].fill_between(d.index,d.low,d.high,color='#8db2cf',alpha=.3);axs[j,0].set_yscale('log');axs[j,0].set_title(names[sym]+' '+sym+' 冻结价格（对数）',fontproperties=FONT)
   axs[j,1].plot(d.index,d.volume/d.volume.median(),color='#81939c',lw=.7);axs[j,1].set_title('当日量/全展示段量中位数，仅用于原始图展示',fontproperties=FONT)
   for ax in axs[j]:ax.grid(alpha=.15)
  fig.tight_layout();fig.savefig(HERE/'review'/f'raw-{g}.png',dpi=120);plt.close(fig)
 write(HERE/'input-manifest.json',dict(recorded_at=now(),sources=sources,case_source=ref(OLD/'cases.json'),fixed_registry=ref(ROOT/'research_rounds/fixed-scenarios-v1/manifest.json'),network_requests=0))
 print({'raw_symbols':7,'cases':18,'new_accounts':0},flush=True)
if __name__=='__main__':main()
