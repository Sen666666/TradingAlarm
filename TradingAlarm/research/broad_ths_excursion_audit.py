"""Ex-post episode path diagnostics; no peak-price exits or tradable filter claims."""
import json,hashlib
import pandas as pd
from build_stock_features import ROOT


def excursions(frame,entry,exit_day,entry_price,exit_price):
    # Sold at exit open: exclude exit close/high/low. Include exit open mark.
    window=frame[(frame.index>=pd.Timestamp(entry))&(frame.index<pd.Timestamp(exit_day))&frame.observed_bar]
    marks=[entry_price,exit_price,*window.signal_close.tolist()]
    return dict(peak_close_return=max(marks)/entry_price-1,trough_close_return=min(marks)/entry_price-1,observed_holding_sessions=len(window))


def main(output='broad-ths-channel-pilot'):
    out=ROOT/'results'/output;data=ROOT/'data/ths-refresh-20261018'
    protocol=json.loads((out/'protocol.json').read_text())
    manifest=json.loads((ROOT/protocol['manifest']).read_text());frames={}
    for r in manifest['records']:
        p=data/f"{r['ths_symbol']}-signal.parquet";assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256']
        f=pd.read_parquet(p);previous=f.signal_close.shift();tr=pd.concat([f.signal_high-f.signal_low,(f.signal_high-previous).abs(),(f.signal_low-previous).abs()],axis=1).max(axis=1);f['atr21']=tr.rolling(21).mean();frames[r['symbol']]=f
    episodes=pd.read_parquet(out/'episodes.parquet');episodes=episodes[episodes.cutoff.eq('2026-10-16')&episodes.status.eq('closed')];rows=[]
    for e in episodes.to_dict('records'):
        f=frames[e['symbol']];prior=f.loc[:pd.Timestamp(e['signal_date'])];atr=float(prior.atr21.iloc[-1]);x=excursions(f,e['entry_date'],e['exit_date'],e['entry_price'],e['exit_price'])
        rows.append(dict(e,**x,entry_atr_fraction=atr/e['entry_price'],peak_over_entry_atr=x['peak_close_return']/(atr/e['entry_price']) if atr>0 else None,giveback_from_peak=x['peak_close_return']-e['return15']))
    table=pd.DataFrame(rows);table.to_parquet(out/'closed-excursions.parquet',index=False);reports=[]
    for (strategy,delay),g in table.groupby(['strategy','delay']):
        for cohort in ('all','entries2026'):
            h=g if cohort=='all' else g[g.entry_date.ge('2026-01-01')];loss=h[h.return15<0];win=h[h.return15>0]
            reports.append(dict(strategy=strategy,delay=int(delay),cohort=cohort,closed=len(h),losses=len(loss),losers_previously_up2atr=int(loss.peak_over_entry_atr.ge(2).sum()),losers_previously_up10pct=int(loss.peak_close_return.ge(.1).sum()),loser_median_peak=float(loss.peak_close_return.median()),loser_median_sessions=float(loss.observed_holding_sessions.median()),winner_median_sessions=float(win.observed_holding_sessions.median()),winner_median_giveback=float(win.giveback_from_peak.median())))
    (out/'excursion-audit.json').write_text(json.dumps(dict(reports=reports,meaning='Hindsight completed-episode close excursions incl exitopen,excludeexitclose.2ATR is descriptive signal-date volatility,not actual stoprisk or executable exit. Openepisodes excluded;2026closedcohort censored. No causal filter inferred.'),indent=2)+'\n')
    for r in reports:
        if r['delay']==0:print(r)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='broad-ths-channel-pilot')
    main(parser.parse_args().output)
