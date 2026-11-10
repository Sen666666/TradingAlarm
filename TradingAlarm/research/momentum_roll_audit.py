"""Attribute rolling momentum sign flips to new return versus expired return."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
OUT=Path('results/momentum-roll-audit')
def flips(close,h):
    log=np.log(close);r=log.diff();m=log-log.shift(h);prior=m.shift();old=r.shift(h)
    changed=m.gt(0).ne(prior.gt(0))&m.notna()&prior.notna();current_only=prior+r;roll_only=prior-old
    same_current=current_only.gt(0).eq(m.gt(0));same_roll=roll_only.gt(0).eq(m.gt(0))
    kind=np.select([same_current&same_roll,same_current&~same_roll,~same_current&same_roll],['either_sufficient','new_only','roll_only'],default='joint_required')
    f=pd.DataFrame(dict(close=close,horizon=h,momentum=m,previous=prior,new_return=r,expired_return=old,side=np.where(m.gt(0),'enter','exit'),kind=kind),index=close.index)
    return f.loc[changed]

def observations(group,symbol,close):
    out=[]
    for h in [21,63]:
        events=flips(close,h);future=close.shift(-21)/close-1
        for d,row in events.iterrows():
            if d<pd.Timestamp('2024-01-01') or d>pd.Timestamp('2026-10-16'):continue
            out.append(dict(group=group,symbol=symbol,date=str(d.date()),year=d.year,**row.to_dict(),forward21=float(future.loc[d]) if pd.notna(future.loc[d]) else None))
    return out

def main():
    OUT.mkdir(exist_ok=True,parents=True);protocol=dict(period='2024-2026Oct16',horizons=[21,63],identity='m_t=m_previous+r_new-r_expired; classify native signcross by whether new-only or expired-only counterfactual gives actualnewsign',categories=['new_only','roll_only','either_sufficient','joint_required'],outcomes='Next21rowclose return,completehorizononly; flips useallavailablewarmup; no actualtradefilter added',scope='ETF17/HK7 sourcecalendars;485Aobservedpositivevolume rows; horizons therefore may differ incalendar duration',limits='Counterfactual arithmeticattribution notcausalprofitproof. Turningdatecurrentknown,labelsfuture. Overlappingevents,selectedsurvivors,development data. Rollingexpirycancarryusefulinformation; not assumednoise.')
    p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==protocol
    p.write_text(json.dumps(protocol,indent=2));etf,_=load_extended();hk,_=load_assets();rows=[]
    for group,assets in [('etf17',etf),('hk7',hk)]:
        for s,a in assets.items():rows+=observations(group,s,a['signal'].close.loc[:'2026-10-16'])
    root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());verified=0
    for r in manifest['records']:
        p=root/f"{r['ths_symbol']}-signal.parquet";assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256'];verified+=1
        f=pd.read_parquet(p).loc[:'2026-10-16'];c=f.loc[f.observed_bar&f.volume.gt(0),'signal_close'];rows+=observations('a485',r['symbol'],c)
    f=pd.DataFrame(rows);assert np.allclose(f.momentum,f.previous+f.new_return-f.expired_return,rtol=1e-10,atol=1e-12);f.to_parquet(OUT/'events.parquet',index=False)
    summary=f.groupby(['group','horizon','year','side','kind']).agg(events=('symbol','size'),mature=('forward21','count'),mean_forward21=('forward21','mean'),median_forward21=('forward21','median'));summary.to_csv(OUT/'summary.csv')
    totals=f.groupby(['group','horizon','side','kind']).size().rename('events').reset_index();totals['fraction']=totals.events/totals.groupby(['group','horizon','side']).events.transform('sum');totals.to_csv(OUT/'mechanism-fractions.csv',index=False)
    (OUT/'validation.json').write_text(json.dumps(dict(stock_hashes_verified=verified,events=len(f),mature=int(f.forward21.notna().sum()),identity_checks=len(f)),indent=2));print(totals.to_string(index=False))
if __name__=='__main__':main()
