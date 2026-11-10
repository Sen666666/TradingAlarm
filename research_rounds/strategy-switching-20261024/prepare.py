from pathlib import Path
import json,hashlib,sys
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from legacy import context,state
from fitted import features
from chan_signals import build
from model import POLICIES,fitted_state,chan_state,own_initial,combined
R=Path(__file__).resolve().parent;ROOT=R.parents[1];SOURCE=ROOT/'research_rounds/market-regimes-exit-20261024'
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 (R/'prepared').mkdir(exist_ok=False);(R/'review').mkdir();(R/'contexts').mkdir()
 cases=json.loads((SOURCE/'cases.json').read_text())
 cases.append(dict(id='bull_semi25_26h1',symbol='USHJ512480',name='半导体ETF',start='2025-01-02',end='2026-06-30',type='牛市',selection='prior user-requested bull window; previously studied development sample'))
 for c in cases:c['role']='fixed_scenario'
 registry=ROOT/'research_rounds/fixed-scenarios-v1';dump(registry/'cases.json',cases)
 manifest={'version':'v1','asof':'2026-10-24','cases':len(cases),'data_snapshot':{},'hindsight_labels_not_signals':True,'development_only':True}
 for symbol in sorted({c['symbol'] for c in cases}):
  p=SOURCE/'inputs'/f'{symbol}.parquet';manifest['data_snapshot'][symbol]={'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
 dump(registry/'manifest.json',manifest)
 for sym,name in [('USHJ512480','半导体ETF'),('USHJ510300','沪深300ETF'),('USHJ518880','黄金ETF'),('HK00002','中电控股'),('HK00101','恒隆地产'),('HK09618','京东集团'),('HK03033','恒生科技ETF')]:
  cases.append(dict(id='continuous_'+sym,symbol=sym,name=name,start='2021-01-01',end='2026-10-16',type='连续历史',selection='common calendar continuous check; not independent of fixed scenes',role='continuous_check'))
 dump(R/'cases.json',cases)
 for symbol in sorted({c['symbol'] for c in cases}):
  d=pd.read_parquet(SOURCE/'inputs'/f'{symbol}.parquet');assert d.index.is_unique and d.index.is_monotonic_increasing
  assert (d[['open','high','low','close','volume']]>0).all().all()
  e,base,oldf=context(d);f=features(d);ch,ev=build(d,symbol=symbol);fs=fitted_state(d,f);cs=chan_state(d,ch)
  folder=R/'contexts'/symbol;folder.mkdir();ch.to_parquet(folder/'chan.parquet');ev.to_csv(folder/'chan-events.csv',index=False)
  fs.to_parquet(folder/'fitted.parquet');cs.to_parquet(folder/'C2.parquet');f.to_parquet(folder/'features.parquet');base.to_parquet(folder/'shadow-E0.parquet')
  for c in [x for x in cases if x['symbol']==symbol]:
   out=R/'prepared'/c['id'];out.mkdir();z=d.loc[c['start']:c['end']];initial={};states={}
   for p in ['E0','E2']:states[p],initial[p]=state(d,e,base,oldf,c['start'],c['end'],policy=p)
   for p,s in [('F',fs),('C2',cs)]:states[p]=s.loc[z.index];initial[p]=own_initial(d,s,c['start'])
   for p in ['R','RC','RF','G']:states[p],initial[p]=combined(d,base,f,ch,fs,c['start'],c['end'],p)
   for p,s in states.items():s.to_parquet(out/f'{p}.parquet')
   dump(out/'initial.json',initial)
   if c['role']=='fixed_scenario':
    fig,axs=plt.subplots(4,1,figsize=(13,7.8),sharex=True,gridspec_kw={'height_ratios':[3,1,1,1]})
    axs[0].plot(z.index,z.close,color='black',lw=.8);axs[0].set_title(f"{c['id']} {c['name']} | RAW OHLCV + CAUSAL STATES (no accounts)",fontproperties=FONT)
    axs[1].bar(z.index,z.volume/z.volume.median(),width=1,color='gray');axs[1].set_ylabel('vol / median')
    for j,p in enumerate(['E0','E2','R','RC','RF','G']):axs[2].step(z.index,states[p].target*.65+j,where='post',label=p,lw=.8)
    axs[2].set_yticks(range(6),['E0','E2','R','RC','RF','G'])
    axs[3].plot(z.index,f.loc[z.index,'drift_63_PV'],label='63-day PV drift');axs[3].axhline(0,color='red',lw=.7);axs[3].legend(loc='upper right',fontsize=8)
    for ax in axs:ax.grid(alpha=.15)
    fig.tight_layout();fig.savefig(R/'review'/f"{c['id']}.png",dpi=110);plt.close(fig)
  print('prepared',symbol,len(d),flush=True)
 dump(R/'prepare.json',{'cases':len(cases),'policies':POLICIES,'accounts_run':0,'czsc_version':__import__('czsc').__version__})
if __name__=='__main__':main()
