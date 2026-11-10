"""Stage-one source OHLCV only. No signal/policy/account imports."""
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
CASES=[('002747.SZ','Estun','ordinary-loss capital'),('002718.SZ','Youpon','extra ordinary loss'),('688766.SH','Puran','missed semiconductor rise'),('688605.SH','Pioneer','new semiconductor failed attempt'),('002969.SZ','Jiamei','incremental exited winner'),('300489.SZ','LightPath','incremental marked winner')]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 with (P/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def main():
 mp=W/'pvr-slot1-native-readiness-20261101/preflight-development-v1/SCORES_MANIFEST.json'
 sm={x['symbol']:x for x in json.loads(mp.read_text())['entries']};src={str(mp):sha(mp),str(Path(__file__)):sha(__file__)};summ=[]
 fig,ax=plt.subplots(6,2,figsize=(19,19),gridspec_kw={'width_ratios':[3,1]},layout='constrained')
 for j,(sid,name,selection) in enumerate(CASES):
  e=sm[sid];p=Path(e['source']);assert sha(p)==e['source_sha256'];src[str(p)]=sha(p)
  # The source file contains later bars; the exported view is physically sliced
  # before plotting/statistics. No later close, extreme, factor or signal used.
  full=pd.read_parquet(p).loc[:'2026-06-30'];assert len(full)==e['source_rows']
  f=full.loc['2025-07-01':'2026-06-30'].copy()
  cols=['raw_open','raw_high','raw_low','raw_close','raw_volume','amount','open','high','low','close','volume','adjustment_factor','segment_id','source_invalid','observed_bar','is_observed_bar','synthetic_event_bar','quality_status','source_kind','source_path','volume_unit','amount_unit']
  f[cols].to_csv(P/(sid+'-SOURCE_OHLCV.csv'))
  x=np.arange(len(f));up=f.raw_close>=f.raw_open;colors=np.where(up,'#b84848','#2b897f')
  for a,key in [(ax[j,0],'raw'),(ax[j,1],'continuous')]:
   o=f.raw_open if key=='raw' else f.open;c=f.raw_close if key=='raw' else f.close;h=f.raw_high if key=='raw' else f.high;l=f.raw_low if key=='raw' else f.low
   a.vlines(x,l,h,color=colors,lw=.6);a.bar(x,c-o,bottom=o,width=.65,color=colors)
   if key=='raw':
    a.set_title(f'{sid} {name}: raw source OHLC; {selection}',loc='left',fontsize=10)
    v=a.twinx();v.bar(x,f.raw_volume,color='#aab4be',alpha=.18);v.set_ylim(0,float(f.raw_volume.max())*4);v.set_yticks([]);v.set_ylabel('raw volume (faint)',fontsize=8)
   else:a.set_title('cached continuous OHLC coordinate',fontsize=9)
   a.grid(alpha=.15);ticks=np.arange(0,len(f),40);a.set_xticks(ticks,[str(f.index[k].date()) for k in ticks],fontsize=8,rotation=15)
  factor_changes=f.index[f.adjustment_factor.ne(f.adjustment_factor.shift())][1:]
  summ.append(dict(sid=sid,name=name,selection=selection,first_day=str(f.index[0].date()),last_day=str(f.index[-1].date()),bars=len(f),raw_start=f.raw_close.iloc[0],raw_end=f.raw_close.iloc[-1],continuous_start=f.close.iloc[0],continuous_end=f.close.iloc[-1],factor_changes=[str(x.date()) for x in factor_changes],source_invalid=f.source_invalid.fillna(False).sum(),unobserved=(~f.observed_bar.fillna(False)).sum(),strict_raw_first=True,no_account_markers=True,no_signal_markers=True))
 fig.savefig(P/'SIX_RAW_OHLCV.png',dpi=140);plt.close(fig)
 save('RAW_SOURCE_BINDING.json',dict(sources=src,cases=summ,selection='post-result exploratory fixed six, not unseen validation',price_units='left actual raw OHLC; right existing continuous corporate-action coordinate; no signal recomputation',later_source_rows_physical_cutoff='2026-06-30'))
 print(json.dumps(summ,default=str,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
