from common import *
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
def main():
 out=HERE/'raw-review';out.mkdir(exist_ok=False);meta=read(OLD/'inputs-v2/metadata.json');rows=[]
 for sid in IDS:
  p=SRC/'signals'/f'{sid}.parquet';verify_source(p);f=pd.read_parquet(p).loc[START:END]
  rows.append(dict(symbol=sid,name=meta[sid]['name'],first=str(f.index[0].date()),last=str(f.index[-1].date()),start_close=f.close.iloc[0],end_close=f.close.iloc[-1],end_over_start=f.close.iloc[-1]/f.close.iloc[0],observations=len(f),**{k:int(f[k].sum()) for k in MODES}))
  fig,ax=plt.subplots(2,1,figsize=(13,5),sharex=True,gridspec_kw={'height_ratios':[3,1]});ax[0].plot(f.index,f.close/f.close.iloc[0]*100,color='#263f46',lw=1);ax[0].set_yscale('log');ax[0].set_title(meta[sid]['name']+'：原始因果复权量价（2023首个收盘=100，对数坐标）',fontproperties=FONT,loc='left');ax[0].set_ylabel('price index')
  ax[1].bar(f.index,f.volume/f.volume.shift().rolling(21).median(),color='#9baaae',width=1);ax[1].set_ylabel('relative V')
  for a in ax:a.grid(alpha=.18)
  fig.tight_layout();fig.savefig(out/f'{sid}.png',dpi=120);plt.close(fig)
 pd.DataFrame(rows).to_csv(out/'price-context.csv',index=False);write(out/'price-context.json',rows)
 paths=[HERE/'PROTOCOL.md']+list((HERE/'code').glob('*.py'))+[SRC/'complete.json',OLD/'h1/matrix.npz',OLD/'prepared-v2/manifest.json',OLD/'inputs-v2/metadata.json']+[SRC/'signals'/f'{sid}.parquet' for sid in IDS]
 write(HERE/'initial-freeze.json',dict(recorded_at=now(),phase='posthoc diagnostic before detailed traces and broad future labels',new_accounts=0,algorithm_changes=0,sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}))
 print(rows,flush=True)
if __name__=='__main__':main()
