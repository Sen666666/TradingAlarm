import json,math
from pathlib import Path
import numpy as np
import pandas as pd
from run_pv_segment_round import assets,write
from portfolio_data import fx_series


def main(out):
    groups,_=assets();report={}
    for group,items in groups.items():
        case=group+'-pv-base';p=pd.read_parquet(out/f'{case}-path.parquet');ep=json.loads((out/f'{case}-episodes.json').read_text());orders=json.loads((out/f'{case}-orders.json').read_text());decisions=json.loads((out/f'{case}-decisions.json').read_text());fx=fx_series(p.index)
        run=longest=0
        for drawdown in p.drawdown:
            run=run+1 if drawdown<0 else 0;longest=max(longest,run)
        rets=np.array([e['ret'] for e in ep if e['status']=='closed']);wins=rets[rets>0];loss=rets[rets<0]
        rows=[]
        for decision in decisions:
            day=pd.Timestamp(decision['date']);row=p.loc[day]
            for s,target in decision['targets'].items():
                a=items[s];raw=a['raw'];price=float(raw.loc[:day,'close'].iloc[-1]);rate=float(fx.loc[day]) if a['currency']=='HKD' else 1.
                held=float(row['w_'+s]*row.nav*1e6/(price*rate));remaining=target-held
                if abs(remaining)<1e-6:continue
                if day not in raw.index:reason='no_asset_session'
                elif raw.loc[day,'volume']<=0 or raw.loc[day,'high']<=raw.loc[day,'low']:reason='zero_volume_or_zero_range'
                elif 0<remaining<a['lot']-1e-6:reason='remaining_less_than_buy_lot'
                else:
                    adv=float(raw.loc[raw.index<day,'volume'].tail(20).mean())*a.get('volume_multiplier',1)
                    limit=math.floor(adv*.01/a['lot'])*a['lot']
                    used=sum(abs(o['units']) for o in orders if o['symbol']==s and o['date']==str(day.date()))
                    minimum=18*rate if a['currency']=='HKD' else 5.
                    unit=float(raw.loc[day,'open'])*rate
                    fee=max(a['lot']*unit*(25 if a['currency']=='HKD' else 15)/10000,minimum)
                    reasons=[]
                    if limit<=used+1e-6:reasons.append('prior20_volume_participation_cap')
                    if remaining>0 and row.cash<a['lot']*unit+fee:reasons.append('cash_cap')
                    reason='+'.join(reasons) or 'unresolved_requires_order_trace'
                rows.append(dict(date=str(day.date()),symbol=s,target=target,end_quantity=held,unfilled=remaining,reason=reason))
        pd.DataFrame(rows,columns=['date','symbol','target','end_quantity','unfilled','reason']).to_csv(out/f'{case}-unfilled.csv',index=False)
        report[group]={'peak_return':float(p.nav.max()-1),'max_underwater_sessions':longest,'closed_return_quantiles':{str(q):float(np.quantile(rets,q)) for q in [0,.1,.25,.5,.75,.9,1]},'average_win_return':float(wins.mean()),'average_loss_return':float(loss.mean()),'unfilled_target_days':len(rows),'unfilled_reasons':pd.Series([x['reason'] for x in rows],dtype=str).value_counts().to_dict()}
    write(out/'extra-diagnostics.json',report);print(report)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
