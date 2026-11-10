"""Calendar attribution and fixed annual cash restarts; not independent holdouts."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from campaign_engine import run_campaign
from hk_extension import load_extended

ROOT=Path(__file__).resolve().parent;SOURCE=ROOT/'results/campaign-asset-transfer';OUT=ROOT/'results/campaign-start-audit'


def annual(path):
    records=[]
    for year,g in path.groupby(path.index.year):
        value=(1+g.return_daily).cumprod()
        peak=np.maximum.accumulate(np.r_[1.,value.to_numpy()])[1:]
        records.append(dict(year=int(year),sessions=len(g),return_total=float(value.iloc[-1]-1),
            within_year_drawdown=float((value.to_numpy()/peak-1).min()),
            full_account_drawdown_min=float(g.drawdown.min()),first=str(g.index[0].date()),last=str(g.index[-1].date())))
    assert np.isclose(np.prod([1+x['return_total'] for x in records]),path.nav.iloc[-1])
    return records


def main():
    OUT.mkdir(exist_ok=True)
    engine_hash=hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest()
    assert engine_hash==json.loads((SOURCE/'protocol.json').read_text())['engine_sha256']
    protocol=dict(starts=['2023-01-01','2024-01-01','2025-01-01','2026-01-01'],
        cases='All4annualstarts x base,doublecost,delay1;fixed2022start previously saved as reference.',
        unchanged='All17ETF names;55highbreakout,4ATRinitialstop,MA200trendexit,noadds,lowATRpriority,fullcapacity,0.5%entry/4%aggregate risk and existing guards.',
        restart='One million CNY cash at each start,prior data retained only for features;zero inherited positions and dividends. All finish at same data end.',
        interpretation='Overlapping calendar sensitivity,not independent samples or unseen validation. No choice of best starting year. Annualoriginalpath keeps inherited holdings;freshstart resets economic exposure.',
        engine_sha256=engine_hash)
    target=OUT/'protocol.json'
    if target.exists():assert json.loads(target.read_text())==protocol
    target.write_text(json.dumps(protocol,indent=2))
    original={s:pd.read_csv(SOURCE/f'all-{s}-path.csv',index_col=0,parse_dates=True) for s in ['base','cost2','delay1']}
    (OUT/'original-annual.json').write_text(json.dumps({s:annual(p) for s,p in original.items()},indent=2))
    assets,_=load_extended();rows=[]
    for start in protocol['starts']:
        for scenario in original:
            case=start[:4]+'-'+scenario
            m,p,o,c,s=run_campaign(assets,start=start,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(assets),eligible_kinds=('equity','defensive'),cost_bps=30 if scenario=='cost2' else 15,fx_bps=20 if scenario=='cost2' else 10,extra_delay=1 if scenario=='delay1' else 0)
            before=original[scenario].loc[original[scenario].index<p.index[0],'nav'].iloc[-1]
            m.update(case=case,start=start,scenario=scenario,original_account_same_period_return=float(original[scenario].nav.iloc[-1]/before-1))
            rows.append(m);p.to_csv(OUT/(case+'-path.csv'));(OUT/(case+'-orders.json')).write_text(json.dumps(o));(OUT/(case+'-campaigns.json')).write_text(json.dumps(dict(closed=c,open=s)));(OUT/(case+'-annual.json')).write_text(json.dumps(annual(p),indent=2));(OUT/'results.json').write_text(json.dumps(rows,indent=2))
            print(case,{k:m[k] for k in ['total_return','max_drawdown','original_account_same_period_return','closed_campaigns','open_campaigns']},flush=True)


if __name__=='__main__':main()
