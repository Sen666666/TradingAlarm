"""Frozen individual-asset trend transfer; no reinvestment or portfolio claim."""
import json
import numpy as np
import pandas as pd
from campaign_engine import features
from portfolio_data import total_return_frame
from a_stock_campaign_signals import campaigns
from build_stock_features import ROOT


def load(symbol, distribution_path=None):
    raw=pd.read_parquet(ROOT/f'data/global-transfer/{symbol}-ohlcv.parquet')
    events=json.loads((distribution_path or ROOT/f'data/global-transfer/{symbol}-distributions.json').read_text())
    div=[dict(ex_date=e['ex_date'],amount=e['amount']) for e in events]
    a=dict(raw=raw,signal=total_return_frame(raw,div,[]),dividends=div,splits=[],currency='USD')
    feat=features(a)
    frame=feat.rename(columns=dict(close='signal_close',atr='atr20',upper='breakout55',ma='sma200',trend_exit='exit_signal'))
    frame['observed_bar']=True;frame['positive_volume']=raw.volume.gt(0);frame['date']=frame.index
    return raw,events,frame


def run_period(symbol,raw,events,frame,start,end):
    f=frame[frame.date.le(pd.Timestamp(end))];cutoff=f.date.max()
    mask=pd.Series(~np.isclose(raw.high,raw.low,rtol=1e-10,atol=1e-10),index=raw.index)
    rows=campaigns(f.reset_index(drop=True),f.open,symbol,cutoff,start=start,execution_mask=mask)
    for r in rows:
        entry=pd.Timestamp(r['entry_date']);last=pd.Timestamp(r['exit_date'] or r['mark_date'])
        raw_entry=float(raw.loc[entry,'open'])
        raw_last=float(raw.loc[last,'open' if r['status']=='closed' else 'close'])
        entitled=sum(e['amount'] for e in events if entry<pd.Timestamp(e['ex_date'])<=last)
        economic=raw_last-raw_entry+entitled
        assert np.isclose(economic,r['exit_price']-r['entry_price'],rtol=1e-10,atol=1e-8)
        r.update(period_start=start,period_end=str(cutoff.date()),raw_entry=raw_entry,raw_exit_or_mark=raw_last,
                 distribution_entitlement_per_unit=entitled,economic_pnl_before_cost_per_unit=economic)
        for cost in (15,30):
            fee=(raw_entry+(raw_last if r['status']=='closed' else 0))*cost/10000
            r[f'R_cost{cost}']=(economic-fee)/r['risk_distance']
        r['price_move']=raw_last/raw_entry-1
    return rows


def main():
    out=ROOT/'results/global-signal-transfer';out.mkdir(exist_ok=True)
    frozen=json.loads((ROOT/'results/global-transfer-freeze/protocol.json').read_text())
    protocol=dict(rule=frozen['rule'],mode='Individual-asset no-add signals only;finitecapital/completion account awaits settlementdata.',
        blocks=[['2007-01-01','2012-12-31'],['2013-01-01','2018-12-31'],['2019-01-01','2025-12-31'],['2007-01-01','2025-12-31']],
        accounting='No splits inusedwindow;rawpricechange plus distributions exafterentry throughpositionexit/mark. Entryonexdate getsnone;exitonexdate retainsentitlement. Feesonrawprices,not additiveadjustedprice. Distributions are accruedrights,not assumedcashavailable/reinvestment.',
        interpretation='R normalized by4entryATR;notportfolioyield. Closed meanspositionclosed,somedistributionsmayremainreceivable. Entirehistory overlaps3fixedblocks;noindependenceclaim orblockselection. Currentvintagevendorpricesandrounding;selectedsurvivors.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    rows=[];summaries=[]
    for symbol in frozen['universe']:
        raw,events,frame=load(symbol)
        for start,end in protocol['blocks']:
            records=run_period(symbol,raw,events,frame,start,end);rows.extend(records);d=pd.DataFrame(records)
            assert len(d)>0 and not d.status.eq('terminal_unknown').any()
            for cost in (15,30):
                values=d[f'R_cost{cost}'];closed=d[d.status.eq('closed')];win=closed[f'R_cost{cost}']>0
                summaries.append(dict(symbol=symbol,start=start,end=end,cost_bps=cost,campaigns=len(d),closed=len(closed),open=int(d.status.eq('open_at_cutoff').sum()),
                    marked_mean_R=float(values.mean()),closed_mean_R=float(closed[f'R_cost{cost}'].mean()),
                    closed_win_rate=float(win.mean()),ordinary_below3R_sum=float(values[values<3].sum()),
                    tail_atleast3R_sum=float(values[values>=3].sum()),largest_marked_R=float(values.max())))
    pd.DataFrame(rows).to_parquet(out/'campaigns.parquet',index=False)
    (out/'summary.json').write_text(json.dumps(summaries,indent=2))
    for r in summaries:
        if r['start']=='2007-01-01' and r['end']=='2025-12-31' and r['cost_bps']==15:print(r)


if __name__=='__main__':main()
