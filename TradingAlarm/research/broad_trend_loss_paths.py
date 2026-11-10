"""Observed holding-path diagnostics, no hypothetical stop or peak sale."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd

OUT=Path('results/broad-trend-loss-paths')
SOURCE=Path('results/strength-range-transfer485')


def excursion(frame,entry_date,exit_date,entry_price,terminal_price,closed):
    start=pd.Timestamp(entry_date);end=pd.Timestamp(exit_date)
    observed=frame.loc[frame.observed_bar & frame.volume.gt(0)]
    held=observed.loc[(observed.index>=start)&((observed.index<end) if closed else (observed.index<=end))]
    high=max(entry_price,terminal_price,float(held.signal_high.max()) if len(held) else entry_price)
    low=min(entry_price,terminal_price,float(held.signal_low.min()) if len(held) else entry_price)
    return dict(mfe=high/entry_price-1,mae=low/entry_price-1,peak_to_terminal=terminal_price/high-1,observed_bars=len(held))


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(status='Frozen before outcomes',source=str(SOURCE),scope='base15bps,cutoff2026Oct16,three frozen models,all episodes',path='Observed positivevolume bars fromentryinclusive toexitexclusive whenclosed; appendactualexitopen as terminalpoint. Openepisodes include markday OHLC.',loss_bins='netreturn<0 with MFE<10% versus MFE>=10%; nonloss<30% versus>=30%; status separate',limits='MFE/MAE are hindsight intraday excursions, not realizable exits.10% diagnosticcutoff not optimized stop/takeprofit. Signals/data already reviewed. Synthetic sleeves,notactualshareaccount.'),indent=2))
    manifest=json.loads(Path('data/ths-refresh-20261018/validated-input-balanced-second500.json').read_text());frames={}
    for r in manifest['records']:
        path=Path('data/ths-refresh-20261018')/f"{r['ths_symbol']}-signal.parquet"
        assert hashlib.sha256(path.read_bytes()).hexdigest()==r['signal_sha256'];frames[r['symbol']]=pd.read_parquet(path)
    episodes=pd.read_parquet(SOURCE/'episodes.parquet');episodes=episodes.loc[episodes.cutoff.eq('2026-10-16')&episodes.delay.eq(0)].copy()
    ledger=pd.read_parquet(SOURCE/'tail-economics-ledger.parquet');ledger=ledger.loc[ledger.allocation.eq('equal_capital')]
    keys=['strategy','symbol','entry_date','status'];episodes=episodes.merge(ledger[keys+['pnl_initial_sleeve']],on=keys,validate='one_to_one')
    rows=[]
    for e in episodes.itertuples():
        f=frames[e.symbol];path=excursion(f,e.entry_date,e.mark_date,e.entry_price,e.exit_price,e.status=='closed')
        before=f.loc[f.observed_bar&f.volume.gt(0)&(f.index<pd.Timestamp(e.entry_date))].tail(63)
        advance=e.entry_price/before.signal_close.min()-1 if len(before)==63 else None
        category=('loss_after_10pct' if path['mfe']>=.1 else 'loss_without_10pct') if e.return15<0 else ('tail_30pct' if e.return15>=.3 else 'nonloss_below_30pct')
        rows.append(dict(strategy=e.strategy,symbol=e.symbol,entry_date=e.entry_date,year=int(e.entry_date[:4]),status=e.status,return_fraction=e.return15,pnl_initial_sleeve=e.pnl_initial_sleeve,entry_above_prior63_min=advance,category=category,**path))
    f=pd.DataFrame(rows);f.to_parquet(OUT/'episodes.parquet',index=False)
    summary=f.groupby(['strategy','status','category']).agg(n=('symbol','size'),pnl=('pnl_initial_sleeve','sum'),median_return=('return_fraction','median'),median_mfe=('mfe','median'),median_mae=('mae','median'),median_peak_to_terminal=('peak_to_terminal','median'),median_entry_advance=('entry_above_prior63_min','median'))
    summary['pnl_fraction']=summary.pnl/len(frames);summary.to_csv(OUT/'summary.csv')
    expected=ledger.groupby('strategy').pnl_initial_sleeve.sum();actual=f.groupby('strategy').pnl_initial_sleeve.sum();np.testing.assert_allclose(actual,expected,atol=1e-12)
    (OUT/'validation.json').write_text(json.dumps(dict(input_hashes=len(frames),episode_rows=len(f),max_reconciliation_error=float((actual-expected).abs().max())),indent=2))
    print(summary.to_string())


if __name__=='__main__':main()
