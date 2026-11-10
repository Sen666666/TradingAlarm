from pathlib import Path
import json
import pandas as pd,numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1]
SNAP=Path(json.loads((ROOT/'research_rounds/pvr-act-comparison-20261027/input.json').read_text())['snapshot']['path'])
WINDOWS=[('688498.SH','2025-06-01','2025-11-28'),('300502.SZ','2025-03-01','2025-10-31'),('603186.SH','2026-02-01','2026-08-31'),('001309.SZ','2025-03-01','2025-10-31'),('688048.SH','2025-06-01','2025-12-31'),('002439.SZ','2024-01-01','2024-08-31'),('688041.SH','2026-04-01','2026-10-27'),('600845.SH','2024-01-01','2024-08-31'),('300308.SZ','2026-04-01','2026-10-27')]
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
for page in range(3):
 fig,ax=plt.subplots(2,3,figsize=(18,8),sharex='col',gridspec_kw={'height_ratios':[3,1]})
 for j,(sid,start,end) in enumerate(WINDOWS[page*3:page*3+3]):
  f=pd.read_parquet(SNAP/'signals'/f'{sid}.parquet').loc[start:end];x=np.arange(len(f))
  for i,r in enumerate(f.itertuples()):
   c='#b8352f' if r.close>=r.open else '#26794f';ax[0,j].vlines(i,r.low,r.high,color=c,lw=.6);ax[0,j].add_patch(Rectangle((i-.3,min(r.open,r.close)),.6,max(abs(r.open-r.close),1e-5),facecolor=c,lw=.3))
  ax[0,j].set_title(sid+' '+start+' ~ '+end);ax[1,j].bar(x,f.amount/1e8,color='#8096aa');ax[1,j].set_ylabel('实际成交金额/亿元');ticks=np.linspace(0,len(f)-1,6,dtype=int);ax[1,j].set_xticks(ticks,[str(f.index[i].date())[2:] for i in ticks],rotation=25)
 fig.suptitle('原始量价先行：因果复权OHLC；尚未叠加新信号、未运行账户');fig.tight_layout();fig.savefig(O/f'raw-{page+1}.png',dpi=115);plt.close(fig)
(O/'windows.json').write_text(json.dumps(WINDOWS,indent=2))
