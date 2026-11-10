"""Post-main-result implementation diagnostic; frozen before sector account outcomes."""
import argparse,json,hashlib,datetime
from pathlib import Path
import pandas as pd,numpy as np
from run_competing_state import assets,write,run,CampaignClaims,cash_check,claims_check,audit_episodes

def targets(frames,flavor,kind):
    col='strength' if flavor=='pv' else 'price_strength';gate=frames['HK03033']['target' if flavor=='pv' else 'price_target'];stocks=['HK00700','HK03690','HK09618'];chosen=[];prev=0;history={s:[] for s in stocks};events=[]
    for day,level in gate.items():
        if level and not prev:
            ranking=sorted(stocks,key=lambda s:(-float(frames[s].loc[:day,col].iloc[-1]),s));chosen=ranking[:2] if kind=='top2' else stocks.copy();events.append(dict(date=str(day.date()),selected=chosen.copy(),scores={s:float(frames[s].loc[:day,col].iloc[-1]) for s in stocks}))
        if not level:chosen=[]
        for s in stocks:history[s].append(float(s in chosen))
        prev=level
    return gate,{s:pd.Series(history[s],index=gate.index).reindex(frames[s].index,method='ffill').fillna(0.) for s in stocks},events

def main(src,out):
    out.mkdir(exist_ok=False);write(out/'protocol.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='exploratory extension after main16 accounts, before these12 outcomes; no model changes',scope='same historical3 stock cohort as prior impact-sector pilot, common HK03033 new filter gate; initial90% ETF,30%all3,45%top2; picks fixed until exit; 2022..2026-10-16',cases='pv/price each ETF/all3/top2 base; pv all3structures additionally cost2/delay1;12total',fees='15bps FX10 base,30+20double; generic, not exact asymmetric stock/ETF taxes',source_signal_hashes={s:hashlib.sha256((src/f'{s}-signals.csv').read_bytes()).hexdigest() for s in ['HK03033','HK00700','HK03690','HK09618']}))
    frames={s:pd.read_csv(src/f'{s}-signals.csv',index_col='date',parse_dates=True) for s in ['HK03033','HK00700','HK03690','HK09618']};groups,_=assets();stocks={s:groups['hk7'][s] for s in ['HK00700','HK03690','HK09618']};recipients={s:groups['hk7'][s] for s in ['HK09618','HK03690']};rows=[]
    for flavor in ['pv','price']:
        for kind in ['etf','all3','top2']:
            gate,signals,events=targets(frames,flavor,kind);cut='2024-12-31';g,t,e=targets({s:f.loc[:cut] for s,f in frames.items()},flavor,kind);pd.testing.assert_series_equal(g,gate.loc[:cut]);assert e==[x for x in events if x['date']<=cut]
            for s in stocks:pd.testing.assert_series_equal(t[s],signals[s].loc[:cut])
            for sc,cost,fx,delay in [('base',15,10,0)]+([('cost2',30,20,0),('delay1',15,10,1)] if flavor=='pv' else []):
                case=f'{flavor}-{kind}-{sc}';chosen={'HK03033':groups['etf17']['HK03033']} if kind=='etf' else stocks;sig={'HK03033':gate} if kind=='etf' else signals;claims=None if kind=='etf' else CampaignClaims(stocks,recipients);kwargs=dict(selection=lambda d,s,q,p:s,entry_fraction=.45) if kind=='top2' else {}
                m,path,orders,decisions=run(chosen,'2022-01-01','2026-10-16','score_change',cost,fx,delay,security_claims=claims,signals=sig,cadence='daily',**kwargs);check=claims_check(chosen,path,orders,cost,fx,recipients) if claims else cash_check(chosen,path,orders,cost,fx);ep,daily,shape=audit_episodes(chosen,path,orders,fx);assert max(check.values())<1e-6 and shape['max_daily_error']<1e-6;assert all(o['signal_date']<o['date'] for o in orders)
                path.to_parquet(out/f'{case}-path.parquet');write(out/f'{case}-orders.json',orders);write(out/f'{case}-episodes.json',ep);write(out/f'{case}-selections.json',events);write(out/f'{case}-decisions.json',decisions);pd.DataFrame(daily).to_csv(out/f'{case}-daily-episodes.csv',index=False);rows.append(dict(case=case,**m,ledger=check,episodes=shape));write(out/'accounts.json',rows);print(case,m['total_return'],flush=True)
    write(out/'validation.json',dict(cases=len(rows),selection_prefix_checks=6,cut=cut,max_ledger_error=max(max(x['ledger'].values()) for x in rows)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.source,a.output)
