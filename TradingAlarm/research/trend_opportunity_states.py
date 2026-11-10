"""Causal price/volume strata for existing future first-passage labels.
No classifier fitting, trading changes, sector selection, or winning-only fit.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from volume_units import split_consistent_volume
from trend_first_passage_audit import MODELS

OUT=Path('results/trend-opportunity-states')


def path_states(close,volume):
    r21=np.log(close/close.shift(21));r63=np.log(close/close.shift(63))
    activity=volume/volume.shift().rolling(21).median()
    regime=np.select([r21.gt(0)&r63.gt(0),r21.gt(0)&r63.le(0),r21.le(0)&r63.gt(0)],['up_up','rebound','pullback'],default='down_down')
    f=pd.DataFrame(dict(r21=r21,r63=r63,relative_volume=activity,regime=regime,activity=np.where(activity.ge(1),'above_median','below_median')),index=close.index)
    return f.loc[r21.notna()&r63.notna()&activity.notna()]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(status='Frozen before outcomes',features='sign(log close/close21), sign(log close/close63), current split-consistent volume divided by prior21 median',bins='Four fixed sign quadrants; activity>=1 or<1. Zero treated nonpositive.',labels='Unchanged existing63-session +30% before -10% labels; all outcomes retained',comparison='Group/year/regime and group/year/regime/activity. Report missed up_first date coverage for all four frozen models.',sensitivity='Select every63rd observed position per symbol, anchored at raw series start, then intersect eligible labels. Reduces within-symbol overlap but does not remove cross-symbol correlation.',limits='Descriptive development diagnostic. Sign quadrants are coarse labels, not proof of actual regimes or future continuation.'),indent=2))
    labels=pd.read_parquet('results/trend-first-passage-audit/labels-and-exposure.parquet')
    etf,_=load_extended();hk,_=load_assets();features=[]
    for group,assets in [('etf17',etf),('hk7',hk)]:
        for symbol,a in assets.items():
            raw=a['raw'];valid=raw.index[raw.volume.gt(0)].intersection(a['signal'].index)
            close=a['signal'].close.reindex(valid);v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            f=path_states(close,v);f['nonoverlap']=pd.Series(np.arange(len(valid))%63==0,index=valid).reindex(f.index)
            f['group']=group;f['symbol']=symbol;f['date']=f.index.astype(str);features.append(f.reset_index(drop=True))
    f=labels.merge(pd.concat(features),on=['group','symbol','date'],validate='one_to_one')
    assert len(f)==len(labels)
    f.to_parquet(OUT/'observations.parquet',index=False)
    summaries=[]
    for sample,df in [('all_dates',f),('nonoverlap',f.loc[f.nonoverlap])]:
        for split in ['regime','regime_activity']:
            keys=['group','year','regime']+(['activity'] if split=='regime_activity' else [])
            for key,g in df.groupby(keys):
                wins=g.label.eq('up_first');row=dict(zip(keys,key),sample=sample,split=split,n=len(g),up_first=int(wins.sum()),down_first=int(g.label.eq('down_first').sum()),neither=int(g.label.eq('neither').sum()),ambiguous=int(g.label.eq('ambiguous').sum()),up_rate=float(wins.mean()))
                for m in MODELS:
                    row[m+'_missed']=int((wins&g[m].eq(0)).sum())
                summaries.append(row)
    pd.DataFrame(summaries).to_csv(OUT/'strata.csv',index=False)
    print(pd.DataFrame(summaries).loc[lambda x:x['split'].eq('regime')&x['sample'].eq('all_dates'),['group','year','regime','n','up_first','down_first','up_rate']].to_string(index=False))


if __name__=='__main__':main()
