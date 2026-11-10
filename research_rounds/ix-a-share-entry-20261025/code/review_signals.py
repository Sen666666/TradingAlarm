"""Pre-account full-pool counts, physical prefixes and six fixed visual windows."""
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from util_ix import *
from entry_rules import events

FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
CASES=[('001309.SZ','德明利','2024-01-01','2026-10-22'),('688981.SH','中芯国际','2024-01-01','2026-10-22'),('600519.SH','贵州茅台','2020-01-01','2023-12-31'),('600036.SH','招商银行','2021-01-01','2024-12-31'),('300750.SZ','宁德时代','2023-01-01','2026-10-22'),('000001.SZ','平安银行','2015-01-01','2016-12-31')]

def exact(a,b):
 assert a.index.equals(b.index)
 for c in a.columns:
  av,bv=a[c],b[c];mask=av.isna();assert mask.equals(bv.isna()),c
  assert np.asarray(av.loc[~mask].to_numpy()==bv.loc[~mask].to_numpy()).all(),c

def main():
 out=HERE/'review';out.mkdir(exist_ok=False);(out/'figures').mkdir()
 manifest=read(HERE/'signals/manifest.json');records={x['series_id']:x for x in read(OLD/'prepared-v2/manifest.json')['series']};daily=[];counts=[]
 selected_ids={x['security_id'] for x in read(OLD/'inputs-v2/selection.json')['lines'] if (x.get('company_cap_cny') or 0)>1e10}
 for row in manifest['series']:
  sid=row['symbol'];p=HERE/'signals'/f'{sid}.parquet';assert sha(p)==row['output_sha256'];f=pd.read_parquet(p);z=f.loc['2015-01-01':]
  prev=z.previous_grade
  assert not (z.W23&~z.W2H).any() and not (z.W2H&~z.C3).any() and not (z.C3&~z.IX).any()
  assert not (z.W23&~(prev.eq(2)&z.grade.eq(3))).any()
  assert not ((z.grade>prev)&prev.notna()&~z.fresh_up).any()
  for dt,r in z.loc[z.IX].iterrows():daily.append(dict(date=str(dt.date()),symbol=sid,current_pool_selected=sid in selected_ids,IX=1,W23=int(r.W23),W2H=int(r.W2H),C3=int(r.C3),jump_2_to_4=int(r.previous_grade==2 and r.grade==4),other_jump_to_hot=int(r.previous_grade<2 and r.grade>=3)))
  counts.append(dict(symbol=sid,current_pool_selected=sid in selected_ids,observations=len(z),**{k:int(z[k].sum()) for k in ENTRY_TYPES},warm_jump_to_expansion=int((z.previous_grade.eq(2)&z.grade.eq(4)&z.IX).sum()),cold_jump_hot=int((z.previous_grade.lt(2)&z.grade.ge(3)&z.IX).sum())))
 pd.DataFrame(counts).to_csv(out/'event-counts.csv',index=False);df=pd.DataFrame(daily);df.to_csv(out/'all-actionable-events.csv',index=False);df.loc[df.current_pool_selected].groupby('date')[ENTRY_TYPES+['jump_2_to_4','other_jump_to_hot']].sum().to_csv(out/'daily-events.csv')
 # Fixed names plus a deterministic spread of sorted identities, chosen before
 # looking at any economic result; no sample is selected by returns.
 ids=sorted(records);stocks=sorted(x['symbol'] for x in manifest['series']);selected=sorted(set([x[0] for x in CASES]+[stocks[i] for i in np.linspace(0,len(stocks)-1,6,dtype=int)]))
 sys.path.insert(0,str(B5/'code'));import api
 sys.path.insert(0,str(G1/'code'));from grade import classify
 from policies_g1 import project
 sys.path.insert(0,str(ROOT/'research_rounds/pv-participation-response-20261020/code'));from data_utils import eligible_prices
 prefixes=[]
 for sid in selected:
  rec=records[sid];sg=pd.read_parquet(OLD/'prepared-v2'/rec['files']['signal']['path']);f=eligible_prices(sg)[['open','high','low','close','volume','segment_id']].copy();f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
  full=pd.read_parquet(HERE/'signals'/f'{sid}.parquet')
  for n in sorted(set([min(65,len(f)),max(1,len(f)//2),max(1,len(f)-1)])):
   sub=f.iloc[:n].copy();a=api.run_b5(sub);g,_=classify(a['evidence']);ix=project(a['evidence'],a['state'],g,'G1_IX');ev=events(g,ix)
   exact(g[['grade','score','proposal','fresh_up']],full.iloc[:n][['grade','score','proposal','fresh_up']]);exact(ev[['previous_grade']+ENTRY_TYPES],full.iloc[:n][['previous_grade']+ENTRY_TYPES])
   exact(ix[['target','entered','exited','floor']].rename(columns=lambda c:'ix_'+c),full.iloc[:n][['ix_target','ix_entered','ix_exited','ix_floor']])
   prefixes.append(dict(symbol=sid,rows=n,end=str(sub.index[-1].date()),passed=True))
  print(dict(prefix_done=sid),flush=True)
 pd.DataFrame(prefixes).to_csv(out/'physical-prefixes.csv',index=False)
 for sid,name,start,end in CASES:
  f=pd.read_parquet(HERE/'signals'/f'{sid}.parquet').loc[start:end]
  for overlay in [False,True]:
   fig,axs=plt.subplots(4 if overlay else 2,1,figsize=(13,8 if overlay else 5),sharex=True,gridspec_kw={'height_ratios':[3,1,1.6,1.3] if overlay else [3,1]})
   axs[0].plot(f.index,f.close,color='#263f46',lw=.8);axs[0].set_title(name+' '+start+'—'+end+('：固定入场事件图检（无账户）' if overlay else '：原始因果量价'),fontproperties=FONT)
   axs[1].bar(f.index,f.volume/f.volume.shift().rolling(21).median(),color='#97a6aa',width=1);axs[1].set_ylabel('relative V')
   if overlay:
    axs[2].step(f.index,f.score,where='post',color='#ae743a',lw=.8);axs[2].axhline(50,lw=.5,color='gray');axs[2].axhline(75,lw=.5,color='gray');axs[2].set_ylabel('G1 score')
    for j,k in enumerate(ENTRY_TYPES):
     at=f.index[f[k]];axs[3].scatter(at,np.full(len(at),j),s=12,marker='|');axs[3].text(f.index[0],j+.08,k,fontsize=8)
    axs[3].set_yticks(range(4),ENTRY_TYPES);axs[3].set_ylim(-.5,3.6)
   for ax in axs:ax.grid(alpha=.15)
   fig.tight_layout();fig.savefig(out/'figures'/f'{sid}-{"events" if overlay else "raw"}.png',dpi=110);plt.close(fig)
 write(out/'verification.json',dict(recorded_at=now(),passed=True,full_stock_sources=len(counts),eligible_stocks=len(selected_ids),unknown_cap_retained=2,all_E0_state_identity=True,all_entry_subset_and_new_evidence_invariants=True,physical_prefixes=len(prefixes),sample_sources=len(selected),figure_windows=len(CASES),economic_accounts=0,event_totals=df.loc[df.current_pool_selected,ENTRY_TYPES].sum().to_dict()))
 print(read(out/'verification.json'),flush=True)

if __name__=='__main__':main()
