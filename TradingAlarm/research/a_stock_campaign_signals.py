"""Frozen daily breakout campaigns on synthetic signal prices; NOT account returns."""
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import ROOT,SOURCE,grouped
from ths_signal_adjustment import signal_frame

OUT=ROOT/'results/a-stock-campaign-signals'
COLS=['symbol','date','signal_close','observed_bar','positive_volume','atr20','breakout55','sma200','exit_signal']


def campaigns(frame,opens,symbol,cutoff,start='2022-01-01',confirm_ma=False,execution_mask=None,trail_initial_risk=False,entry_confirmation=None):
    f=frame.sort_values('date').set_index('date');op=opens.reindex(f.index).to_numpy()
    close=f.signal_close.to_numpy();atr=f.atr20.to_numpy();upper=f.breakout55.to_numpy();ma=f.sma200.to_numpy()
    active=(f.observed_bar&f.positive_volume).to_numpy();exit_signal=f.exit_signal.to_numpy();dates=f.index
    executable=np.ones(len(f),dtype=bool) if execution_mask is None else execution_mask.reindex(f.index,fill_value=False).to_numpy(dtype=bool)
    confirmed=np.ones(len(f),dtype=bool) if entry_confirmation is None else entry_confirmation.reindex(f.index,fill_value=False).fillna(False).to_numpy(dtype=bool)
    state=None;pending_exit=False;rows=[];trailing_stop=None
    for i in range(1,len(f)):
        if dates[i]<pd.Timestamp(start):continue
        if state is not None:
            if trail_initial_risk and active[i-1]:
                trailing_stop=max(trailing_stop,close[i-1]-state['risk_distance'])
            effective_stop=trailing_stop if trail_initial_risk else state['stop']
            if close[i-1]<effective_stop or exit_signal[i-1]:pending_exit=True
        if not active[i] or not executable[i] or not np.isfinite(op[i]) or op[i]<=0:continue
        if state is not None:
            if pending_exit:
                rows.append(dict(state,symbol=symbol,exit_date=str(dates[i].date()),exit_price=float(op[i]),status='closed'))
                state=None;pending_exit=False
            continue
        if confirmed[i-1] and close[i-1]>upper[i-1] and np.isfinite(ma[i-1]) and (not confirm_ma or close[i-1]>ma[i-1]) and np.isfinite(atr[i-1]) and atr[i-1]>0:
            state=dict(entry_date=str(dates[i].date()),signal_date=str(dates[i-1].date()),entry_price=float(op[i]),risk_distance=float(4*atr[i-1]),stop=float(op[i]-4*atr[i-1]))
            trailing_stop=state['stop']
    if state is not None:
        available=np.flatnonzero(active & np.isfinite(close))
        last=int(available[-1]);status='open_at_cutoff' if dates[last]==pd.Timestamp(cutoff) else 'terminal_unknown'
        rows.append(dict(state,symbol=symbol,exit_date=None,exit_price=float(close[last]),mark_date=str(dates[last].date()),status=status))
    for r in rows:
        for bps in [15,30]:
            fee=(r['entry_price']+(r['exit_price'] if r['status']=='closed' else 0))*bps/10000
            r[f'R_cost{bps}']=(r['exit_price']-r['entry_price']-fee)/r['risk_distance']
        r['price_move']=r['exit_price']/r['entry_price']-1
    return rows


def volume_confirmation(volume):
    """Signal-date shares volume above preceding20 positive observed sessions."""
    valid=volume[volume.gt(0)&np.isfinite(volume)].sort_index()
    return valid.gt(valid.shift(1).rolling(20,min_periods=20).mean()).reindex(volume.index,fill_value=False)


