"""Independent arithmetic audit and physical account prefixes; frozen before run."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"code"))
import numpy as np
import pandas as pd
from g1util import *

def main():
    from run_accounts import verify
    verify();summary=pd.read_csv(HERE/'summary.csv',float_precision='round_trip');details=[];prefixes=[];eng=engine()
    for x in summary.to_dict('records'):
        p=HERE/'accounts'/x['key'];l=pd.read_parquet(p/'ledger.parquet');fills=pd.read_csv(p/'fills.csv',float_precision='round_trip');trades=pd.read_csv(p/'trades.csv',float_precision='round_trip');d=pd.read_parquet(HERE/'inputs'/f"{x['symbol']}.parquet")
        s=pd.read_parquet(HERE/'prepared'/x['case']/f"{x['policy']}.parquet");cash=1.;qty=0.;navs=[];rate=.0005*(2 if x['scenario']=='cost2' else 1)
        grouped={k:v.to_dict('records') for k,v in fills.groupby('date',sort=False)}
        for dt,r in l.iterrows():
            for f in grouped.get(str(dt.date()),[]):
                raw=float(d.loc[dt,'close' if f['signal_date']=='preset_end' else 'open']);slip=raw*rate;px=raw+slip if f['side']=='buy' else raw-slip
                np.testing.assert_allclose([f['raw_price'],f['price'],f['fee'],f['slippage']],[raw,px,f['quantity']*px*rate,f['quantity']*slip],rtol=1e-12,atol=1e-12)
                if f['signal_date'] not in ['preset_start','preset_end']:
                    sig=pd.Timestamp(f['signal_date']);assert d.index.get_loc(dt)-d.index.get_loc(sig)==SCENARIOS[x['scenario']]['delay']
                    if f['side']=='buy' and x['policy'] in ['G1_I','G1_IX']:assert bool(s.loc[sig,'buy_event'])
                if f['side']=='buy':
                    assert qty==0;qty=cash/(px*(1+rate));cash-=qty*px*(1+rate);np.testing.assert_allclose(qty,f['quantity'],rtol=1e-12,atol=1e-12)
                else:
                    np.testing.assert_allclose(qty,f['quantity'],rtol=1e-12,atol=1e-12);cash+=qty*px*(1-rate);qty=0.
            nav=cash+qty*float(r.close);navs.append(nav);np.testing.assert_allclose([cash,qty,nav],[r.cash,r.quantity,r.nav],rtol=1e-11,atol=1e-12)
        navs=np.asarray(navs);dd=1-navs/np.maximum.accumulate(np.r_[1.,navs])[1:]
        np.testing.assert_allclose([navs[-1]-1,float(dd.max()),trades.net_pnl.sum(),np.prod(1+trades.net_return)-1],[x['net_return'],x['max_drawdown'],x['net_return'],x['net_return']],rtol=1e-11,atol=1e-12)
        assert len(trades)==x['trades'] and int(trades.net_return.gt(0).sum())==x['wins']
        details.append(dict(key=x['key'],rows=len(l),fills=len(fills),trades=len(trades),max_nav_error=float(np.max(abs(navs-l.nav.to_numpy()))),passed=True))
        if x['scenario']!='base':continue
        z=d.loc[x['start']:x['end']];ini=read(HERE/'prepared'/x['case']/'initial.json')[x['policy']]
        for n in [len(z)//2,len(z)-1]:
            sub=z.iloc[:n].copy();state=s.iloc[:n].copy();_,pl,pt,pf,po=eng.backtest(sub,state,ini,x['symbol'],SCENARIOS['base'],policy=x['policy'],entry_event_column='buy_event' if x['policy'] in ['G1_I','G1_IX'] else None)
            pd.testing.assert_frame_equal(pl.iloc[:-1],l.iloc[:n-1],check_exact=True,check_freq=False)
            a=pf.loc[pf.signal_date.ne('preset_end')].reset_index(drop=True);b=fills.loc[fills.signal_date.ne('preset_end')&fills.date.le(str(sub.index[-1].date()))].reset_index(drop=True)
            # Canonicalize only declared text serialization; numerical values stay exact.
            for col in ['date','side','signal_date','reason']:
                a[col]=a[col].astype('string');b[col]=b[col].astype('string')
            for col in ['quantity','raw_price','price','fee','slippage']:
                a[col]=a[col].astype('float64');b[col]=b[col].astype('float64')
            pd.testing.assert_frame_equal(a,b,check_exact=True)
            mark=float(pl.nav.iloc[-1]);terminal=pf.loc[pf.signal_date.eq('preset_end')]
            if len(terminal):
                r=terminal.iloc[0];mark+=float(r.quantity)*(float(sub.close.iloc[-1])-float(r.price))+float(r.fee)
            np.testing.assert_allclose(mark,l.nav.iloc[n-1],rtol=1e-12,atol=1e-12)
            prefixes.append(dict(key=x['key'],rows=n,exact_daily_before_terminal=n-1,last_mark_error=abs(mark-l.nav.iloc[n-1]),passed=True))
    assert len(details)==216 and len(prefixes)==144
    pd.DataFrame(details).to_csv(HERE/'accounting-audit.csv',index=False);pd.DataFrame(prefixes).to_csv(HERE/'account-prefixes.csv',index=False)
    verify();write(HERE/'accounting-audit.json',dict(recorded_at=now(),passed=True,accounts=len(details),daily_rows=sum(x['rows'] for x in details),fills=sum(x['fills'] for x in details),technical_account_prefixes=len(prefixes),max_nav_error=max(x['max_nav_error'] for x in details),old_sources_unchanged=True))
    print(read(HERE/'accounting-audit.json'),flush=True)

if __name__=='__main__':main()
