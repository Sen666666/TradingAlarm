"""Frozen four consumed-development source OHLCV, before state overlay."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent;O=P/'absolute_loss_2022_2023';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 cases=json.loads((O/'FIXED_FOUR_CASES.json').read_text())['cases'];mp=W/'pvr-slot1-native-readiness-20261101/preflight-development-v1/SCORES_MANIFEST.json';meta={x['symbol']:x for x in json.loads(mp.read_text())['entries']};sources={str(mp):sha(mp)}
 fig,aa=plt.subplots(4,1,figsize=(17,14),layout='constrained')
 for a,c in zip(aa,cases):
  sid=c['sid'];e=meta[sid];p=Path(e['source']);assert sha(p)==e['source_sha256'];sources[str(p)]=sha(p);lo,hi=('2022-01-01','2023-12-29') if c['scope']=='2022_2023' else ('2025-07-01','2026-06-30');f=pd.read_parquet(p).loc[lo:hi];f.to_csv(O/(sid+'-RAW_SOURCE.csv'));x=np.arange(len(f));colors=np.where(f.raw_close>=f.raw_open,'#b84c4c','#238a78');a.vlines(x,f.raw_low,f.raw_high,color=colors,lw=.6);a.bar(x,f.raw_close-f.raw_open,bottom=f.raw_open,width=.7,color=colors);v=a.twinx();v.bar(x,f.raw_volume,color='#9aa8b6',alpha=.18);v.set_ylim(0,float(f.raw_volume.max())*4);v.set_yticks([]);v.set_ylabel('source raw volume',fontsize=8);a.set_title(f'{sid} {lo}..{hi}: source raw OHLCV only; {c["criterion"]}',loc='left',fontsize=10);ticks=np.arange(0,len(f),60);a.set_xticks(ticks,[str(f.index[i].date()) for i in ticks],fontsize=8);a.grid(alpha=.15)
 fig.savefig(O/'FOUR_RAW_OHLCV.png',dpi=140);plt.close(fig);(O/'RAW_SOURCE_BINDING.json').write_text(json.dumps(dict(sources=sources,script_sha256=sha(__file__),new_signals=0,new_account_events=0,source_physically_sliced_before_plot=True),indent=2))
if __name__=='__main__':main()