def main(output=OUT,confirm_ma=False,block_zero_range=False,trail_initial_risk=False,confirm_volume=False,rank_gate=None):
    output.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'data/stock-features/manifest.json').read_text())
    retired=json.loads((ROOT/'data/stock-features/ths-retired-manifest.json').read_text())
    protocol=dict(scope='All cached5204local plus acceptedTHSretired histories;no winnerselection. Daily2022+ campaign diagnostics.',
        rule='Priorclose>prior55high;MA200/ATR20 available;nextpositive-volume observed adjustedopen;4ATRinitialstop or2closesbelowMA200 exits atnexteligibleopen;noadds.',
        costs='15/30bps each side synthetic-price diagnostic;not verified stocktax/commission/limitqueue cost.',
        censored='End holdings reported separately;lastobserveddate beforeglobalcutoff terminal_unknown,never treat as realizedexit orfillfuturequotes.',
        limitations='Syntheticadjustedprices,not raw cash/shares;no totalaccount wealthclaim. IncompletePITuniverse,ST/limits,terminalproceeds andproviderrevisionhistory. Correlatedoverlapping campaigns not independent trials.',
        local_symbols=manifest['symbols'],retired_symbols=retired['symbols'])
    if confirm_ma:
        protocol['change']='Require priorclose>SMA200 as well as55highbreakout;previously declared stockprotocol rule. Allotherconditions unchanged;fullpaths rerun,not filteringpriortrades.'
    if block_zero_range:
        protocol['execution_sensitivity']='No fills on daily high==low bars within1e-10 tolerance;both buys andsells. Pendingexits persist;entries revalidated. Observedquotes still mark heldpositions. Full-daybar fill scenario,not an at-open known alpha filter or verified historical limit queue.'
    if trail_initial_risk:
        protocol['exit_experiment']='Raise protection monotonically to highest observed positive-volume close since entry minus original4ATR risk distance. Only completed prior closes used;close breach triggers next eligible open. Retain2closesbelowMA exit. No intraday stopfill or changing ATR width;no parameter search. Reused exploratory history,not holdout.'
    if confirm_volume:
        protocol['volume_experiment']='Require signal-day raw shares volume strictly above mean of preceding20 positive observed volume sessions;currentday excluded from mean. Nextopen entry,all other rules unchanged. Fixed1x/20 window,no search. Raw share volume affected by corporate actions;not turnover ratio or published-paper replication. Exploratory reused data.'
    rank_confirmations={}
    if rank_gate is not None:
        if rank_gate not in ('atr_fraction','momentum126_21') or confirm_volume:
            raise ValueError('One prespecified ranking experiment at a time;no combined volume filter')
        ranked=pd.read_parquet(ROOT/'results/a-stock-opportunity-ranking/all-candidates.parquet')
        rank_confirmations={s:pd.Series(g[rank_gate+'_quintile'].eq(1).fillna(False).to_numpy(dtype=bool),index=pd.DatetimeIndex(g.date)) for s,g in ranked.groupby('symbol')}
        protocol['rank_experiment']=f'Prior-signal-date {rank_gate} best quintile among all independent eligible breakouts,including currently held and subsequently unfilled candidates;full path rerun,not filtering oldcampaigns. No capitalallocation claim;no quintile/window search. Reused exploratory data.'
    file=output/'protocol.json'
    if file.exists():assert json.loads(file.read_text())==protocol
    file.write_text(json.dumps(protocol,indent=2))
    paths=ROOT/'data/stock-features';pf=pq.ParquetFile(paths/'local-features.parquet')
    cutoff=max(pd.to_datetime(b.column(0).to_pandas()).max() for b in pf.iter_batches(columns=['date']))
    source_iter=iter(grouped(pq.ParquetFile(SOURCE),['symbol','trade_date','open','high','low','close','volume','reference_adjustment_factor']))
    current_symbol,current=next(source_iter);allrows=[];coverage=[]
    for symbol,f in grouped(pf,COLS):
        while current_symbol<symbol:current_symbol,current=next(source_iter)
        if current_symbol!=symbol:raise ValueError('Missing source symbol '+symbol)
        raw=current.set_index('trade_date');opens=raw.open*raw.reference_adjustment_factor
        check=(raw.close*raw.reference_adjustment_factor).reindex(pd.DatetimeIndex(f.date))
        observed=f.observed_bar.to_numpy()
        if not np.allclose(check.to_numpy()[observed],f.signal_close.to_numpy()[observed],rtol=1e-10,atol=1e-8):raise ValueError('Source/feature mismatch '+symbol)
        mask=pd.Series(~np.isclose(raw.high,raw.low,rtol=1e-10,atol=1e-10),index=raw.index) if block_zero_range else None
        confirmation=volume_confirmation(raw.volume) if confirm_volume else None
        if rank_gate is not None:confirmation=rank_confirmations.get(symbol,pd.Series(dtype=bool))
        rows=campaigns(f,opens,symbol,cutoff,confirm_ma=confirm_ma,execution_mask=mask,trail_initial_risk=trail_initial_risk,entry_confirmation=confirmation);allrows.extend(dict(r,source='local') for r in rows);coverage.append(dict(symbol=symbol,source='local',campaigns=len(rows)))
        if len(coverage)%500==0:print('local symbols',len(coverage),'campaigns',len(allrows),flush=True)
    for symbol,f in grouped(pq.ParquetFile(paths/'ths-retired-features.parquet'),COLS):
        code,market=symbol.split('.');name=('USHD' if market=='SH' else 'USZD')+code+'.json'
        raw=signal_frame(json.loads((ROOT/'data/ths-raw'/name).read_text()),json.loads((ROOT/'data/ths-rights'/name).read_text()))
        mask=pd.Series(~np.isclose(raw.high,raw.low,rtol=1e-10,atol=1e-10),index=raw.index) if block_zero_range else None
        # Read actual exchange bars: synthetic corporate-action rows are not volume observations.
        volume_raw=pd.DataFrame(json.loads((ROOT/'data/ths-raw'/name).read_text())['bars'])
        volume_raw.index=pd.to_datetime(volume_raw.date)
        confirmation=volume_confirmation(volume_raw.volume) if confirm_volume else None
        if rank_gate is not None:confirmation=rank_confirmations.get(symbol,pd.Series(dtype=bool))
        rows=campaigns(f,raw.signal_open,symbol,cutoff,confirm_ma=confirm_ma,execution_mask=mask,trail_initial_risk=trail_initial_risk,entry_confirmation=confirmation);allrows.extend(dict(r,source='ths_retired') for r in rows);coverage.append(dict(symbol=symbol,source='ths_retired',campaigns=len(rows)))
    pd.DataFrame(allrows).to_parquet(output/'campaigns.parquet',index=False)
    (output/'coverage.json').write_text(json.dumps(dict(cutoff=str(cutoff.date()),symbols=len(coverage),campaigns=len(allrows),records=coverage),indent=2))
    print(pd.DataFrame(allrows).groupby(['source','status']).size().to_string(),flush=True)


if __name__=='__main__':main()
