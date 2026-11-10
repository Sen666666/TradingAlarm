"""Prespecified separate-layer stop experiment; all markets and entry controls."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from campaign_engine import run_campaign
from hk_extension import load_extended
from trend_tail_audit import summarize

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results/campaign-layer-transfer'


def main():
    OUT.mkdir(exist_ok=True)
    protocol = dict(
        change='Each filled buy has its own fixed four-ATR stop. Stop of an add does not raise other layers stops.',
        exits='Next available open, ADV constrained. Trend exit or portfolio halt liquidates all. Split quantities tracked per layer.',
        adds='At most three lifetime layers, no new adds after first stop/exit trigger in campaign; no recycle of stopped layers.',
        risk='Same0.5% per-entry budget,4% aggregate planned risk, exposure caps and drawdown guards. Aggregate risk now summed at each layer stop. Fixed original stops retain more risk and may constrain adds.',
        cases='A/HK/mixed x MA/breakout x base/double-cost; all twelve, no parameter search.',
        costs='Base15bps+HKFX10bps;stress30bps+HKFX20bps;minimum commissions unchanged.',
        limitations='Exploratory reused survivor ETF histories; not out of sample. Campaign open PnL marked, FX attribution residual separate. Initial-R may be unstable after small initial fills.',
        evaluation='Ordinary remainder losses, sparse tail gains, account PnL/drawdown, costs; no CAGR optimization.')
    file = OUT / 'protocol.json'
    if file.exists(): assert json.loads(file.read_text()) == protocol
    file.write_text(json.dumps(protocol, indent=2))
    assets, _ = load_extended()
    # Preserve default shared-stop behavior before testing the new mode.
    _, p, o, c, s = run_campaign(assets, entry='breakout', exit_mode='trend', ranking='low_atr')
    frozen = ROOT / 'results/campaign-entry-transfer'
    pd.testing.assert_frame_equal(p, pd.read_csv(frozen/'mixed-breakout-path.csv', index_col=0, parse_dates=True), check_exact=False, rtol=1e-12, atol=1e-12)
    assert o == json.loads((frozen/'mixed-breakout-orders.json').read_text())
    assert dict(closed=c, open=s) == json.loads((frozen/'mixed-breakout-campaigns.json').read_text())
    print('Frozen shared-stop baseline reproduced.', flush=True)
    records=[]
    for market in ['A','HK','mixed']:
        chosen={n:a for n,a in assets.items() if market=='mixed' or a['currency']==('CNY' if market=='A' else 'HKD')}
        for entry in ['ma','breakout']:
            for stress in [False,True]:
                name=f'{market}-{entry}-layers'+('-cost2' if stress else '')
                m,p,o,c,s=run_campaign(chosen,entry=entry,exit_mode='trend',ranking='low_atr',stop_mode='layers',cost_bps=30 if stress else 15,fx_bps=20 if stress else 10)
                m.update(case=name,market=market,entry=entry,double_cost=stress);records.append(m)
                p.to_csv(OUT/(name+'-path.csv'))
                (OUT/(name+'-orders.json')).write_text(json.dumps(o))
                (OUT/(name+'-campaigns.json')).write_text(json.dumps(dict(closed=c,open=s)))
                (OUT/'results.json').write_text(json.dumps(records,indent=2))
                stats=summarize(c)
                print(name,json.dumps(dict(return_total=m['total_return'],drawdown=m['max_drawdown'],closed=len(c),open=len(s),ordinary=stats['ordinary_pnl'],tail=stats['top10_pnl'])),flush=True)
    (OUT/'engine-sha256.txt').write_text(hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest())


if __name__=='__main__':main()
