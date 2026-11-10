"""Before economic accounts: raw-price charts and exact prefix-causal checks."""
from pathlib import Path
import os,json,datetime
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/a-selection-mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import pandas as pd,numpy as np
from current_pool_bridge import load_bundle,build_series,prepare_signal,state_frame,sha256,source_segments
from build_inputs import HERE,read,write,now,ref

def main():
 out=HERE/'audit/signal-review-v1';out.mkdir(exist_ok=False)
 b=load_bundle(HERE/'inputs-v1/input-manifest.json');pm=read(HERE/'prepared-v1/manifest.json');saved={x['series_id']:x for x in pm['series']}
 # Fixed identities plus deterministic corporate-action cases, never selected by returns.
 ids=['600519.SH','600036.SH','000858.SZ','002415.SZ','300750.SZ','688981.SH','920185.BJ','920982.BJ','URFI881121','URFI881155','URFI881101']
 actions=read(HERE/'inputs-v1/action-normalization.json')
 ids+=sorted(x['symbol'] for x in actions if 'rights_issue_no_subscription' in x['classifications'])[:3]
 ids=list(dict.fromkeys(s for s in ids if s in b.series));results=[];font=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
 metadata=read(HERE/'inputs-v1/metadata.json')
 for sid in ids:
  item=build_series(b.series[sid].record,b.manifest_path.parent,b.manifest['scope_date'])
  if item.blocked_reason:raise ValueError(sid+':'+item.blocked_reason)
  saved_state=pd.read_parquet(HERE/'prepared-v1'/saved[sid]['files']['states']['path'])
  pd.testing.assert_frame_equal(item.states,saved_state,check_exact=True,check_freq=False)
  for cutoff in ['2017-12-31','2020-12-31','2023-12-31']:
   compared=0
   for n,part in enumerate(source_segments(item.raw,item.record)):
    raw=item.raw.loc[part['start']:part['end']].loc[:cutoff]
    if len(raw)<65 or not (raw.volume>0).any():continue
    sig=prepare_signal(raw,item.record,item.action_policy.get('events',[]));eligible,event,state,memory=state_frame(sig)
    for frame in [sig,event,state]:frame['segment_id']=n
    for name,prefix in [('signal',sig),('events',event),('states',state)]:
     full=getattr(item,name);full=full.loc[full.segment_id==n].loc[:cutoff]
     pd.testing.assert_frame_equal(prefix,full,check_exact=True,check_freq=False)
    compared+=len(state)
   results.append(dict(series_id=sid,cutoff=cutoff,compared_observations=compared,exact=True))
  signal=item.signal;state=item.states;raw=item.raw
  fig,(ax,av)=plt.subplots(2,1,figsize=(14,6),sharex=True,gridspec_kw={'height_ratios':[4,1]})
  ax.plot(raw.index,raw.close,lw=.75,color='#253858',label='Raw close')
  floor=state.floor.reindex(signal.index)/signal.adjustment_factor
  ax.plot(floor.index,floor,color='#d48b19',lw=.7,label='E0 causal support in raw coordinates')
  for col,color,mark in [('entered','#159265','^'),('exited','#d34a50','v')]:
   d=state.index[state[col].eq(1)];price=signal.loc[d,'close']/signal.loc[d,'adjustment_factor']
   ax.scatter(d,price,s=10,c=color,marker=mark,label='E0 '+col,zorder=3)
  ax.set_yscale('log');ax.grid(alpha=.15);ax.legend(fontsize=8)
  ax.set_title(sid+' '+metadata.get(sid,{}).get('name','')+' | 原价、当时支持与确认日',fontproperties=font)
  av.bar(raw.index,raw.volume,width=1.2,color='#bcc8d8');av.set_ylabel('Volume')
  fig.tight_layout();fig.savefig(out/(sid+'.png'),dpi=130);plt.close(fig)
 write(out/'prefix-checks.json',dict(recorded_at=now(),identities_fixed_before_accounts=ids,checks=results,
  exact_state_identity_vs_parallel_writer=True,algorithm_changes=0,account_runs=0,
  limitations='Representative formula/adjustment prefixes; whole-universe account prefixes checked separately. Diagnostic memory ledgers can contain later resolution fields and are never account inputs.'))
 print({'identities':len(ids),'prefix_checks':len(results),'observations':sum(x['compared_observations'] for x in results)},flush=True)

if __name__=='__main__':main()
