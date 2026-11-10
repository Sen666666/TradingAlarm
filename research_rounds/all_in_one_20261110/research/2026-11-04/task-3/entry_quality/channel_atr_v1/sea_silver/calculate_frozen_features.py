"""Frozen OHLC features only. No account, position, sizing or return calculation."""
from pathlib import Path
import importlib.util
import json, hashlib, csv
import pandas as pd
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
HELPER=ROOT/'indicators.py'
SPEC=ROOT/'PAPER_SPEC.md'
OUT=HERE/'frozen_features'
KEYS={'002583.SZ':['2024-09-19','2024-09-20','2024-09-23','2024-09-24','2024-09-30','2024-10-10','2024-10-11','2024-11-01','2024-11-04'],
      '300085.SZ':['2024-09-24','2024-09-30','2024-10-08','2024-10-09','2024-10-10','2024-10-11','2024-10-14','2024-10-16']}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if x is None or x is pd.NA:return None
    if isinstance(x,np.generic):x=x.item()
    return None if isinstance(x,float) and not np.isfinite(x) else x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    OUT.mkdir(exist_ok=False)
    sources={str(p):sha(p) for p in [HELPER,SPEC,Path(__file__)]}
    spec=importlib.util.spec_from_file_location('frozen_channel_atr',HELPER);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    keys=[];prefix_checks=[];bounds=[]
    for sid,days in KEYS.items():
        p=HERE/(sid.replace('.','_')+'_ORIGINAL_PREFIX_OHLC.parquet');sources[str(p)]=sha(p)
        price=pd.read_parquet(p);features=helper.features(price)
        features.to_parquet(OUT/(sid.replace('.','_')+'_FULL_PREFIX_FEATURES.parquet'))
        joined=price.join(features.add_prefix('feature__'))
        joined.loc['2024-09-01':'2024-11-29'].to_parquet(OUT/(sid.replace('.','_')+'_SEP_NOV_OHLC_AND_FEATURES.parquet'))
        cut='2024-10-11';shorter=helper.features(price.loc[:cut]);assert shorter.equals(features.loc[:cut])
        prefix_checks.append(dict(sid=sid,cutoff=cut,exact_all_helper_columns=True))
        for day in days:
            p=price.loc[day];f=features.loc[day]
            keys.append(dict(sid=sid,day=day,**{k:p[k] for k in ['open','high','low','close','raw_open','raw_high','raw_low','raw_close','adjustment_factor','source_kind','source_invalid','synthetic_event_bar']},
                **f.to_dict(),ready_to_use_previous_bar_ATR=True if pd.notna(f.ATR14_prior) else False))
        bounds.append(dict(sid=sid,original_first_day=str(price.index[0].date()),full_rows=len(price),
                           invalid_source_rows=int((~features.valid_bar).sum()),display_rows=len(features.loc['2024-09-01':'2024-11-29'])))
    save('FIXED_KEY_DAYS.json',keys)
    with (OUT/'FIXED_KEY_DAYS.csv').open('w',newline='') as out:
        w=csv.DictWriter(out,fieldnames=list(keys[0]));w.writeheader();w.writerows(clean(keys))
    save('PREFIX_CHECKS.json',prefix_checks)
    assert all(sha(p)==expected for p,expected in sources.items())
    save('FEATURE_RECEIPT.json',dict(status='FROZEN_OHLC_FEATURES_COMPLETE',source_sha256=sources,full_prefix=bounds,
       helper_seed='First true bar TR=H-L; first14 TR arithmetic mean; subsequent Wilder',prior_only=True,
       new_strategy_positions=0,new_accounts=0,new_quantities=0,new_returns=0,parameter_selection=False))
    save('OUTPUT_SHA256.json',{str(p):sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
    print(json.dumps(clean([{k:r[k] for k in ['sid','day','raw_close','close','U20','U55','ATR14_prior','z20','z55','rolloff20','rolloff55']} for r in keys]),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
