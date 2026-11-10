"""Isolated funded accounts distinguish opportunity economics from slot competition."""
import hashlib
import json
import math
from pathlib import Path
import pandas as pd
from campaign_engine import features, run_campaign
from hk_extension import load_extended

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/campaign-opportunity-audit'


def distribution(rows):
    v=pd.Series([x['pnl']/x['initial_risk'] for x in rows],dtype=float)
    w=v[v>0];l=v[v<0];tail=v.nlargest(max(1,math.ceil(len(v)*.1)))
    return dict(count=len(v),win_rate=float((v>0).mean()),mean_R=float(v.mean()),
        payoff=float(w.mean()/-l.mean()) if len(w) and len(l) else None,
        total_R=float(v.sum()),top10_R=float(tail.sum()),ordinary_R=float(v.drop(tail.index).sum()),
        open_count=sum(x['open'] for x in rows))


def main():
    OUT.mkdir(exist_ok=True)
    assets,_=load_extended();assets={n:a for n,a in assets.items() if a['kind']=='equity'}
    protocol=dict(universe=sorted(assets),cases='Each asset isolated;MA/breakout;noadd/sharedadd at basecost and noadd at doublecost.90cases expected for15assets.',
        isolation='Each account funded with1m CNY. No competition with other symbols. Original guards,limits,lots,FX,fees,ADV and signal/exit rules unchanged.',
        sizing='0.5% NAV planned risk each entry, capped by executable quantity;normalize actual PnL by actual initial stop-distance risk.',
        diagnosis='Noadd removes pyramid denominator ambiguity. Add cases retain known initialR caveat;report separately. No summed account return or tradable pooled NAV claim.',
        inference='All symbols,not chosen after outcomes. Report pooled campaigns, equal-symbol means and leave-one-symbol-out. Overlapping correlated trades are not independent statistical samples.',
        caveats='Reused surviving ETF universe;not individual stocks or cross-asset confirmation. Single account drawdown guards remain,so this is not unconstrained signal expectancy.',
        costs='15bps plus HKFX10bps;doublecost30bps plus HKFX20bps;minimum commissions unchanged.',
        engine_sha256=hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest())
    p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==protocol
    p.write_text(json.dumps(protocol,indent=2))
    metrics=[];campaigns=[]
    for n,a in sorted(assets.items()):
        f=features(a)
        for entry in ['ma','breakout']:
            for adds,stress in [(False,False),(True,False),(False,True)]:
                case=f'{n}-{entry}-adds{adds}-cost{2 if stress else 1}'
                m,path,orders,closed,opened=run_campaign({n:a},entry=entry,exit_mode='trend',pyramid=adds,ranking='low_atr',cost_bps=30 if stress else 15,fx_bps=20 if stress else 10)
                m.update(case=case,symbol=n,market='HK' if a['currency']=='HKD' else 'A',entry=entry,adds=adds,stress=stress)
                metrics.append(m);path.to_csv(OUT/(case+'-path.csv'))
                (OUT/(case+'-orders.json')).write_text(json.dumps(orders))
                (OUT/(case+'-campaigns.json')).write_text(json.dumps(dict(closed=closed,open=opened)))
                rows=[]
                for s,is_open in [(s,False) for s in closed]+[(s,True) for s in opened.values()]:
                    buys=[o for o in orders if o['campaign_id']==s['id'] and o['units']>0]
                    first=buys[0];risk=first['units']*4*s['entry_atr']/float(f.loc[first['date'],'factor'])*first['fx']
                    assert risk>0
                    if not adds:assert len(buys)==1
                    mark=float(path.iloc[-1]['w_'+n]*path.iloc[-1].nav*1e6) if is_open else 0.
                    pnl=mark+s['sell_cash']+s['dividend_claims']-s['buy_cash']
                    row=dict(case=case,symbol=n,market=m['market'],entry=entry,adds=adds,stress=stress,id=s['id'],entry_date=s['entry_date'],exit_date=s.get('exit_date'),open=is_open,pnl=pnl,initial_risk=risk)
                    rows.append(row);campaigns.append(row)
                m['reconciliation_residual']=m['total_return']*1e6-sum(s['pnl'] for s in rows)
        (OUT/'results.json').write_text(json.dumps(metrics,indent=2))
        (OUT/'normalized-campaigns.json').write_text(json.dumps(campaigns,indent=2))
        print(n,'completed',len(metrics),flush=True)
    summary=[]
    for entry in ['ma','breakout']:
        for adds,stress in [(False,False),(True,False),(False,True)]:
            for market in ['A','HK','all']:
                rows=[s for s in campaigns if s['entry']==entry and s['adds']==adds and s['stress']==stress and (market=='all' or s['market']==market)]
                symbols=sorted(set(s['symbol'] for s in rows))
                by_symbol={n:distribution([s for s in rows if s['symbol']==n]) for n in symbols}
                loo={n:distribution([s for s in rows if s['symbol']!=n])['mean_R'] for n in symbols}
                summary.append(dict(entry=entry,adds=adds,stress=stress,market=market,all_marked=distribution(rows),closed=distribution([s for s in rows if not s['open']]),equal_symbol_mean_R=sum(s['mean_R'] for s in by_symbol.values())/len(symbols),by_symbol=by_symbol,leave_one_out_mean_R=loo))
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    for s in summary:
        if not s['adds']:print(s['entry'],s['stress'],s['market'],s['all_marked'],flush=True)


if __name__=='__main__':main()
