"""Fixed four-slot versus full-universe capacity at unchanged total risk limits."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import pandas as pd
from campaign_engine import run_campaign
from hk_extension import load_extended
from trend_tail_audit import summarize

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/campaign-capacity-audit'
CONTROL=ROOT/'results/campaign-opportunity-audit/funded-noadd'


def main():
    OUT.mkdir(exist_ok=True)
    protocol=dict(change='max_positions4 versus eligible equity universe size;no intermediate capacity search',
        fixed='55daybreakout,trendexit,noadds,lowATRpriority,risk0.5%,aggregate4%,gross90%,single35%,sector45%,HK50%,drawdown guards,initial1mCNY',
        cases='A/HK/mixed x base/doublecost x four/fullcapacity;all12reported',
        interpretation='Broader capacity at identical limits is not identical realized risk. No leverage or total-risk budget increase.',
        limitations='Repeated surviving ETF histories,not holdout or individual-stock/cross-asset proof.',
        engine_sha256=hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest())
    f=OUT/'protocol.json'
    if f.exists():assert json.loads(f.read_text())==protocol
    f.write_text(json.dumps(protocol,indent=2))
    assets,_=load_extended();records=[];audits=[]
    for market in ['A','HK','mixed']:
        chosen={n:a for n,a in assets.items() if a['kind']=='equity' and (market=='mixed' or a['currency']==('CNY' if market=='A' else 'HKD'))}
        for stress in [False,True]:
            for capacity in ['four','full']:
                name=f'{market}-{capacity}'+('-cost2' if stress else '')
                decisions=[]
                m,p,o,c,s=run_campaign(chosen,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=4 if capacity=='four' else len(chosen),cost_bps=30 if stress else 15,fx_bps=20 if stress else 10,decision_audit=decisions)
                if capacity=='four':
                    key=market+('-cost2' if stress else '')
                    pd.testing.assert_frame_equal(p,pd.read_csv(CONTROL/(key+'-path.csv'),index_col=0,parse_dates=True),check_exact=False,rtol=1e-12,atol=1e-12)
                    assert o==json.loads((CONTROL/(key+'-orders.json')).read_text())
                    assert dict(closed=c,open=s)==json.loads((CONTROL/(key+'-campaigns.json')).read_text())
                sizing=[e for e in decisions if e['event']=='sizing']
                for e in sizing:
                    if e['units']>0:assert e['planned_risk_before']+e['planned_risk_added']<=e['planned_risk_limit']+1e-6
                assert p.cash.min()>=-1e-6
                zero=[e for e in sizing if e['units']==0]
                a=summarize(c)
                m.update(case=name,market=market,capacity=capacity,double_cost=stress,ordinary_pnl=a['ordinary_pnl'],tail_pnl=a['top10_pnl'],win_rate=a['win_rate'],peak_names=int((p.filter(like='w_')>0).sum(axis=1).max()))
                records.append(m)
                audits.append(dict(case=name,rejections=dict(Counter(e['reason'] for e in decisions if e['event']=='rejected')),zero_size_attempts=len(zero),zero_constraints={k:sum(e[k]==0 for e in zero) for k in ['risk_units','exposure_units','cash_units','adv_units','target_units']},note='Repeated blocked daily attempts,not unique missed trades;multiple constraints can co-occur.'))
                p.to_csv(OUT/(name+'-path.csv'));(OUT/(name+'-orders.json')).write_text(json.dumps(o));(OUT/(name+'-campaigns.json')).write_text(json.dumps(dict(closed=c,open=s)))
                (OUT/(name+'-decisions.json')).write_text(json.dumps(decisions))
                (OUT/'results.json').write_text(json.dumps(records,indent=2));(OUT/'constraints.json').write_text(json.dumps(audits,indent=2))
                print(name,{k:m[k] for k in ['total_return','max_drawdown','ordinary_pnl','tail_pnl','peak_names']},flush=True)


if __name__=='__main__':main()
