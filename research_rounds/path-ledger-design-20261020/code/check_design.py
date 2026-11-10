import hashlib,json
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from path_ledger import cancel
b=Path(__file__).resolve().parents[1];out=b/'results';p=json.loads((out/'protocol.json').read_text());sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for name,digest in p['code'].items():assert sha(b/'code'/name)==digest
for name,digest in p['inputs'].items():assert sha(Path(name))==digest
assert not (out/'summary.json').exists()
paths={'loop':([.02,-.02],[4,1]),'revisit':([.02,-.02,.02],[4,1,1]),'partial_pullback':([.02,.03,-.01],[1,4,1]),'reverse':([.02,.03,-.06],[1,4,1]),'recover_late':([.04,-.06,.04],[1,4,1]),'fall_late':([.04,.04,-.06],[1,1,4])}
examples=[]
for name,(moves,weights) in paths.items():
 r=cancel(moves,weights);examples.append(dict(name=name,moves=moves,weights=weights,**r))
assert cancel([.02,-.02],[4,1])['fragments']==[]
assert cancel([.02,-.02,.02],[4,1,1])['fragments']==[[.02,1.,2]]
rng=np.random.default_rng(20261020)
for i in range(1000):
 moves=rng.normal(0,.02,63);weights=np.exp(rng.normal(0,.7,63));r=cancel(moves,weights)
 assert np.isclose(r['net'],sum(moves),atol=1e-12)
 assert np.isclose(r['retained_absolute'],abs(sum(moves)),atol=1e-12)
 assert np.sign(r['weighted'])==np.sign(sum(moves))
 rows=[]
 for j in [10,30,63]:
  a=cancel(moves[:j],weights[:j]);changed=moves.copy();changed[j:]*=-10
  assert a==cancel(changed[:j],weights[:j])
 assert np.isclose(cancel(moves,weights*100)['weighted'],r['weighted']*100)
# Inspect only fixed cases' saved causal paths, without trades or new state rules.
records=[]
for case in p['cases']:
 f=pd.read_csv(Path(p['source'])/f"{case['symbol']}-signals.csv",index_col='date',parse_dates=True)
 d=f.loc[f.close.gt(0)&f.volume.gt(0)&np.isfinite(f.close)&np.isfinite(f.volume)]
 r=np.log(d.close).diff();a=np.sqrt(d.volume/d.volume.shift().rolling(21).median()).clip(.25,4)
 target=d.loc[case['start']:case['end']].index;rr=[]
 for date in target:
  i=d.index.get_loc(date)
  if i<63 or not a.iloc[i-62:i+1].notna().all():continue
  ledger=cancel(r.iloc[i-62:i+1],a.iloc[i-62:i+1]);net=float(np.log(d.close.iloc[i]/d.close.iloc[i-63]));sigma=float(np.sqrt(np.mean(r.iloc[i-62:i+1]**2)))
  assert abs(ledger['net']-net)<1e-12
  assert (abs(net)<1e-12) or np.sign(ledger['weighted'])==np.sign(net)
  rr.append(dict(date=date,close=float(d.close.iloc[i]),net=net,weighted=ledger['weighted'],score=ledger['weighted']/(np.sqrt(63)*max(sigma,1e-8)),fragments=len(ledger['fragments'])))
 df=pd.DataFrame(rr).set_index('date');df.to_csv(out/f"{case['id']}-ledger.csv")
 records.append(dict(id=case['id'],observations=len(df),sign_mismatches=int(((df.net.abs()>1e-12)&(np.sign(df.net)!=np.sign(df.weighted))).sum())))
 fig,ax=plt.subplots(2,1,figsize=(10,5),sharex=True);ax[0].plot(df.index,df.close,color='black');ax[0].set_yscale('log');ax[0].set_title(case['id']+' chronological cancellation is not a state model');ax[1].plot(df.index,df.net,label='63-return net');ax[1].plot(df.index,df.weighted,label='weighted surviving displacement');ax[1].axhline(0,color='gray');ax[1].legend();fig.tight_layout();fig.savefig(out/f"{case['id']}-ledger.png",dpi=100);plt.close(fig)
summary=dict(examples=examples,random_invariant_tests=1000,price_prefix_tests=3000,cases=records,conclusion='Correct cancellation prevents resurrection but positive-weight score sign is identically endpoint return sign. Do not promote as new path-state estimator.')
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
