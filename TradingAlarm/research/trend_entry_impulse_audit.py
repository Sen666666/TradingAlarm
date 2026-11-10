"""Endpoint-score attribution to final two observed bars; descriptive, not a trading filter."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from adaptive_geometric_strength import adaptive_frame,fit_experts
from ths_volume_units import ths_split_consistent_volume
OUT=Path('results/trend-entry-impulse-audit')

def snapshot(close,volume,weights):
    y=np.log(np.asarray(close,float));v=np.asarray(volume,float);r=np.diff(y)
    assert len(y)==21 and len(v)==21
    actual,_=fit_experts(y,v);flat=y.copy();flat[-2:]=flat[-3];without,_=fit_experts(flat,v)
    velocity=float(np.asarray(weights)@actual);removed=float(np.asarray(weights)@(actual-without))
    return dict(last2_return=float(np.expm1(y[-1]-y[-3])),prior18_return=float(np.expm1(y[-3]-y[0])),positive_fraction=float((r>0).mean()),path_efficiency=float(r.sum()/np.abs(r).sum()) if np.abs(r).sum()>0 else 0.,velocity=velocity,last2_velocity_contribution=removed,last2_velocity_fraction=removed/velocity if abs(velocity)>1e-12 else None)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(scope='Existing adaptive485stock entry episodes,2024-2026; diagnostic not threshold search',method='21observedclose fit window; replace final2logprices with preceding close, hold observed volume, original expertweights and RMS fixed; measure endpoint velocity difference. Attribution not counterfactual full model prediction.',outcomes='Closed episode returns and tail>=30 grouped by entryyear; open separately retained; same-entrydate strength quintiles with >=5candidates',limits=['Future returns used only as labels','No stop/entry filter adopted','Historical surviving universe and correlated episodes','Contribution can exceed1 or be negative, not a probability'])
    p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==protocol
    p.write_text(json.dumps(protocol,indent=2))
    e=pd.read_parquet('results/sector-episode-allocation/candidate-input.parquet');root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());rows=[];checks=0
    for rec in manifest['records']:
        p=root/f"{rec['ths_symbol']}-signal.parquet";q=root/'rights'/f"{rec['ths_symbol']}.json"
        assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['signal_sha256'];assert hashlib.sha256(q.read_bytes()).hexdigest()==rec['rights_sha256']
        f=pd.read_parquet(p);v=ths_split_consistent_volume(f.volume,json.loads(q.read_text()));obs=f.loc[f.observed_bar&f.volume.gt(0)];a=adaptive_frame(obs.signal_close,obs.close,v.reindex(obs.index))
        for row in e.loc[e.symbol.eq(rec['symbol'])].to_dict('records'):
            past=obs.loc[:row['signal_date']].iloc[-21:];state=a.loc[:row['signal_date']].iloc[-1];assert np.isclose(state.strength,row['strength'],rtol=0,atol=1e-12);checks+=1
            x=snapshot(past.signal_close,v.reindex(past.index),[state.linear_weight,state.quadratic_weight]);assert np.isclose(x['velocity'],state.velocity)
            rows.append(dict(row,**x,quadratic_weight=float(state.quadratic_weight)))
    allrows=pd.DataFrame(rows);allrows.to_parquet(OUT/'episodes.parquet',index=False)
    allrows['year']=pd.to_datetime(allrows.entry_date).dt.year;allrows['n']=allrows.groupby('entry_date').symbol.transform('size');f=allrows.loc[allrows.n.ge(5)].copy();f['rank']=f.groupby('entry_date').strength.rank(method='average',pct=True);f['bucket']=pd.cut(f['rank'],[0,.2,.4,.6,.8,1],labels=[1,2,3,4,5]);f['tail']=f.return15.ge(.3)
    summary=f.loc[f.status.eq('closed')].groupby(['year','bucket'],observed=True).agg(episodes=('symbol','size'),median_last2=('last2_return','median'),median_prior18=('prior18_return','median'),median_contribution=('last2_velocity_fraction','median'),median_efficiency=('path_efficiency','median'),median_quadratic_weight=('quadratic_weight','median'),mean_net_return=('return15','mean'),tail_fraction=('tail','mean'));summary.to_csv(OUT/'strength-quintiles.csv')
    f['last2_dominates']=f.last2_velocity_fraction.gt(.5)
    f.loc[f.status.eq('closed')].groupby(['year','last2_dominates']).agg(episodes=('symbol','size'),mean_net_return=('return15','mean'),tail_fraction=('tail','mean')).to_csv(OUT/'majority-contribution-diagnostic.csv')
    (OUT/'validation.json').write_text(json.dumps(dict(input_hashes=970,entry_strength_exact_checks=checks),indent=2));print(summary.to_string())
if __name__=='__main__':main()
